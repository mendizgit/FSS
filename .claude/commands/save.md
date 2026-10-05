---
description: Update agent-kit/MEMORY.md with minimal edits
---
Update `agent-kit/MEMORY.md` with **targeted edits only**. Do not rewrite the file.

- Header line: `updated`, `commit` (`git rev-parse --short HEAD`), `phase`, `status`.
- `Next step`: one line that a fresh session can execute without chat history.
- Change only the feature codes whose status changed.
- `Log`: add one line at the top. If there are more than 10 lines, delete the oldest.
- Add a line to `Decisions`, `Code map` or `Env` only if something new happened.
- Facts only. No secrets. Keep the file ≤ 150 lines.

Reply with only: `Saved — Next: <next step>`. $ARGUMENTS
