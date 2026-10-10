# Daily Git Workflow — FaMTNarriAI

After setup_github is done, this is how you work every day.

## The 4 commands you use every day

```bash
# 1. Start work — get latest changes from GitHub
git pull

# 2. Make your changes to the code...

# 3. Save your changes to git
git add .
git commit -m "feat: describe what you changed"

# 4. Upload to GitHub
git push
```

## Commit message format

Use this prefix so commits are easy to read:

| Prefix | Use for |
|--------|---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation change |
| `test:` | Adding or fixing tests |
| `refactor:` | Code cleanup (no behaviour change) |
| `style:` | Formatting, no logic change |

**Examples:**
```
feat: add Italian voice support
fix: prevent crash when PDF has no text
docs: update README with Docker instructions
test: add tests for Arabic text cleaning
```

## Feature branch workflow (when adding something new)

```bash
# 1. Create a branch for your feature
git checkout -b feat/add-italian-voices

# 2. Make changes, commit as normal
git add .
git commit -m "feat: add Italian voices Elsa and Diego"

# 3. Push the branch to GitHub
git push -u origin feat/add-italian-voices

# 4. On GitHub: open a Pull Request
#    Your branch → main
#    CI runs automatically
#    When tests pass → merge

# 5. Back to main locally
git checkout main
git pull
```

## Check what changed before committing

```bash
git status          # what files changed?
git diff            # what lines changed?
git log --oneline   # recent commit history
```
