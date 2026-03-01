# Phase 4: Report and Integration - Research

**Researched:** 2026-03-01
**Domain:** Markdown report generation (backend), file download (frontend), SRS priority elevation (backend service integration)
**Confidence:** HIGH (codebase is the primary source; all patterns are established in prior phases)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REPT-01 | User can export a cognitive diagnostic report (Markdown format) containing concept, blind spots, score trajectory, and improvement suggestions | New `GET /cog-test/sessions/{id}/report` endpoint; backend assembles Markdown string from DB rows; frontend triggers browser file download via Blob URL |
| REPT-02 | Blind spots discovered during testing automatically elevate the corresponding model card's review priority in the SRS queue | After session ends (stop or complete), call `srs_service.process_review(schedule, quality=0)` on the linked model card's `ReviewSchedule`; if no schedule exists yet, create one via `srs_service.schedule_card()` then immediately apply quality=0 |
</phase_requirements>

---

## Summary

Phase 4 has two independent deliverables. REPT-01 is a backend report-assembly endpoint plus a one-line frontend download trigger. REPT-02 is a backend-only integration between the cog test session lifecycle and the existing `SRSService`.

For REPT-01, the backend already has all the data it needs: `CogTestSession`, `CogTestBlindSpot`, `CogTestSnapshot`, and `CogTestTurn` are all persisted. The endpoint reads these rows, formats them into a Markdown string in Python, and returns it as a `FileResponse` (or a plain text response with `Content-Disposition: attachment`). The frontend calls `GET /cog-test/sessions/{id}/report`, receives the file, and triggers a browser download using a Blob URL — the same pattern used by any "download file" button in a Vue 3 app. No new libraries are needed on either side.

For REPT-02, the integration surface is already fully understood. `SRSService` has `schedule_card()` and `process_review()`. `ReviewSchedule` is linked to `ModelCard` by `model_card_id`. The cog test session has a `model_card_id` column in the migration (though the ORM model currently stores `concept` as a string — this discrepancy must be resolved). The trigger point is the session end: either `POST /sessions/{id}/stop` or the natural `session_complete` event from the engine. At that point, if blind spots were found, the backend calls `process_review(schedule, quality=0)` to force the card back to interval=1 day and reset repetitions, making it appear at the top of the due queue.

**Primary recommendation:** Two backend tasks (report endpoint + SRS elevation hook) and one frontend task (Export Report button + download). All work is additive — no existing code needs to be rewritten.

---

## Standard Stack

### Core (all already in project — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | project standard | Report endpoint, response types | Project standard |
| SQLAlchemy async | project standard | Query CogTestBlindSpot, CogTestSnapshot, CogTestTurn | Project standard; all DB access uses AsyncSession |
| `fastapi.responses.Response` | built-in | Return Markdown file with Content-Disposition header | No FileResponse needed for in-memory string |
| `SRSService` | project code | `schedule_card()`, `process_review()` | Already implemented in `las_backend/app/services/srs_service.py` |
| Vue 3 + axios | project standard | Frontend download trigger | Project standard |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `textwrap` / f-strings | stdlib | Markdown string assembly | No template engine needed for simple Markdown |
| Browser `URL.createObjectURL` | browser built-in | Blob download trigger | Standard pattern for programmatic file download |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory Markdown string + Response | `FileResponse` with temp file | FileResponse requires writing to disk; in-memory string is simpler and sufficient for reports of this size |
| `process_review(quality=0)` for SRS elevation | Custom `next_review_at = now()` mutation | Using the existing service method keeps SM-2 state consistent; direct mutation bypasses the algorithm |
| Trigger SRS elevation in the stop/complete endpoint | Background task / celery | Background task adds complexity; the operation is fast (one DB read + one write) and can run synchronously in the endpoint |

**Installation:** No new packages needed.

---

## Architecture Patterns

### Recommended Project Structure

```
las_backend/app/
├── api/
│   └── cog_test.py          # MODIFY: add GET /sessions/{id}/report endpoint
│                            # MODIFY: add SRS elevation call in stop + session_complete path
├── services/
│   └── srs_service.py       # READ ONLY: use schedule_card() + process_review()
│
las_frontend/src/
├── views/
│   └── CogTestListView.vue  # MODIFY: add "Export Report" button per session row
│   └── CogTestSessionView.vue  # MODIFY: add "Export Report" button when status=completed
```

