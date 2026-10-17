# plugin/ — MYELIN for Claude Code

**P3** 에서 구현한다. 사양은 `docs/adr/0002-claude-code-plugin-spec.md` 를 따른다.

예정 구조 (Claude Code 표준 레이아웃):

```
plugin/
├── .claude-plugin/plugin.json      # name: "myelin"
├── skills/{ingest,distill,interview,link,compose,review,ip-scan}/SKILL.md
├── hooks/hooks.json                # PreToolUse: Write|Edit|MultiEdit|NotebookEdit → guard
└── scripts/guard_write.py          # 표준 라이브러리만, 모든 예외는 exit 2
```

주의: 플러그인 루트의 `CLAUDE.md` 는 컨텍스트로 로드되지 않는다. 지침은 Skill에 넣는다.
