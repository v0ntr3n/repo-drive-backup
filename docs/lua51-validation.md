# Lua 5.1 validation

Open Actions → Lua 5.1 Validation → Run workflow on main. Select the private source ref.

Before running, create a fine-grained GitHub personal access token restricted to v0ntr3n/lua_scripts with Contents: Read-only. Save it in the runner repository's Actions secrets as LUA_SCRIPTS_READ_TOKEN.

Push-triggered CI tests synthetic fixtures only. Manual dispatch on main additionally fetches private source onto an ephemeral runner and parses every .lua file using luac5.1 -p. No private scripts are executed, committed, cached or uploaded as artifacts. Only aggregate results are printed by default. To intentionally publish failed relative filenames and line numbers (never compiler messages or source snippets), enable show_failed_paths on manual dispatch. Example: `gh workflow run lua51-validation.yml --repo v0ntr3n/repo-drive-backup -f target_ref=main -f show_failed_paths=true`. Public logs are visible to anyone. Review workflow changes and restrict write access to trusted maintainers. The private checkout is removed at job end.

Syntax validation is not runtime or Cocos2d integration testing. Run local compiler checks in the private repo for detailed diagnostics.
