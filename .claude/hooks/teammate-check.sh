#!/usr/bin/env bash
# SessionStart hook — two people work on this repo, so before anyone starts:
# fetch, then report what the other developer pushed, what is unpushed locally,
# and whether the working tree is dirty.
#
# Silent when there is nothing to say. Never blocks a session: every failure path
# exits 0, because a missing network or a detached HEAD is not a reason to refuse
# to start work.
set -u

cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Fetch quietly; offline is fine, we just report on stale refs.
git fetch --quiet 2>/dev/null || true

# No upstream (detached HEAD, fresh branch) means nothing to compare against.
git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1 || exit 0

behind=$(git rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)
ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
dirty=$(git status --porcelain 2>/dev/null | grep -c . || true)
[ -z "$dirty" ] && dirty=0

[ "$behind" -eq 0 ] && [ "$ahead" -eq 0 ] && [ "$dirty" -eq 0 ] && exit 0

incoming=$(git log --no-decorate --format='  %h %an: %s' 'HEAD..@{u}' 2>/dev/null | head -20)
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)

summary=""
[ "$behind" -gt 0 ] && summary="${summary}${behind} new commit(s) on ${upstream} — pull before starting:
${incoming}
"
[ "$ahead" -gt 0 ] && summary="${summary}${ahead} local commit(s) on ${branch} not pushed yet.
"
[ "$dirty" -gt 0 ] && summary="${summary}${dirty} uncommitted file(s) in the working tree.
"

if command -v node >/dev/null 2>&1; then
  SUMMARY="$summary" BEHIND="$behind" node -e '
    const s = process.env.SUMMARY.trimEnd();
    const behind = Number(process.env.BEHIND);
    const advice = behind
      ? "\nAnother developer has pushed. Pull and rebase before editing, and re-read any file you are about to change — it may have moved."
      : "";
    process.stdout.write(JSON.stringify({
      systemMessage: s,
      hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: "Shared-repo status at session start:\n" + s + advice,
      },
    }));
  '
else
  # No node: plain text still reaches the transcript.
  printf '%s\n' "$summary"
fi
exit 0
