# Branch Protection Rules

After pushing to GitHub, set these rules:
GitHub Repo → Settings → Branches → Add rule → Branch: main

✅ Require a pull request before merging
✅ Require status checks to pass (select: FaMTNarriAI CI)
✅ Require branches to be up to date before merging
✅ Do not allow bypassing the above settings

This ensures:
- No one pushes broken code directly to main
- Every change is reviewed
- All tests pass before merging
