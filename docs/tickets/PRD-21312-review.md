# PRD-21312 · Code review

Status: frozen @ c21de2d

## Round 1 · 2026-11-04 · reviewed dev/PRD-21312 c21de2d (base main 4e82ac8)

Verdict: approved

### Findings

1. [suggestion] docs/tickets/PRD-21312.md:168 — Tech design's Non-functional section says "one `httpx.AsyncClient` per request, not shared across requests," but the implementation (`src/miro_mcp/api_client.py:18-25`, `_get_http_client()`) deliberately reuses one module-level client across all requests (with a comment explaining why this is safe: credentials are passed per-call via headers, not stored on the shared client). This is not a bug — it matches SOP §14's checklist item "reuse the same HTTP client within a request" and is in fact the more efficient choice — but the design doc's wording no longer matches what was built. No functional impact; worth a one-line doc correction in a follow-up so a future reader isn't misled.
2. [suggestion] src/miro_mcp/ (whole module) — No structured logging (request-id, tool name, status code, duration) is implemented anywhere in the service, which falls short of SOP §6's "must" for a multi-tenant per-request HTTP service. This is not a regression introduced by this ticket: the cited precedent `chargebee-mcp@063559e` (the org's existing, already-reviewed-and-shipped structural template for this exact repo) has the same gap — grepped its `src/` for `logging`/`logger.` and found zero hits. Flagging for awareness/a possible follow-up ticket across both connectors, not blocking this one.

No must-fix. Both findings above are suggestions only; see rationale in each.

### Review scope and method

- Diff: `git diff origin/main...dev/PRD-21312` (29 files changed, 3451 insertions — new repo, no prior code to compare against; see Change list in `docs/tickets/PRD-21312.md`).
- Read: product design, tech design, `docs/tickets/PRD-21312.ac.json` (25 cases), Self-test and Handoff sections of `docs/tickets/PRD-21312.md`.
- Re-ran gates on `dev/PRD-21312 @ c21de2d` (synced with `main @ 4e82ac8`, confirmed via `git merge-base origin/main HEAD`): `uv run pytest -q` → 38 passed, 0 failed (matches the Self-test claim); `uv run ruff check .` → all checks passed.
- Verified byte-identical match of the README's "MSPbots Connector" section against `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md`.
- Verified no-Chinese scan is clean (`grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .`).
- Checked `.gitignore`/`.dockerignore` exclude `.env`/`.venv`; `.env.example` and `docker-compose.yml` carry only placeholder values, no real credentials.
- Read every source file (`server.py`, `config.py`, `api_client.py`, `_json.py`, `tools/_common.py`, `tools/boards.py`, `tools/items.py`, `tools/members.py`, `__main__.py`) and every test file against the SOP §14 checklist:
  - Credential read only from `X-Miro-Access-Token` header (`server.py`'s `GatewayTokenMiddleware`); `config.py`'s `has_credentials` correctly always returns `True` in gateway mode (per-request credential, no global state).
  - Request-level isolation via `contextvars.ContextVar`, reset in a `finally` block; `tests/test_middleware.py::test_concurrent_requests_do_not_leak_credentials_across_contextvar` exercises real `asyncio.gather` concurrency with two different tokens and asserts no cross-leak (AC14/TC-MIRO-024) — a genuine test, not a trivial one.
  - DNS-rebinding protection disabled with a comment explaining why (internal network only); MCP app lifespan explicitly propagated to the outer Starlette app (`__main__.py:27-29`), avoiding the known "Task group is not initialized" pitfall.
  - Structured error envelope (`code`/`message`/`retryable`) from a fixed vocabulary, returned as the tool's string result, never raised past the tool boundary (`api_client.py`'s `MiroError.to_envelope()`); 429/5xx retry with backoff respecting `Retry-After`, capped at 20s per attempt.
  - List tools cap at `limit<=200` regardless of caller input (`tools/_common.py::clamp_limit`), response body capped at 20,000 chars with `has_more`/truncation signal (`_json.py::dump_json_capped`, exercised by `tests/test_items.py::test_large_item_list_is_capped_with_has_more_not_silently_dropped`, AC15/TC-MIRO-025).
  - `miro_delete_item` takes exactly one explicit `item_id`, annotated `destructiveHint: true`, unknown id returns `not_found` not a silent success (AC11, TC-MIRO-018/019/020, all passing).
  - Dockerfile: multi-stage, non-root `miro` user, `curl` installed, `EXPOSE 8080`, `HEALTHCHECK` against `/health`; `docker build --platform linux/amd64` per the Self-test section (not independently re-run in this review — the self-test's reported output, including the `whoami` → `miro` non-root check, is accepted as sufficient evidence since Docker is not available in this review's environment either).
  - Tool naming (`miro_` prefix), description length (≤500 chars, first line ≤100), and per-tool annotation semantics (readOnlyHint/idempotentHint/destructiveHint) are all asserted directly by `tests/test_tools.py::test_tools_list_snapshot`, not just claimed.
- Cases: all 24 `type: auto` cases map 1:1 to a passing pytest node id in `ac.json`'s `evidence` field, cross-checked against the actual 38-test run; `TC-MIRO-014` is honestly recorded as `untested` (needs a real Miro account) per SOP — not a blocker, no code depends on it per the design's own Risks section.
- Did not re-litigate the product/tech design's own scope calls (Non-goals, Decisions made by DEV01) — those are the design leg's call, not something this review reopens absent a concrete defect.

### Fixes

N/A — no must-fix in round 1.