### Pattern 1: Markdown Report Assembly (Backend)

The report endpoint queries all related rows for the session and assembles a Markdown string. Return it as a `Response` with `media_type="text/markdown"` and `Content-Disposition: attachment`.

```python
# In las_backend/app/api/cog_test.py
from fastapi import Response
from sqlalchemy import select
from app.models.entities.user import CogTestSession, CogTestBlindSpot, CogTestSnapshot, CogTestTurn

@router.get("/sessions/{session_id}/report")
async def export_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Query blind spots
    blind_spots_result = await db.execute(
        select(CogTestBlindSpot)
        .where(CogTestBlindSpot.session_id == session_id)
        .order_by(CogTestBlindSpot.created_at)
    )
    blind_spots = list(blind_spots_result.scalars().all())

    # Query snapshots for score trajectory
    snapshots_result = await db.execute(
        select(CogTestSnapshot)
        .where(CogTestSnapshot.session_id == session_id)
        .order_by(CogTestSnapshot.round_number.nullslast())
    )
    snapshots = list(snapshots_result.scalars().all())

    md = _build_report_markdown(session, blind_spots, snapshots)

    filename = f"cog-report-{session.concept[:30].replace(' ', '-')}.md"
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_report_markdown(session, blind_spots, snapshots) -> str:
    lines = [
        f"# Cognitive Diagnostic Report",
        f"",
        f"**Concept:** {session.concept}",
        f"**Session ID:** {session.id}",
        f"**Status:** {session.status}",
        f"**Date:** {session.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
        f"## Blind Spots",
        f"",
    ]

    if blind_spots:
        for bs in blind_spots:
            lines.append(f"- **[{bs.category}]** {bs.description}")
    else:
        lines.append("No blind spots recorded.")

    lines += [
        f"",
        f"## Score Trajectory",
        f"",
    ]

    if snapshots:
        for snap in snapshots:
            label = f"Round {snap.round_number}" if snap.round_number else "Final"
            lines.append(f"- {label}: {snap.understanding_score} (blind spots: {snap.blind_spot_count})")
    else:
        lines.append("No score data recorded.")

    lines += [
        f"",
        f"## Improvement Suggestions",
        f"",
        f"Based on the blind spots identified above, focus your review on:",
        f"",
    ]

    gap_spots = [bs for bs in blind_spots if bs.category == "gap"]
    if gap_spots:
        for bs in gap_spots:
            lines.append(f"- {bs.description}")
    else:
        lines.append("- Continue reinforcing your understanding through spaced repetition.")

    return "\n".join(lines)
```

### Pattern 2: SRS Priority Elevation (Backend)

The elevation hook runs inside the stop and session_complete paths. It reads the session's `model_card_id`, checks if a `ReviewSchedule` exists, and applies `quality=0` to force the card to the front of the review queue.

```python
# Helper function — add to cog_test.py or a small utility
async def _elevate_srs_priority_if_blind_spots(
    session: CogTestSession,
    db: AsyncSession,
) -> None:
    """If the session has blind spots and a linked model card, push the SRS schedule forward."""
    # Check if there are any blind spots
    result = await db.execute(
        select(CogTestBlindSpot)
        .where(CogTestBlindSpot.session_id == session.id)
        .limit(1)
    )
    has_blind_spots = result.scalar_one_or_none() is not None

    if not has_blind_spots:
        return

    # Need a model_card_id to link to SRS
    model_card_id = getattr(session, 'model_card_id', None)
    if not model_card_id:
        return  # session was started without a model card link — skip

    # Find existing schedule
    sched_result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == session.user_id,
            ReviewSchedule.model_card_id == model_card_id,
        )
    )
    schedule = sched_result.scalar_one_or_none()

    if schedule is None:
        # Card not yet scheduled — create a schedule first
        schedule = srs_service.schedule_card(model_card_id, session.user_id)
        db.add(schedule)
        await db.flush()  # get the id without committing

    # Apply quality=0 (forgot) to force interval back to 1 day
    srs_service.process_review(schedule, quality=0)
    # Caller is responsible for db.commit()
```

Call this helper at the end of both the stop endpoint and the session_complete path in the engine's run loop (or in the stop endpoint after updating session status).

### Pattern 3: Frontend File Download (Vue 3)

The standard browser pattern for downloading a file from an API response is to create a Blob URL and click a hidden anchor element. No library needed.

