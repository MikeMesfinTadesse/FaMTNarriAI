#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# scripts/setup_github.sh
#
# Run this ONCE to push FaMTNarriAI to GitHub for the first time.
# After this, normal workflow is:  git add → git commit → git push
#
# USAGE:
#   chmod +x scripts/setup_github.sh
#   ./scripts/setup_github.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Stop immediately on any error

echo ""
echo "══════════════════════════════════════════════"
echo "  FaMTNarriAI — GitHub Setup"
echo "══════════════════════════════════════════════"
echo ""

# ── Step 1: Check git is installed ──────────────────────────────
if ! command -v git &>/dev/null; then
    echo "❌  git not found."
    echo "    Windows: https://git-scm.com/download/win"
    echo "    macOS:   brew install git"
    echo "    Linux:   sudo apt install git"
    exit 1
fi
echo "✅  git $(git --version | awk '{print $3}') found"

# ── Step 2: Configure git identity ──────────────────────────────
echo ""
echo "── Configure your identity ───────────────────"
read -p "Your name (for git commits): " GIT_NAME
read -p "Your GitHub email: " GIT_EMAIL
git config --global user.name  "$GIT_NAME"
git config --global user.email "$GIT_EMAIL"
git config --global init.defaultBranch main
echo "✅  Identity set: $GIT_NAME <$GIT_EMAIL>"

# ── Step 3: Initialize repo ──────────────────────────────────────
echo ""
echo "── Initialize repository ─────────────────────"
if [ -d ".git" ]; then
    echo "ℹ️   Already a git repo — skipping init"
else
    git init
    echo "✅  Git repo initialized"
fi

# ── Step 4: First commit ─────────────────────────────────────────
echo ""
echo "── First commit ──────────────────────────────"
git add .
git status --short
git commit -m "feat: initial FaMTNarriAI Audiobook Studio

Phase 1 — Version Control & Infrastructure:
- Desktop GUI app (customtkinter) with 8 tabs
- Edge-TTS neural voices, 50+ languages
- PDF chapter detection, text cleaning
- Translation via deep-translator (no API key)
- Dockerfile with multi-stage build
- GitHub Actions CI (test.yml + docker.yml)
- Full test suite (pytest)
- Architecture, roadmap, changelog docs"

echo "✅  First commit created"

# ── Step 5: Connect to GitHub ────────────────────────────────────
echo ""
echo "── Connect to GitHub ─────────────────────────"
echo ""
echo "Before continuing:"
echo "  1. Go to https://github.com/new"
echo "  2. Repository name: FaMTNarriAI"
echo "  3. Set to Public or Private"
echo "  4. Do NOT check 'Add README' or 'Add .gitignore'"
echo "  5. Click 'Create repository'"
echo "  6. Copy the URL (e.g. https://github.com/YourName/FaMTNarriAI.git)"
echo ""
read -p "Paste your GitHub repository URL: " REPO_URL

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
echo "✅  Remote set to: $REPO_URL"

# ── Step 6: Push ─────────────────────────────────────────────────
echo ""
echo "── Push to GitHub ────────────────────────────"
git branch -M main
git push -u origin main

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅  Done! Your code is now on GitHub."
echo ""
echo "  Next steps:"
echo "  1. Go to your repo → Actions tab"
echo "     Watch the CI tests run automatically ✓"
echo ""
echo "  2. Set branch protection:"
echo "     Repo → Settings → Branches"
echo "     See .github/BRANCH_PROTECTION.md for exact settings"
echo ""
echo "  3. For Docker Hub auto-build:"
echo "     Repo → Settings → Secrets → Actions"
echo "     Add: DOCKER_USERNAME and DOCKER_PASSWORD"
echo "══════════════════════════════════════════════"
echo ""
