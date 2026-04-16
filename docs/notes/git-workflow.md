## Daily Commands

The commands you'll use every day:

```bash
# Check what's changed
git status
git diff                    # Unstaged changes
git diff --staged           # Staged changes

# Stage and commit
git add <file>              # Stage specific file
git add -p                  # Stage interactively (by hunk)
git commit -m "message"     # Commit with message

# Sync with remote
git pull origin main        # Pull latest changes
git push -u origin branch   # Push and set upstream
```

## Branching Strategy

### Feature Branch Workflow

```
main ─────●────────●────────●───────
           \      /          \
 feature    ●──●──            \
                         fix   ●──●
```

```bash
# Create and switch to new branch
git checkout -b feature/add-search

# Do your work, commit...
git add .
git commit -m "Add search functionality"

# Push branch
git push -u origin feature/add-search

# After PR is merged, clean up
git checkout main
git pull origin main
git branch -d feature/add-search
```

## Undoing Things

### Undo last commit (keep changes)

```bash
git reset --soft HEAD~1
```

### Unstage a file

```bash
git restore --staged <file>
```

### Discard changes to a file

```bash
git restore <file>
```

### Amend last commit message

```bash
git commit --amend -m "New message"
```

> **Warning**: Never amend or rebase commits that have been pushed to a shared branch.

## Useful Aliases

Add these to your `~/.gitconfig`:

```ini
[alias]
    st = status
    co = checkout
    br = branch
    ci = commit
    lg = log --oneline --graph --decorate -20
    last = log -1 HEAD --stat
    unstage = restore --staged
    undo = reset --soft HEAD~1
```

Then use them:

```bash
git lg      # Pretty log
git st      # Quick status
git undo    # Undo last commit
```

## Interactive Rebase

Clean up your commit history before merging:

```bash
# Rebase last 3 commits
git rebase -i HEAD~3
```

In the editor, you can:
- `pick` — Keep commit as-is
- `squash` — Merge into previous commit
- `reword` — Change commit message
- `drop` — Remove commit

## Stashing

Save work in progress without committing:

```bash
git stash                   # Stash changes
git stash -m "WIP: search"  # Stash with message
git stash list              # List stashes
git stash pop               # Apply and remove latest stash
git stash apply stash@{1}   # Apply specific stash
git stash drop stash@{0}    # Remove specific stash
```

## Cherry Pick

Apply a specific commit to the current branch:

```bash
git cherry-pick <commit-hash>
```

## Viewing History

```bash
# Search commits by message
git log --grep="fix bug"

# Show changes by author
git log --author="name"

# Show file history
git log --follow -p -- path/to/file

# Find when a line was changed
git blame path/to/file

# Search for string in all commits
git log -S "function_name" --oneline
```

## Tips

1. **Commit often, push when ready** — Small, focused commits are easier to review and revert
2. **Write good commit messages** — Explain *why*, not just *what*
3. **Use `.gitignore`** — Keep build artifacts, secrets, and OS files out of the repo
4. **Pull before push** — Avoid unnecessary merge conflicts
5. **Never commit secrets** — Use environment variables or secret managers
