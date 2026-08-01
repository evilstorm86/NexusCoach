# Working on NexusCoach

**Two developers share this repo.** Someone else may have changed the file you are about
to edit, since your last session or since ten minutes ago.

## Before starting work

A `SessionStart` hook (`.claude/hooks/teammate-check.sh`) fetches and reports incoming
commits, unpushed local commits, and a dirty tree. It is silent when there is nothing to
say — so silence means you are in sync.

When it reports incoming commits:

1. `git pull --rebase` before editing anything.
2. **Re-read the files you are about to change.** A file you remember from an earlier
   session may have moved, been renamed, or already contain the fix you were about to
   write.
3. If you were mid-task, check whether the other developer already did it.

## Before committing

- `git pull --rebase` again — the other developer may have pushed while you worked.
- Run the checks that cover what you touched:
  - `api/` → `pytest` (from `api/`, with `DATABASE_URL` unset so it uses the test SQLite file)
  - `web/` → `npx eslint .` and `npm run build`
- Commit and push promptly. Long-lived local work is what turns into conflicts.

## Never

- **Force-push `main`.** It rewrites the other developer's history.
- Commit `.env`, `api/dev.db`, or anything else in `.gitignore`.
- Leave the working tree dirty at the end of a session without saying so — the hook will
  report it to whoever opens the repo next, including you tomorrow.

## Conventions

- Deployment and operations: [docs/DEPLOY.md](docs/DEPLOY.md).
- Architecture, endpoint tables, and the reasoning behind the design choices: [README](README.md).
- Deliberate simplifications are marked with a `ponytail:` comment naming the ceiling and
  the upgrade path. Read one before "fixing" it.
- The API is verified against SQLite only; Postgres and Docker are unexercised. Don't
  claim a change works in production without saying which of those you actually ran.
