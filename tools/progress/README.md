# Progress dashboard tools

- `build.js`: merges tracker fragments, then builds `wiki/progress/index.html` from `wiki/progress/tracker.json`. Run `node tools/progress/build.js`. Never edit `index.html` by hand.
- `fragments.js`: the fragment merge (also usable alone: `node tools/progress/fragments.js [--dry-run]`).
- `test-fragments.js`: self-check of the merge. Run `node tools/progress/test-fragments.js`. It uses temporary copies only.

## Tracker fragments: one file per agent, no edit clashes

Several agents may run at the same time. If each one edits `tracker.json` by text, the edits clash. Instead, each agent writes **its own fragment file**:

```
wiki/progress/fragments/<task-id>.json
```

`node tools/progress/build.js` merges all fragments into `tracker.json`, then moves them to `wiki/progress/fragments/archive/<date>/`. After the merge, `tracker.json` is the source of truth again. Commit `tracker.json`, `index.html` and the archived fragment.

### Fragment format

One JSON object. `id` is required. All other keys are optional task fields (the same fields as in `tracker.json`).

```json
{
  "id": "M4-01",
  "milestone": "M4",
  "title": "Causal decoder with look-ahead",
  "status": "done",
  "started_at": "2026-11-13T20:00:00-08:00",
  "finished_at": "2026-11-13T23:10:00-08:00",
  "approx_times": true,
  "notes": "Full notes text (this replaces the old notes).",
  "agent_runs": [
    {"label": "M4-01 GPU training", "duration_s": 11234.5, "tokens": 250000, "tool_uses": 140}
  ],
  "_tracker_updated": "2026-11-13T23:15:00-08:00"
}
```

### Merge rules
| Rule | Detail |
|---|---|
| Fragment wins | Each task field in the fragment replaces the tracker value. Fields not in the fragment stay. `notes` is replaced, not appended: copy the old text if you want to keep it. |
| New task | If `id` is not in the tracker, the fragment must give `milestone` (an existing milestone) and `title`. Defaults: `todo`, no times, no runs, empty notes. The task goes after the last task of its milestone. |
| Agent runs | Run key = `run_key` if set, else `label`. A run with a known key replaces the old run (so a `null` placeholder with the same label gets filled). A new key is appended. Use `run_key` if two runs have the same label. |
| Meta keys | Keys that start with `_` are not task fields. `_tracker_updated` moves the tracker's `updated` time forward (never back). |
| Order | Fragments are applied in file-name order. For several updates to one task, use `<task-id>.json`, `<task-id>.2.json`, ... |
| Idempotent | The same fragment merged twice gives the same file. No fragments = no change. |
| Safe | A bad fragment (bad JSON, unknown status or milestone, run without label) stops the merge with a clear message. Nothing is written and no fragment is moved. |
| Minimal diff | Only the changed task objects (and `updated`) change in the file text. All other lines stay byte for byte. Before it writes, the merge parses the new text and checks that it equals the expected result. |
| Lock | `fragments/.merge.lock` stops two merges at the same time (a lock older than 60 s counts as stale). |

Valid `status` values: `done`, `in_progress`, `todo`, `blocked`, `externally_blocked`.

Set `PROGRESS_NO_MERGE=1` to build the page without a merge.
