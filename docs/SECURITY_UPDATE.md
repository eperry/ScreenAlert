# ScreenAlert - Config File Security Update

## What was done:

1. **Added config files to .gitignore:**
   - `screenalert_config.json`
   - `windowalert_config.json`

2. **Removed config files from entire git history:**
   - Used `git filter-branch` to remove all config files from all commits
   - Ran aggressive garbage collection to completely purge the files
   - Config files contained sensitive information like window handles and user-specific data

## Important: Remote Repository Update

⚠️ **WARNING**: The git history has been rewritten to remove sensitive config files.

If you have already pushed this repository to GitHub, you will need to force-push to update the remote:

```bash
git push --force-with-lease origin main
git push --force-with-lease origin --all
git push --force-with-lease origin --tags
```

**Note**: This will rewrite the remote git history. Anyone else who has cloned this repository will need to re-clone it.

## Files Removed from History:
- `config.json`
- `screenalert_config.json` 
- `windowalert_config.json`
- `archive old versions/screenalert_config.json`

## Privacy Protection:
The config files contained:
- Window handles (HWND values)
- Specific window titles (including game references)
- User-specific system configuration
- Monitor and screen resolution data

These have been completely removed from all git commits to protect user privacy.

## Current Status:
✅ Config files are now in .gitignore
✅ Config files removed from all git history
✅ Local config file still exists for your use
✅ Aggressive garbage collection completed
