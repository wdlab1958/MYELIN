# MYELIN for Claude Code (plugin)

Layout follows `docs/adr/0002-plugin-spec.md`:

- `.claude-plugin/plugin.json` — manifest (only `name` is required)
- `skills/<skill>/SKILL.md` — /ingest /distill /interview /link /compose /review /ip-scan (P3)
- `hooks/hooks.json` + `hooks/guard_write.py` — Fail-closed PreToolUse guard (P3; P0 placeholder blocks everything)
- `commands/` — reserved

Local test load: `claude --plugin-dir ./plugin` · validate: `claude plugin validate ./plugin`
