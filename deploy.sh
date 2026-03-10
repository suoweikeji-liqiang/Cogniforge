#!/usr/bin/env bash
set -Eeuo pipefail

# Cogniforge production deploy helper
# Default workflow:
# 1) Pull latest main
# 2) Backup database (PostgreSQL by default, SQLite fallback)
# 3) Build backend/frontend images
# 4) Run backend maintenance (schema migration, optional data import)
# 5) Restart selected services
# 6) Run basic health checks

APP_DIR="/data/Cogniforge"
BRANCH="main"
BACKUP_MODE="auto"
DB_VOLUME_LOGICAL="postgres_data"
POSTGRES_SERVICE="postgres"
POSTGRES_DB="las_db"
POSTGRES_USER="postgres"
BACKUP_DIR=""
NO_CACHE=0
SKIP_BACKUP=0
SKIP_PULL=0
SKIP_BACKFILL=0
TARGET_DB_URL=""
MIGRATE_SQLITE=""
TRUNCATE_TARGET=0
SERVICES=()
INVOKE_CWD="$(pwd -P)"

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
  --backup-mode <mode>      auto, postgres, or sqlite (default: auto)
  --db-volume <name>        Logical DB volume name in compose (default: postgres_data)
  --pg-service <name>       PostgreSQL service name in compose (default: postgres)
  --pg-db <name>            PostgreSQL database name (default: las_db)
  --pg-user <name>          PostgreSQL user (default: postgres)
  --backup-dir <path>       Backup directory (default: <app-dir>/backups)
  --migrate-sqlite <path>   Import data from a SQLite file after migrations
  --target-db-url <url>     Target PostgreSQL URL for SQLite import
  --truncate-target         Truncate target tables before SQLite import
  --skip-backup             Skip DB backup
  --skip-backfill           Skip embedding backfill after SQLite import
  --skip-pull               Skip git pull
  --no-cache                Use --no-cache on docker compose build
  -h, --help                Show this help

