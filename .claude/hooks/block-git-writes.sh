#!/usr/bin/env bash
# PreToolUse hook (Bash/PowerShell): the user alone stages and commits (CLAUDE.md §6).
# Exit 2 blocks the call and shows stderr to the agent; anything else lets it run.

payload=$(tr -d '\r\n')
command=$(printf '%s' "$payload" | grep -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"')

opt='[[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?'
sub='add|rm|mv|commit|push|reset|rebase|merge|cherry-pick|revert|am|stash|restore'
pattern="(^|[^[:alnum:]_.-])git(\.exe)?($opt)*[[:space:]]+($sub)([^[:alnum:]_-]|$)"

if match=$(printf '%s' "$command" | grep -oE "$pattern" | head -n 1) && [ -n "$match" ]; then
  match=${match#"${match%%git*}"}
  echo "Blocked by .claude/hooks/block-git-writes.sh: '$match' changes the index or" \
    "history, which only the user does (CLAUDE.md §6). Leave the change in the working" \
    "tree and report it, with a proposed commit message." >&2
  exit 2
fi
exit 0
