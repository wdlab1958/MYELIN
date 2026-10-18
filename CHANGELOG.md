# Changelog

## v1.1.0 — 2026-10-18
Desktop 세션 라인(보존 브랜치 `main-desktop-p9-2026-10-18`)에만 있던 기능을 이 라인에 이식(P9).
- patches: `under` 제목 구획 append, `## set` 허용 키 제한, 적용 계획(diff·digest·fail-closed 검사), `_patches/applied|rejected/` 이동
- hub: 패치 목록·미리보기(diff) API, digest 검증 Apply(불일치 409), Review 화면 미리보기
- install: `--claude` opt-in(플러그인/MCP 등록), Obsidian 설치 스크립트(`install_obsidian.sh`), 테마 선설치(`init_vault`)
- obsidian: 노트 제목 상태 링·칩(cssclasses), Obsidian 연동 가이드, 사용자 가이드 v1.0 docx/xlsx/png
- hub-web: favicon, React Router v7 flags

## v1.0.0 — 2026-10-18
첫 릴리스. 정본 Rev 2.0 의 P0(Bootstrap) ~ P8(Hardening) 전 Phase 구현. 상세는 `docs/RELEASE_NOTES.md`, Phase 별 보고서는 `docs/reports/P0.md`~`P8.md`, 설계 결정은 `docs/adr/0001`~`0010`.
