#!/usr/bin/env bash
set -Eeuo pipefail

# Cogniforge production deploy helper
# Default workflow:
# 1) Pull latest main
# 2) Backup SQLite data volume
# 3) Build backend/frontend images
# 4) Restart selected services
# 5) Run basic health checks

APP_DIR="/data/Cogniforge"
BRANCH="main"
DB_VOLUME_LOGICAL="las_db_data"
BACKUP_DIR=""
NO_CACHE=0
SKIP_BACKUP=0
SKIP_PULL=0
SERVICES=()

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  echo "[$(timestamp)] $*"
}

die() {
  echo "[$(timestamp)] ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./deploy.sh [options]

Options:
  --app-dir <path>          Project directory (default: /data/Cogniforge)
  --branch <name>           Git branch to deploy (default: main)
  --services <list>         Comma-separated service list (default: backend,frontend)
  --db-volume <name>        Logical DB volume name in compose (default: las_db_data)
  --backup-dir <path>       Backup directory (default: <app-dir>/backups)
  --skip-backup             Skip DB backup
  --skip-pull               Skip git pull
  --no-cache                Use --no-cache on docker compose build
  -h, --help                Show this help

Examples:
  ./deploy.sh
  ./deploy.sh --services backend
  ./deploy.sh --branch main --no-cache
  ./deploy.sh --skip-backup --services backend,frontend
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --app-dir)
        [[ $# -ge 2 ]] || die "--app-dir requires a value"
        APP_DIR="$2"
        shift 2
        ;;
      --branch)
        [[ $# -ge 2 ]] || die "--branch requires a value"
        BRANCH="$2"
        shift 2
        ;;
      --services)
        [[ $# -ge 2 ]] || die "--services requires a value"
        IFS=',' read -r -a SERVICES <<<"$2"
        shift 2
        ;;
      --db-volume)
        [[ $# -ge 2 ]] || die "--db-volume requires a value"
        DB_VOLUME_LOGICAL="$2"
        shift 2
        ;;
      --backup-dir)
        [[ $# -ge 2 ]] || die "--backup-dir requires a value"
        BACKUP_DIR="$2"
        shift 2
        ;;
      --skip-backup)
        SKIP_BACKUP=1
        shift
        ;;
      --skip-pull)
        SKIP_PULL=1
        shift
        ;;
      --no-cache)
        NO_CACHE=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1 (use --help)"
        ;;
    esac
  done
}

dc() {
  docker compose "$@"
}

normalize_services() {
  if [[ ${#SERVICES[@]} -eq 0 ]]; then
    SERVICES=("backend" "frontend")
  fi
}

check_repo_clean() {
  local tracked_changes
  tracked_changes="$(git status --porcelain --untracked-files=no)"
  if [[ -n "$tracked_changes" ]]; then
    die "Git working tree has tracked changes. Commit/stash before deploy."
  fi
}

resolve_db_volume_name() {
  local backend_cid
  local mounted_name
  local candidate

  backend_cid="$(dc ps -q backend 2>/dev/null || true)"
  if [[ -n "$backend_cid" ]]; then
    mounted_name="$(docker inspect "$backend_cid" --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null || true)"
    if [[ -n "$mounted_name" ]]; then
      echo "$mounted_name"
      return 0
    fi
  fi

  if docker volume inspect "$DB_VOLUME_LOGICAL" >/dev/null 2>&1; then
    echo "$DB_VOLUME_LOGICAL"
    return 0
  fi

  candidate="$(docker volume ls --format '{{.Name}}' | grep -E "_${DB_VOLUME_LOGICAL}$" | head -n 1 || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

backup_db() {
  local volume_name
  local backup_name
  local backup_path

  [[ "$SKIP_BACKUP" -eq 1 ]] && {
    log "Skip DB backup (requested)."
    return 0
  }

  mkdir -p "$BACKUP_DIR"

  volume_name="$(resolve_db_volume_name)" || die "Cannot resolve docker volume for DB ($DB_VOLUME_LOGICAL)."
  backup_name="las_db_$(date +%F_%H%M%S).tgz"
  backup_path="$BACKUP_DIR/$backup_name"

  log "Backing up DB volume '$volume_name' -> $backup_path"
  docker run --rm \
    -v "${volume_name}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine sh -c "tar czf /backup/${backup_name} -C /data ."
}

pull_code() {
  local before_sha
  local after_sha

  [[ "$SKIP_PULL" -eq 1 ]] && {
    log "Skip git pull (requested)."
    return 0
  }

  check_repo_clean

  before_sha="$(git rev-parse --short HEAD)"
  log "Updating code on branch '$BRANCH' (current: $before_sha)"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
  after_sha="$(git rev-parse --short HEAD)"
  log "Code updated: $before_sha -> $after_sha"
}

build_images() {
  if [[ "$NO_CACHE" -eq 1 ]]; then
    log "Building services (no cache): ${SERVICES[*]}"
    dc build --no-cache "${SERVICES[@]}"
  else
    log "Building services: ${SERVICES[*]}"
    dc build "${SERVICES[@]}"
  fi
}

restart_services() {
  log "Restarting services: ${SERVICES[*]}"
  dc up -d "${SERVICES[@]}"
}

wait_backend_health() {
  local max_retry=30
  local i

  if ! printf '%s\n' "${SERVICES[@]}" | grep -qx "backend"; then
    return 0
  fi

  if ! command -v curl >/dev/null 2>&1; then
    log "curl not found; skip /health check."
    return 0
  fi

  log "Waiting for backend health endpoint..."
  for ((i=1; i<=max_retry; i++)); do
    if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
      log "Backend health check passed."
      return 0
    fi
    sleep 2
  done

  die "Backend health check failed after $max_retry retries."
}

show_summary() {
  log "docker compose ps"
  dc ps
  log "Recent backend/frontend logs"
  dc logs --tail=80 backend frontend || true
}

main() {
  require_cmd git
  require_cmd docker

  parse_args "$@"
  normalize_services

  BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"

  [[ -d "$APP_DIR" ]] || die "App dir not found: $APP_DIR"
  cd "$APP_DIR"
  [[ -f "docker-compose.yml" ]] || die "docker-compose.yml not found in $APP_DIR"

  log "Deploy start: app_dir=$APP_DIR branch=$BRANCH services=${SERVICES[*]}"
  backup_db
  pull_code
  build_images
  restart_services
  wait_backend_health
  show_summary
  log "Deploy finished successfully."
}

main "$@"