```typescript
// In CogTestListView.vue or CogTestSessionView.vue
import api from '@/api'

const exportReport = async (sessionId: string, concept: string) => {
  const response = await api.get(`/cog-test/sessions/${sessionId}/report`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(new Blob([response.data], { type: 'text/markdown' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `cog-report-${concept.slice(0, 30).replace(/\s+/g, '-')}.md`
  a.click()
  URL.revokeObjectURL(url)
}
```

### Pattern 4: "Export Report" Button Placement

Two locations need the button:

1. `CogTestListView.vue` — add an "Export" button on each session row where `status === 'completed' || status === 'stopped'`
2. `CogTestSessionView.vue` — add an "Export Report" button in the status bar when `store.status === 'completed'`

```vue
<!-- CogTestListView.vue — inside session-item div -->
<button
  v-if="s.status === 'completed' || s.status === 'stopped'"
  class="btn btn-secondary btn-sm"
  @click="exportReport(s.id, s.concept)"
>
  {{ t('cogTest.exportReport') }}
</button>

<!-- CogTestSessionView.vue — inside status-bar, alongside "Session complete" message -->
<button
  v-if="store.status === 'completed'"
  class="btn btn-secondary"
  @click="exportReport(store.sessionId!, store.concept)"
>
  {{ t('cogTest.exportReport') }}
</button>
```

### Anti-Patterns to Avoid

- **Generating the report on the frontend from store.messages:** The store only holds the dialogue text, not the parsed blind spots or score snapshots. The backend DB is the authoritative source. Always fetch from the API.
- **Using `window.open(url)` for the download:** This opens a new tab and may be blocked by popup blockers. Use the Blob + anchor click pattern instead.
- **Calling `db.commit()` inside `_elevate_srs_priority_if_blind_spots`:** The helper should only mutate the schedule object; the caller (the endpoint) owns the transaction and calls `await db.commit()` once at the end.
- **Elevating SRS priority even when no blind spots exist:** The check `if not has_blind_spots: return` is critical — the requirement says "if blind spots were found." Don't penalize a perfect session.
- **Assuming `model_card_id` is always set on `CogTestSession`:** The ORM model has `concept` (string) but the migration has `model_card_id` (FK). The ORM must be verified/updated to include `model_card_id` before REPT-02 can work. See Open Questions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SRS priority manipulation | Custom `next_review_at = datetime.utcnow()` | `srs_service.process_review(schedule, quality=0)` | Keeps SM-2 state (ease_factor, repetitions, interval_days) consistent; direct date mutation leaves the algorithm in a corrupt state |
| File download | Custom streaming endpoint / base64 encoding | `Response(content=md_string, media_type="text/markdown", headers={"Content-Disposition": ...})` | In-memory string response is the simplest correct approach for small text files |
| Markdown templating | Jinja2 / markdown library | Python f-strings / string join | The report structure is simple and fixed; no template engine needed |
| Blob download | Third-party download library | `URL.createObjectURL` + anchor click | Standard browser API; zero dependencies |

**Key insight:** Both deliverables are thin wiring of already-built components. The complexity is in knowing which existing pieces to connect, not in building new infrastructure.

---

## Common Pitfalls

### Pitfall 1: ORM Model vs Migration Schema Mismatch on `model_card_id`

**What goes wrong:** `CogTestSession` ORM class (in `user.py`) does not have a `model_card_id` column, but the Alembic migration `001` creates the column in the DB. REPT-02 needs `session.model_card_id` to find the `ReviewSchedule`.

**Why it happens:** The ORM was written after the migration, and `model_card_id` was not added to the ORM class. The `concept` string field was used instead.

**How to avoid:** Before implementing REPT-02, add `model_card_id = Column(String(36), ForeignKey("model_cards.id"), nullable=True)` to the `CogTestSession` ORM class. Also verify that `POST /cog-test/sessions` saves the `model_card_id` when the session is started from a model card detail page (Phase 3 SESS-01 passes `concept` but may not pass `model_card_id`).

**Warning signs:** `AttributeError: 'CogTestSession' object has no attribute 'model_card_id'` at runtime.

### Pitfall 2: SRS Schedule May Not Exist for the Model Card

**What goes wrong:** The user starts a cog test from a model card that has never been added to the SRS queue. `_elevate_srs_priority_if_blind_spots` queries for a `ReviewSchedule` and gets `None`, then skips elevation silently.

