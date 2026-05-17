# Cursor Remote Workflow (Scrap)

## Allowed workflow

```text
Cursor → Remote SSH → hermes → /opt/scrap → edit → commit → push → restart → smoke
```

- All development on **hermes** in `/opt/scrap`
- Git operations only on the remote repo
- Deploy = `git pull` + migrations + service restart + smoke

## Forbidden workflow

- Local temp deploy: `tmp_deploy_*.py`, `deploy*.tar.gz`, `deploy*.zip`
- Local helper scripts committed or run from `F:\Projects\Hivery\scrap`
- Shadow workspace git commits (local copy diverging from hermes)
- SCP tarballs instead of git pull

## Local folder policy

`F:\Projects\Hivery\scrap` (if present) is **backup/archive/reference only** — not an active workspace.

## Recovery procedure

If Cursor creates local tmp artifacts:

1. **Stop** the agent session
2. Verify Cursor window is **Remote SSH** → hermes → `/opt/scrap`
3. Delete local artifacts: `tmp_*.py`, `tmp_*.sh`, `deploy*.tar.gz`
4. On hermes: `git status` (must be clean)
5. Re-run: `python scripts/check_repo_safety.py`
6. Reopen Remote SSH workspace

## Validation commands (on hermes)

```bash
cd /opt/scrap
python scripts/check_repo_safety.py
python scripts/check_git_integrity.py
python scripts/pre_deploy_check.py
curl -s http://127.0.0.1:8800/api/system/workspace
```

## Git hooks (optional)

Examples in `scripts/git-hooks/` — install manually only:

```bash
cp scripts/git-hooks/pre-commit.example .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