Examples:
  ./deploy.sh
  ./deploy.sh --services backend
  ./deploy.sh --branch main --no-cache
  ./deploy.sh --skip-backup --services backend,frontend
  ./deploy.sh --migrate-sqlite /data/legacy/las.db
  ./deploy.sh --migrate-sqlite ./las.db --truncate-target --target-db-url postgresql+asyncpg://postgres:postgres@postgres:5432/las_db
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
      --backup-mode)
        [[ $# -ge 2 ]] || die "--backup-mode requires a value"
        BACKUP_MODE="$2"
        shift 2
        ;;
      --db-volume)
        [[ $# -ge 2 ]] || die "--db-volume requires a value"
        DB_VOLUME_LOGICAL="$2"
        shift 2
        ;;
      --pg-service)
        [[ $# -ge 2 ]] || die "--pg-service requires a value"
        POSTGRES_SERVICE="$2"
        shift 2
        ;;
      --pg-db)
        [[ $# -ge 2 ]] || die "--pg-db requires a value"
        POSTGRES_DB="$2"
        shift 2
        ;;
      --pg-user)
        [[ $# -ge 2 ]] || die "--pg-user requires a value"
        POSTGRES_USER="$2"
        shift 2
        ;;
      --backup-dir)
        [[ $# -ge 2 ]] || die "--backup-dir requires a value"
        BACKUP_DIR="$2"
        shift 2
        ;;
      --migrate-sqlite)
        [[ $# -ge 2 ]] || die "--migrate-sqlite requires a value"
        MIGRATE_SQLITE="$2"
        shift 2
        ;;
      --target-db-url)
        [[ $# -ge 2 ]] || die "--target-db-url requires a value"
        TARGET_DB_URL="$2"
        shift 2
        ;;
      --truncate-target)
        TRUNCATE_TARGET=1
        shift
        ;;
      --skip-backup)
        SKIP_BACKUP=1
        shift
        ;;
      --skip-backfill)
        SKIP_BACKFILL=1
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

validate_args() {
  if [[ -n "$TARGET_DB_URL" && -z "$MIGRATE_SQLITE" ]]; then
    die "--target-db-url requires --migrate-sqlite"
  fi

  if [[ "$TRUNCATE_TARGET" -eq 1 && -z "$MIGRATE_SQLITE" ]]; then
    die "--truncate-target requires --migrate-sqlite"
  fi

  if [[ "$SKIP_BACKFILL" -eq 1 && -z "$MIGRATE_SQLITE" ]]; then
    die "--skip-backfill requires --migrate-sqlite"
  fi
}

has_service() {
  local target="$1"
  local service

  for service in "${SERVICES[@]}"; do
    if [[ "$service" == "$target" ]]; then
      return 0
    fi
  done

  return 1
}

add_service_if_missing() {
  local service="$1"

  if ! has_service "$service"; then
    SERVICES+=("$service")
    log "Added service '$service' because backend maintenance was requested."
  fi
}

resolve_abs_path() {
  local input_path="$1"
  local base_dir
  local file_name

  if [[ -z "$input_path" ]]; then
    die "Path cannot be empty."
  fi

  if [[ "$input_path" != /* ]]; then
    input_path="$INVOKE_CWD/$input_path"
  fi

  [[ -e "$input_path" ]] || die "Path not found: $input_path"

  base_dir="$(cd "$(dirname "$input_path")" && pwd -P)"
  file_name="$(basename "$input_path")"
  echo "$base_dir/$file_name"
}

normalize_services() {
  if [[ ${#SERVICES[@]} -eq 0 ]]; then
    SERVICES=("backend" "frontend")
  fi

  case "$BACKUP_MODE" in
    auto|postgres|sqlite) ;;
    *) die "Invalid --backup-mode: $BACKUP_MODE" ;;
  esac

  if [[ -n "$MIGRATE_SQLITE" ]]; then
    add_service_if_missing "backend"
  fi
}

check_repo_clean() {
  local tracked_changes
  tracked_changes="$(git status --porcelain --untracked-files=no)"
  if [[ -n "$tracked_changes" ]]; then
    echo "$tracked_changes" >&2
    die "Git working tree has tracked changes. Commit/stash before deploy, or use --skip-pull."
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
  [[ "$SKIP_BACKUP" -eq 1 ]] && {
    log "Skip DB backup (requested)."
    return 0
  }

  mkdir -p "$BACKUP_DIR"

  if [[ "$BACKUP_MODE" == "postgres" ]]; then
    backup_postgres_db
    return 0
  fi

  if [[ "$BACKUP_MODE" == "sqlite" ]]; then
    backup_sqlite_db
    return 0
  fi

  if dc ps -q "$POSTGRES_SERVICE" >/dev/null 2>&1 && [[ -n "$(dc ps -q "$POSTGRES_SERVICE" 2>/dev/null || true)" ]]; then
    backup_postgres_db
    return 0
  fi

  backup_sqlite_db
}

backup_postgres_db() {
  local backup_name
  local backup_path

  backup_name="las_db_$(date +%F_%H%M%S).sql.gz"
  backup_path="$BACKUP_DIR/$backup_name"

  log "Backing up PostgreSQL database '$POSTGRES_DB' from service '$POSTGRES_SERVICE' -> $backup_path"
  dc exec -T "$POSTGRES_SERVICE" sh -lc \
    'PGPASSWORD="${POSTGRES_PASSWORD:?}" pg_dump -U "${POSTGRES_USER:?}" "${POSTGRES_DB:?}"' \
    | gzip > "$backup_path"
}

backup_sqlite_db() {
  local volume_name
  local backup_name
  local backup_path

  volume_name="$(resolve_db_volume_name)" || die "Cannot resolve docker volume for DB ($DB_VOLUME_LOGICAL)."
  backup_name="las_db_$(date +%F_%H%M%S).tgz"
  backup_path="$BACKUP_DIR/$backup_name"

  log "Backing up DB volume '$volume_name' -> $backup_path"
  docker run --rm \
    -v "${volume_name}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine sh -c "tar czf /backup/${backup_name} -C /data ."
}

service_declared() {
  dc config --services 2>/dev/null | grep -qx "$1"
}

pull_code() {
  local before_sha
  local after_sha

  [[ "$SKIP_PULL" -eq 1 ]] && {
    log "Skip git pull (requested)."
    return 0
  }

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

ensure_service_running() {
  local service="$1"

  if ! service_declared "$service"; then
    die "Service '$service' is not declared in docker-compose.yml"
  fi

  log "Ensuring service '$service' is running"
  dc up -d "$service"
}

wait_service_ready() {
  local service="$1"
  local max_retry="${2:-30}"
  local sleep_seconds="${3:-2}"
  local container_id
  local status
  local i

  for ((i=1; i<=max_retry; i++)); do
    container_id="$(dc ps -q "$service" 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      status="$(docker inspect "$container_id" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)"
      case "$status" in
        healthy|running)
          log "Service '$service' is ready ($status)."
          return 0
          ;;
        created|starting|restarting|"")
          ;;
        unhealthy|exited|dead)
          die "Service '$service' is not healthy (status: $status)"
          ;;
      esac
    fi
    sleep "$sleep_seconds"
  done

  die "Service '$service' did not become ready after $max_retry checks."
}

prepare_backend_maintenance() {
  if ! has_service "backend"; then
    return 0
  fi

  if service_declared "$POSTGRES_SERVICE"; then
    ensure_service_running "$POSTGRES_SERVICE"
    wait_service_ready "$POSTGRES_SERVICE" 30 2
  else
    log "Compose service '$POSTGRES_SERVICE' not found; assuming backend uses an external database."
  fi
}

run_backend_migrations() {
  if ! has_service "backend"; then
    return 0
  fi

  log "Running backend database migrations"
  dc run --rm backend sh -lc "alembic upgrade head"
}

run_sqlite_import() {
  local source_dir
  local source_file
  local import_cmd

  [[ -n "$MIGRATE_SQLITE" ]] || return 0

  source_dir="$(dirname "$MIGRATE_SQLITE")"
  source_file="$(basename "$MIGRATE_SQLITE")"
  import_cmd='target_url="${TARGET_DB_URL:-${DATABASE_URL:?DATABASE_URL not set in backend service}}"; '
  import_cmd+='python3 scripts/migrate_sqlite_to_postgres.py '
  import_cmd+='--source-sqlite "/migration-src/${MIGRATION_SOURCE_FILE}" '
  import_cmd+='--target-url "$target_url"'

  if [[ "$TRUNCATE_TARGET" -eq 1 ]]; then
    import_cmd+=' --truncate-target'
  fi

  log "Importing SQLite data from '$MIGRATE_SQLITE'"
  dc run --rm \
    -e TARGET_DB_URL="${TARGET_DB_URL}" \
    -e MIGRATION_SOURCE_FILE="${source_file}" \
    -v "${source_dir}:/migration-src:ro" \
    backend sh -lc "$import_cmd"
}

run_embedding_backfill() {
  if [[ -z "$MIGRATE_SQLITE" ]]; then
    return 0
  fi

  if [[ "$SKIP_BACKFILL" -eq 1 ]]; then
    log "Skip embedding backfill (requested)."
    return 0
  fi

  log "Running embedding backfill"
  dc run --rm backend sh -lc "python3 scripts/backfill_model_card_embeddings.py"
}

run_backend_maintenance() {
  if ! has_service "backend"; then
    return 0
  fi

  prepare_backend_maintenance
  run_backend_migrations
  run_sqlite_import
  run_embedding_backfill
}

restart_services() {
  log "Restarting services: ${SERVICES[*]}"
  dc up -d "${SERVICES[@]}"
}

wait_backend_health() {
  local max_retry=30
  local backend_port
  local i

  if ! printf '%s\n' "${SERVICES[@]}" | grep -qx "backend"; then
    return 0
  fi

  if ! command -v curl >/dev/null 2>&1; then
    log "curl not found; skip /health check."
    return 0
  fi

  backend_port="$(dc port backend 8000 2>/dev/null | awk -F: 'END{print $NF}')"
  backend_port="${backend_port:-8000}"

  log "Waiting for backend health endpoint on port ${backend_port}..."
  for ((i=1; i<=max_retry; i++)); do
    if curl -fsS "http://127.0.0.1:${backend_port}/health" >/dev/null 2>&1; then
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
  validate_args

  if [[ -n "$MIGRATE_SQLITE" ]]; then
    MIGRATE_SQLITE="$(resolve_abs_path "$MIGRATE_SQLITE")"
    [[ -f "$MIGRATE_SQLITE" ]] || die "SQLite source file not found: $MIGRATE_SQLITE"
  fi

  normalize_services

  BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"

  [[ -d "$APP_DIR" ]] || die "App dir not found: $APP_DIR"
  cd "$APP_DIR"
  [[ -f "docker-compose.yml" ]] || die "docker-compose.yml not found in $APP_DIR"
  [[ -f ".env" ]] || die ".env not found in $APP_DIR. Copy .env.example to .env and set deployment secrets before deploy."

  if [[ "$SKIP_PULL" -eq 0 ]]; then
    check_repo_clean
  fi

  log "Deploy start: app_dir=$APP_DIR branch=$BRANCH services=${SERVICES[*]}"
  backup_db
  pull_code
  build_images
  run_backend_maintenance
  restart_services
  wait_backend_health
  show_summary
  log "Deploy finished successfully."
}

main "$@"
