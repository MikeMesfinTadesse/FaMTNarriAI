@echo off
title FaMTNarriAI — GitHub Setup
color 0D

echo.
echo ══════════════════════════════════════════════
echo   FaMTNarriAI — GitHub Setup
echo ══════════════════════════════════════════════
echo.

:: Check git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] git not found.
    echo Download from: https://git-scm.com/download/win
    pause & exit /b 1
)
echo [OK] git found

:: Configure identity
echo.
echo -- Configure your identity --
set /p GIT_NAME="Your name for commits: "
set /p GIT_EMAIL="Your GitHub email: "
git config --global user.name "%GIT_NAME%"
git config --global user.email "%GIT_EMAIL%"
git config --global init.defaultBranch main
echo [OK] Identity set

:: Init repo
echo.
echo -- Initialize repository --
if exist ".git" (
    echo [INFO] Already a git repo
) else (
    git init
    echo [OK] Git repo initialized
)

:: First commit
echo.
echo -- First commit --
git add .
git commit -m "feat: initial FaMTNarriAI Audiobook Studio"
echo [OK] First commit created

:: Connect to GitHub
echo.
echo -- Connect to GitHub --
echo.
echo Before continuing:
echo   1. Go to https://github.com/new
echo   2. Name: FaMTNarriAI
echo   3. Do NOT add README or .gitignore
echo   4. Click Create repository
echo   5. Copy the URL shown
echo.
set /p REPO_URL="Paste your GitHub repository URL: "
git remote remove origin 2>nul
git remote add origin %REPO_URL%
echo [OK] Remote set

:: Push
echo.
echo -- Pushing to GitHub --
git branch -M main
git push -u origin main

echo.
echo ══════════════════════════════════════════════
echo   Done! Your code is on GitHub.
echo.
echo   Next: Go to your repo - Actions tab
echo   You will see CI tests running automatically
echo ══════════════════════════════════════════════
echo.
pause
