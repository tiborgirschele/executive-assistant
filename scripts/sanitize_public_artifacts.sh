#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not inside a git repository." >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
  echo "Could not determine current branch." >&2
  exit 1
fi

ignore_entries=(
  "daemon-gogcli-config/"
  "briefing_cron.log"
  "config/*.bak.*"
  "ea/app/*.bak.*"
)

for entry in "${ignore_entries[@]}"; do
  if ! grep -Fxq "$entry" .gitignore; then
    echo "$entry" >> .gitignore
    echo "Added to .gitignore: $entry"
  fi
done

tracked_matches=(
  "daemon-gogcli-config/keyring/*"
  "briefing_cron.log"
  "config/*.bak.*"
  "ea/app/*.bak.*"
)

removed_any=0
for pattern in "${tracked_matches[@]}"; do
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    git rm --cached -- "$path"
    removed_any=1
  done < <(git ls-files -- "$pattern")
done

if ! git diff --cached --quiet || ! git diff --quiet .gitignore; then
  git add .gitignore
  git commit -m "chore: untrack sensitive artifacts and ignore them"
else
  echo "No changes to commit."
fi

if git remote get-url origin >/dev/null 2>&1; then
  if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    git push
  else
    git push -u origin "$branch"
  fi
else
  echo "No 'origin' remote configured; skipping push."
fi

if [[ "$removed_any" -eq 1 ]]; then
  echo "Finished: sensitive artifacts were untracked, committed, and push was attempted."
else
  echo "Finished: no tracked sensitive artifacts matched the configured patterns."
fi