**Why it happens:** `ReviewSchedule` rows are only created when the user explicitly clicks "Add to Review Queue" in the SRS view. A model card can exist without a schedule.

**How to avoid:** When no schedule exists, create one via `srs_service.schedule_card(model_card_id, user_id)` and then immediately apply `process_review(schedule, quality=0)`. This auto-enrolls the card in SRS with elevated priority. This is the correct behavior — the blind spot discovery is itself a signal that the card needs review.

### Pitfall 3: Report Endpoint Called on Active Session

**What goes wrong:** User calls the report endpoint while the session is still `active`. The blind spots and snapshots may be incomplete (mid-session data).

**Why it happens:** No status guard on the report endpoint.

**How to avoid:** Add a status check: if `session.status == "active"`, return HTTP 400 with `"Session is still active. Stop or complete the session before exporting."` Alternatively, allow it but note in the report that data may be incomplete — the simpler approach is the 400 guard.

### Pitfall 4: `Content-Disposition` Filename with Special Characters

**What goes wrong:** Concept names may contain Chinese characters or spaces. The `Content-Disposition` header with a raw non-ASCII filename causes browser download issues.

**Why it happens:** RFC 6266 requires non-ASCII filenames to be encoded with `filename*=UTF-8''...` syntax.

**How to avoid:** Sanitize the filename to ASCII-safe characters before embedding in the header. The simplest approach: replace spaces with hyphens, strip non-ASCII characters, truncate to 50 chars.

```python
import re
safe_name = re.sub(r'[^\w\-]', '', session.concept.replace(' ', '-'))[:50]
filename = f"cog-report-{safe_name}.md"
```

### Pitfall 5: `db.flush()` vs `db.commit()` in the SRS Helper

