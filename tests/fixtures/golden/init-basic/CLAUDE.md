# Brian의 MYELIN Vault — Claude 운영 규칙

<!-- myelin:generated — 이 블록은 `myelin init` / `myelin add-domain` 이 Pack에서 다시 생성한다. 개인 규칙은 아래 personal 블록에. -->

## Vault
- Owner: Brian · A3-AI WG · 언어: ko · 생성: 2026-10-18
- 정본은 이 Vault의 Markdown + YAML. 모든 변경은 Git commit. AI 커밋은 `[myelin:<skill>]` 접두사.
- Frontmatter v2 필수: id · type · created (그 외 status/origin/confidence/classification/share/source/reviewed/tags). 스키마: `90_System/`의 템플릿을 따른다.

## Fail-closed — AI 쓰기 허용 경로 (Level 2 기준; 그 외 경로는 Guard가 차단한다)
- `00_Inbox/ai-drafts/`
- `50_Journal/`
- `_patches/`
- `80_Outputs/drafts/`
- 그 외(특히 `10_Domains/`, `40_IP/`, `90_System/`, `myelin.yaml`)는 **사람 승인 영역**. 변경이 필요하면 `_patches/`에 제안 파일을 만든다 (Level ≥ 2, 형식: ADR-0006).
- Bash 로 파일을 쓰는 우회도 Guard 가 차단한다. `.claude/settings.json` 의 deny 규칙이 2차 방어.
- AI가 만든 노트는 `origin: claude`, `status: draft`로 `00_Inbox/ai-drafts/`에만 생성한다. verified 승격은 사람이 Hub Review Gate에서만 한다.

## Level 2 — link-patch
- 사용 가능 Skill: /ingest · /distill · /interview · /review · /link · /compose
- 0 read-only | 1 drafts | 2 link-patch | 3 scheduled review

## Domains (3+1)
- **D1** AI/ML/AX Platform — primary · `10_Domains/D1/` · Sub-MOC: LLM Engineering, LLMOps/평가, AX 방법론, AI Security, Platform Patterns, 사업화
- **D3** 자율학습 Robotics — research · `10_Domains/D3/` · Sub-MOC: Locomotion(RL/MPC), Sim2Real, VLA, ROS2, HW Platform, Experiment Log
- **D4** Auto Design (SolidWorks) — growth · `10_Domains/D4/` · Sub-MOC: API/Macro, Parametric, Design Rule Engine, 부품 라이브러리, DFM, AI×CAD
- 허용 note type: adr, checklist, evergreen, experiment, idea-ip, lesson, literature
- Domain 추가는 `myelin add-domain <ID>` 로만 (Pack = 데이터).

## 보안등급 · LLM 라우팅
- classification: public | internal | confidential. `confidential` 노트와 `40_IP/`는 외부 LLM에 올리지 않는다.
- `confidential` → local
- `40_IP/**` → local
- share: true 는 Commons 공개 후보 표시일 뿐이며, 공개는 사람이 Hub에서 한다.

## 용어
- `90_System/taxonomy.md` 의 대표 용어로 정규화한다 (/distill).

## Packs
- `myelin.core` v1.0.0 (core) — MYELIN
- `brian.physical-ai` v1.0.0 (reference) — Brian (이원대) · WDLAB

<!-- myelin:personal:start -->

## 개인 규칙

- (여기에 나만의 규칙을 적는다. Pack 재생성 시 보존된다.)

<!-- myelin:personal:end -->
