#!/usr/bin/env bash
# Standalone Antigravity GitHub Synchronization Script
# Automatically stages, commits, and pushes agent updates to GitHub.

set -e

REPO_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$REPO_DIR"

CUSTOM_MSG="$1"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ Error: Not a git repository."
    exit 1
fi

# Check remote
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "❌ Error: Git remote 'origin' is not configured."
    exit 1
fi

STATUS_OUTPUT=$(git status --porcelain)

if [ -z "$STATUS_OUTPUT" ]; then
    echo "✓ Repository is already clean. Nothing to commit."
    # Push any unpushed commits if they exist
    CURRENT_BRANCH=$(git branch --show-current)
    if [ -n "$CURRENT_BRANCH" ]; then
        git push origin "$CURRENT_BRANCH" 2>/dev/null || true
    fi
    exit 0
fi

echo "📦 Detected changes to sync with GitHub:"
echo "$STATUS_OUTPUT"

# Stage all files respecting .gitignore
git add -A

if [ -n "$CUSTOM_MSG" ]; then
    COMMIT_MSG="$CUSTOM_MSG"
else
    COMMIT_MSG="feat(agent): update by Antigravity AI Agent [${TIMESTAMP}]"
fi

git commit -m "$COMMIT_MSG"

CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    CURRENT_BRANCH="main"
fi

echo "🚀 Pushing changes to origin/$CURRENT_BRANCH ..."
git push origin "$CURRENT_BRANCH"

COMMIT_HASH=$(git rev-parse --short HEAD)
echo "✅ Successfully synced to GitHub! Commit: $COMMIT_HASH"