**What goes wrong:** The helper calls `db.add(schedule)` for a new schedule, then immediately calls `srs_service.process_review(schedule, quality=0)`. If `flush()` is not called before `process_review`, the schedule object may not have its `id` set (depending on SQLAlchemy's default generation).

**Why it happens:** `uuid4()` default is a Python-side default, so the `id` is set at object creation time — `flush()` is not strictly required for the id. However, `flush()` is still good practice to ensure the row is visible within the transaction before the commit.

**How to avoid:** Call `await db.flush()` after `db.add(schedule)` and before `process_review`. The endpoint then calls `await db.commit()` once at the end.

---

## Code Examples

### Full Report Endpoint (verified against codebase patterns)

```python
# Source: codebase pattern from las_backend/app/api/routes/srs.py + model inspection
@router.get("/sessions/{session_id}/report")
async def export_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "active":
        raise HTTPException(status_code=400, detail="Session still active")

    blind_spots_result = await db.execute(
        select(CogTestBlindSpot)
        .where(CogTestBlindSpot.session_id == session_id)
        .order_by(CogTestBlindSpot.created_at)
    )
    blind_spots = list(blind_spots_result.scalars().all())

    snapshots_result = await db.execute(
        select(CogTestSnapshot)
        .where(CogTestSnapshot.session_id == session_id)
        .order_by(CogTestSnapshot.round_number.nullslast())
    )
    snapshots = list(snapshots_result.scalars().all())

    md = _build_report_markdown(session, blind_spots, snapshots)
    safe_name = re.sub(r'[^\w\-]', '', session.concept.replace(' ', '-'))[:50]
    filename = f"cog-report-{safe_name}.md"

    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

### SRS Elevation Call Site (in stop endpoint)

```python
# Source: codebase pattern from las_backend/app/api/routes/srs.py
@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    engine = get_engine(session_id)
    if engine:
        await engine.stop()
        unregister_engine(session_id)

    session.status = "stopped"

    # REPT-02: elevate SRS priority if blind spots found
    await _elevate_srs_priority_if_blind_spots(session, db)

    await db.commit()
    return {"status": "stopped"}
```

### Frontend Export Button Logic

```typescript
// Source: standard browser Blob download pattern
const exportReport = async (sessionId: string, concept: string) => {
  try {
    const response = await api.get(`/cog-test/sessions/${sessionId}/report`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([response.data], { type: 'text/markdown' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `cog-report-${concept.slice(0, 30).replace(/\s+/g, '-')}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Export failed', e)
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PDF generation (pdfkit, weasyprint) | Plain Markdown text file | Markdown is simpler, no binary dependency, renders well in GitHub/Obsidian/VS Code |
| Server-side file storage + signed URL | In-memory Response with Content-Disposition | No storage needed for ephemeral reports; generated on demand |
| Manual SRS priority override (set date directly) | `process_review(quality=0)` via existing SM-2 service | Keeps algorithm state consistent; reuses existing tested code |

**Deprecated/outdated:**
- `FileResponse`: Requires writing to disk first. Use `Response(content=string)` for in-memory text.

---

## Open Questions

1. **`model_card_id` missing from `CogTestSession` ORM**
   - What we know: The Alembic migration `001` creates `model_card_id` column in `cog_test_sessions`. The ORM class `CogTestSession` in `user.py` does NOT have this column — it only has `concept` (string).
   - What's unclear: Whether Phase 2/3 implementation actually saves `model_card_id` when creating a session, or whether it was intentionally dropped in favor of the `concept` string.
   - Recommendation: Wave 0 of Phase 4 must add `model_card_id = Column(String(36), ForeignKey("model_cards.id"), nullable=True)` to the ORM. Also verify that `POST /cog-test/sessions` accepts and saves `model_card_id`. If the frontend only sends `concept`, REPT-02 cannot link to a `ReviewSchedule` and must degrade gracefully (log a warning, skip elevation).

2. **Session `concept` vs `model_card_id` for SRS lookup**
   - What we know: `ReviewSchedule` is keyed on `model_card_id`, not on concept name. If `model_card_id` is not stored on the session, there is no reliable way to find the schedule.
   - What's unclear: Whether the Phase 3 "Start Cognitive Test" button (SESS-01) passes the model card's `id` to the backend, or only the `title` as `concept`.
   - Recommendation: The Phase 4 Wave 0 task should inspect the actual `POST /cog-test/sessions` implementation and the frontend `startSession()` call to confirm whether `model_card_id` is being passed. If not, add it to both the request body schema and the session creation logic.

3. **SRS elevation trigger: stop endpoint only, or also session_complete?**
   - What we know: Sessions end in two ways: user calls `POST /stop`, or the engine naturally completes all rounds and emits `session_complete`. The stop endpoint is a clear trigger point. The `session_complete` path runs inside `engine.run()` in the service layer, which does not have direct access to the SRS service.
   - Recommendation: Trigger elevation in the stop endpoint (explicit stop) AND add a post-run hook in the stream endpoint after `engine.run()` completes naturally. The stream endpoint already has a `db` session available. After `EventSourceResponse(engine.run(db))` returns, check if the session status is `completed` and call the elevation helper.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `las_backend/app/services/srs_service.py` — `SRSService.process_review()`, `schedule_card()`, `get_due_cards()` — confirmed API surface
- Codebase: `las_backend/app/models/entities/user.py` — `CogTestSession`, `CogTestBlindSpot`, `CogTestSnapshot`, `CogTestTurn`, `ReviewSchedule` ORM definitions
- Codebase: `las_backend/app/api/routes/srs.py` — existing SRS endpoint patterns (auth, DB session, service calls)
- Codebase: `las_backend/app/api/cog_test.py` — existing cog test router structure
- Codebase: `las_backend/alembic/versions/001_add_cog_test_tables.py` — confirmed `model_card_id` column exists in DB but not in ORM
- Codebase: `las_frontend/src/stores/cogTest.ts` — `SessionSummary` interface, `fetchSessions()`, `stopSession()` — confirmed frontend state shape
- Codebase: `las_frontend/src/views/CogTestListView.vue` — session list rendering pattern
- Codebase: `las_frontend/src/views/CogTestSessionView.vue` — session view, status-based conditional rendering
- Codebase: `las_frontend/src/views/SRSReviewView.vue` — SRS queue display pattern (confirms `next_review_at` drives ordering)

### Secondary (MEDIUM confidence)

- MDN Web Docs (training knowledge): `URL.createObjectURL` + anchor click for programmatic file download — standard browser pattern, widely documented
- FastAPI docs (training knowledge): `Response(content=..., media_type=..., headers=...)` for returning arbitrary content — confirmed against FastAPI's Response class signature

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project; no new dependencies
- Architecture: HIGH — derived directly from existing code; both SRSService and cog test ORM are fully readable
- Pitfalls: HIGH — ORM/migration mismatch is a concrete finding from reading the actual files; other pitfalls are standard FastAPI/browser patterns

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable stack; no fast-moving dependencies)
