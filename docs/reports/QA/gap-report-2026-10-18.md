> **보존 사본.** 이 Gap 분석은 QA 캠페인 시작 시점(HEAD `53e2e5a`)의 코드를 기준으로 작성되었다. 이후 같은 날 수정된 항목: H1·H2(Guard, plugin 1.0.1), M2(CLI git commit), M3(T02 재분류), M4(KPI 판정), M5(CI e2e), M6(403 테스트), M8(가드레일 정적 검사), L1~L3(문서). 이월 항목(H3·H4·M1·M9)은 `PHASE_STATE.md` Backlog 에 기록. 종합은 `docs/reports/QA-2026-10-18.md`.

# MYELIN GAP TEST — 정본(Rev 2.0) 대 구현 비교 보고서

- 일자: 2026-10-18 · 대상 정본: `docs/spec/MYELIN_Rev2.0.md` (WDLAB-MYELIN-SPEC Rev 2.0) · 대상 코드: 작업 트리 HEAD `53e2e5a` (+ 미커밋 변경 4건)
- 방법: 정본의 규범 문장(MUST/"한다"/표·Gate 기준)을 항목화하고, 각 항목을 소스·테스트를 직접 열어 확인했다. Guard 는 fixture Vault(`tests/fixtures/vaults/basic`, level 2)에 대해 hook 스크립트를 실제로 실행해 판정했다. Claude Code hooks/plugin 스키마는 공식 문서(code.claude.com/docs, 2026-10-18)로 재확인했다.
- 검증 환경: `uv run pytest -q` → **421 passed, 1 skipped**(perf 는 `MYELIN_PERF=1` 전용). `scripts/emboss.py check|a11y|lint` 모두 통과. Claude Code 2.1.302.
- 상태 정의: **IMPLEMENTED**(근거 파일:행) / **PARTIAL**(무엇이 빠졌는지) / **MISSING** / **DEVIATES**(정당화 ADR 유무) / **UNTESTED**(구현은 있으나 검증 없음).

> **주의 — 감사 중 작업 트리 변경.** 본 보고서의 분석은 HEAD `53e2e5a` + 당시 미커밋 4건(`index.css`, `Settings.tsx`, `hub.spec.ts`, 가이드 docx) 기준이다. 보고서 작성 중 외부에서 14개 파일(특히 `plugin/hooks/guard_bash.py` +433/-, `guard_common.py`, `guard_write.py`, Hub api/web 다수)이 추가로 수정되었다. 수정된 Guard 를 같은 fixture 로 **재실측**한 결과를 §4 끝에 "재검증" 으로 덧붙였다: `curl -o`·`wget -O`·`find -delete`·`git apply/read-tree`·`awk >`·`patch`·`xargs`·`python3 -` 는 이제 차단(rc=2)되고, **`bash|sh|python3 <ai-drafts 안의 스크립트>` 실행과 `Write …/x.sh`, `Write _patches/applied/…` 는 여전히 허용**된다(H1 의 잔여 범위·H2 는 그대로 유효). 숨김 디렉터리 쓰기는 차단으로 바뀌었다. 변경 중인 Hub 코드는 재검토하지 않았다.

---

## 1. 요약 수치

| 구분 | 개수 |
|---|---|
| 총 요구사항 행 | 200 |
| IMPLEMENTED | 143 |
| PARTIAL | 29 |
| MISSING | 5 |
| DEVIATES | 20 |
| UNTESTED | 3 |

심각도별 발견: **상 4건 · 중 9건 · 하 22건** (§2 참조).

한 줄 결론: 정본의 구조·스키마·Hub·MCP·Commons·디자인 시스템은 충실히 구현되어 있고 세 경로(Guard·MCP·Hub)의 "AI 는 초안만, 승격은 사람만" 원칙은 장치로 강제된다. 그러나 **Bash Guard 는 정본 §3·§7.2·P3 Gate 가 요구하는 "허용 외 쓰기 차단 100%" 를 만족하지 못한다** — 스크립트 파일 실행, `curl -o`, `find -delete`, `git apply` 등 12개 경로가 실측에서 통과(rc=0)했고, 2차 방어(settings.json ask)도 python/node 만 덮는다. 이 한 가지가 "상" 의 핵심이며, 나머지는 부분 구현(LLM 라우팅·재사용 지표·Hub PR)과 문서 불일치이다.

---

## 2. 심각도별 목록

### 2.1 상 — 기능 누락 · 정본 위반

| # | 발견 | 근거 | 권고(1줄) |
|---|---|---|---|
| H1 | **Bash Guard 우회 12종이 실측 통과.** `bash\|sh\|python3\|perl\|ruby\|node <ai-drafts의 스크립트>`, `python3 -`, `curl -o 10_Domains/…`, `wget -O …`, `find 10_Domains -delete`, `awk '{print > "10_Domains/…"}'`, `patch -p0 <…`, `xargs rm`, `git apply\|am\|read-tree\|checkout-index\|update-index` 가 모두 exit 0. 정본 §3 "Fail-closed = 장치", §7.2 "Bash 우회는 settings.json deny 로 함께 제한", P3 Gate "허용 외 쓰기 차단 100%" 위반. settings.json 의 `ask` 는 `python*`/`uv run python`/`node` 만(`settings_template.py:337-343`) — bash/sh/perl/ruby/curl/wget/find/patch/git apply 는 묻지도 않는다. | `plugin/hooks/guard_bash.py:276-324,375-387` (WRITERS·INLINE_INTERPRETERS·GIT_BLOCKED 블록리스트), 실측 로그(본 보고서 §4) | *(재검증: 수정 중인 guard_bash.py 는 12종 중 9종을 이미 차단; 잔여 = 스크립트 파일 실행 3종)* `guard_bash.py`: ① 인터프리터(bash/sh/zsh/python*/node/perl/ruby/`uv run python`)는 `-c` 유무와 무관하게 Vault 내부 경로나 `-` 인자를 받으면 차단, ② WRITERS 에 `curl/wget(-o/-O/--output)·patch·xargs·find(-delete/-exec)·awk/gawk` 추가(판단 불가 → 차단), ③ GIT_BLOCKED 에 `apply am cherry-pick revert read-tree checkout-index update-index write-tree`; `settings_template.py` ask 에 `Bash(bash *) Bash(sh *) Bash(perl *) Bash(ruby *) Bash(curl *) Bash(wget *)`; `tests/plugin/test_guard_bash.py` 에 위 12 케이스를 차단 표로 고정. |
| H2 | **guard_write 가 AI 허용 디렉터리에 비-Markdown 파일과 `_patches/applied\|rejected/` 쓰기를 허용.** `Write 00_Inbox/ai-drafts/x.sh` rc=0, `Write _patches/applied/fake.patch.md` rc=0, `Write 00_Inbox/ai-drafts/.hidden/x.md` rc=0. 전자는 H1 의 발판(스크립트를 만든 뒤 실행), 후자는 Hub 가 이력으로 보여 주는 적용·거부 패치의 위조 경로(`patches.py:349-365 list_patches`). | `plugin/hooks/guard_common.py:228-240 check_allowed`, 실측 | `check_allowed` 에 확장자 allowlist(`.md`; `_patches/` 는 직속 `*.patch.md` 만)와 `_patches/applied|rejected/`·숨김 디렉터리 거부를 추가하고 `test_guard_write.py` 에 3 케이스 추가. |
| H3 | **LLM 라우팅 미구현(설정만).** §4.1 L3 "Local LLM 라우팅", §5.3 `llm.route: {confidential: local, "40_IP/**": local}`, §7.1 /ip-scan "로컬 LLM 라우팅", §12 "기밀 유출 → LLM 라우팅". 코드는 `llm` 블록을 파싱해 CLAUDE.md 에 문장으로 출력할 뿐(`render.py:144`) 어디서도 라우팅하지 않는다. Level 3 에서 외부 Claude 세션이 `/ip-scan` 으로 `40_IP/candidates` 에 쓰는 것을 Guard 는 허용한다(`LEVEL_ALLOW[3]`); SKILL.md 의 "로컬 세션이 아니면 멈춘다"(`ip-scan/SKILL.md:14`)는 소프트 규칙이다. | `config.py:96-102`, `render.py:144,171`, `levels.py:254`, `plugin/skills/ip-scan/SKILL.md:14` | 단기: Guard 가 `40_IP/**` 쓰기를 `MYELIN_LLM=local`(또는 myelin.yaml `llm.default: local`) 일 때만 허용하도록 `check_allowed` 에 라우팅 조건 추가; 장기: ADR 로 "라우팅 = 세션 환경변수 + MCP `expose_confidential`" 해석을 확정하고 정본 Rev 2.1 에 반영. |
| H4 | **§11.2 "재사용" 지표 누락.** "Commons 노트가 타인 노트에 인용된 횟수 ≥ 50/월" 을 계산하는 코드가 없다(`metrics.py` ALLOWED_KEYS 에도 없음). | `packages/myelin-core/src/myelin_core/metrics.py:386-398,494-524` | `aggregate(commons)` 에 `notes/**/*.md` 의 `published_from` id 를 각 소유자 페이로드의 `cited_commons_ids`(익명 id 목록) 와 교차 집계하는 `reuse` 열을 추가하고 `test_metrics.py` 에 고정. |

### 2.2 중 — 부분 구현 · 테스트 없음

| # | 발견 | 근거 | 권고(1줄) |
|---|---|---|---|
| M1 | **Hub "Commons 제안" 이 PR 까지 가지 않는다.** §9.1 "Hub 에서 Commons 제안 → Commons Git 에 PR". Hub 는 `publish/<id>` 브랜치 커밋만 만들고 `push` 는 항상 false(UI 가 보내지 않음), PR 은 CLI `--push --pr`+`gh` 에서만. | `Review.tsx:374`, `app.py:257-260`, `commons.py:380-392` | Review 화면 Commons 행에 "push + PR" 체크박스(기본 off)를 두고 `{confirmed:true, push:true, pr:true}` 를 보내도록 `PublishBody` 에 `pr` 추가; 미push 시 다음 명령을 토스트로 안내. |
| M2 | **CLI `myelin init`/`add-domain` 은 git 을 만들지도 커밋하지도 않는다.** §3 "모든 변경은 Git commit", §4.1 L2 "Vault + Git". Hub 온보딩만 `ensure_git` 으로 `[myelin:init]` 커밋. | `scaffold.py:160-184` (git 호출 없음), `service.py:121-142` | `init_vault` 뒤에 `--git/--no-git`(기본 on) 으로 `git init -b main` + `[myelin:init] vault created` 커밋을 수행하도록 `app.py init` 보강(Hub 의 `ensure_git` 로직을 core 로 이동해 공유). |
| M3 | **위협 모델 T02 등급이 자체 정의와 어긋나 P8 Gate "High 0" 이 형식적으로만 통과.** 문서의 High 정의 = "사람 승인 없이 Vault 를 바꿀 수 있음"; H1 은 정확히 그 경우인데 T02 는 Medium·"완화" 로 기록. | `docs/security/threat-model.md` T02 행, `scripts/gate.py:58-62 _threat_model_high_zero` | H1/H2 조치 후 T02 를 High→조치 로 재분류하고 회귀 테스트 이름을 표에 기입; 그 전까지는 RELEASE_NOTES 알려진 제약에 12개 우회 경로를 명시. |
| M4 | **AI 승격률 상한 경보 없음.** §11.1 "40~70% (과도하게 높으면 검토 부실 신호)", §12 "승격률 상한 경보". Dashboard 는 값·목표 문자열만 표시; `/review` SKILL 의 문장 지시만 있음. | `Dashboard.tsx:185-194`, `plugin/skills/review/SKILL.md:14` | `Stats.kpi_rows()` 에 `ok: bool` 판정(목표 파싱)을 추가하고 Dashboard KPI 행에서 이탈 시 `mx-badge--blocked` 라벨("검토 부실 신호")을 표시; `test_stats.py` 에 경계값 테스트. |
| M5 | **Playwright e2e 가 CI 에서 돌지 않는다.** P6 Gate 의 핵심(온보딩→승격, 클릭 없는 쓰기 0)이 로컬 전용. CI 는 `make gate P=<current>`(=P9) 만 실행하고 P9 Gate 에 e2e 가 없다. | `.github/workflows/ci.yml:144-172`, `scripts/gate.py:507-571` | CI gate job 에 `npx playwright install chromium --with-deps` 후 `make e2e` 스텝 추가(또는 P9 Gate 에 e2e 체크 추가). Backlog 항목을 실행으로. |
| M6 | **Hub 쓰기 403 감사 테스트가 `/api/patches/{name}/reject` 를 빠뜨림**(코드는 헤더를 요구함). `commons/publish` 는 `test_api.py:334` 에서 별도 확인됨. | `app.py:241`, `test_api.py:81-90` | `test_writes_require_user_click` 에 `client.post("/api/patches/x.patch.md/reject").status_code == 403` 한 줄 추가. |
| M7 | **P7·P8 사람 참여 Gate 미완(파일럿 5명·피드백 리포트·KIPRIS).** 정본 §1.2 "Gate 통과 + 사람 승인 후에만 다음 Phase" 이지만 P8 과 v1.0.0 태그가 P7 Gate 통과 전에 이루어졌다(Brian 승인은 PHASE_STATE 에 기록). | `PHASE_STATE.md`, `docs/reports/P7.md`, `docs/reports/P8/naming-check.md` | 운영 항목 — `scripts/pilot.py record` 5건 + `pilot-feedback.md` TBD 제거 → `make gate P=7` → `phase-P7` 태그; KIPRIS 결과 기입. 코드 수정 없음. |
| M8 | **Hub 상태 표시 접근성 규칙(가드레일 4 "칩에 항상 텍스트 라벨", §8.3 "Primary Button 화면당 1개")이 Hub 에 대해 테스트되지 않음.** 갤러리만 `test_gallery_uses_only_tokens_and_labels_states` 로 검사. 수동 확인 결과 페이지별 `.mx-btn-primary` 는 0~1개로 규칙 준수. | `tests/test_emboss.py`, `pages/*.tsx` | `test_emboss.py` 에 TSX 정적 검사 추가: 파일당 `mx-btn-primary` ≤ 1, `mx-chip`/`mx-badge--blocked` 요소는 텍스트 자식 필수. |
| M9 | **`commons.remote` 설정이 코드에서 쓰이지 않는다.** §5.3 예시 필드. publish 는 로컬 clone 의 `origin` 으로만 push. | `config.py:105-115`, `commons.py:383` | `publish_note(push=True)` 에서 clone 에 `origin` 이 없으면 `commons.remote` 로 추가하고, `myelin commons init` 이 `remote` 를 origin 으로 설정하도록 보강. |

### 2.3 하 — 문서 불일치 · 경미한 편차

| # | 발견 | 근거 | 권고(1줄) |
|---|---|---|---|
| L1 | README·plugin/README 가 "Claude Code 2.1.275+" 를 요구하지만 hooks.json 의 `onFailure: block` 은 공식 문서상 **2.1.295+** 에서만 동작(그 이하에서는 hook 자체 오류가 차단으로 전환되지 않음). | `README.md:51`, `plugin/README.md:463`, `plugin/hooks/hooks.json:21` | 두 README 의 최소 버전을 2.1.295+ 로 수정. |
| L2 | README "make check (406 tests)" vs 실제 421 passed. | `README.md:98` | 숫자 갱신(또는 수치 삭제). |
| L3 | README §1·RELEASE_NOTES 의 Bash Guard 서술이 과대: "판단 불가 = 차단", 제약은 "python x.py 등은 ask" 로만 적혀 있으나 curl/find/git apply/bash 스크립트는 ask 조차 없다. | `README.md:15,152`, `docs/RELEASE_NOTES.md` 알려진 제약 | H1 조치 전까지 알려진 제약에 우회 경로를 명시; 조치 후 문구 갱신. |
| L4 | ADR-0003 §1 "Pack 필드 추가 없음" 이지만 `Pack` 모델은 `description`, pack-level `templates`, `taxonomy_seed` 를 추가(Core Pack 용). | `docs/adr/0003-*.md`, `schema/pack.py:347-357` | ADR-0003 에 세 필드 추가 결정을 보강 기록. |
| L5 | ADR-0009 D2 "쓰기 동작 6종" 이지만 실제 쓰기 엔드포인트는 8종(+`commons/publish`, `packs/{name}` PUT). | `docs/adr/0009-*.md`, `app.py:221-264` | ADR-0009 표를 8종으로 갱신(ADR-0010 교차 참조). |
| L6 | §8.4 Token CSS 변수명(`--surface`, `--violet`, `--lime`, `--sh-l`…) 대비 구현은 `--mx-*` 접두(`--mx-violet-600`, `--mx-neon-lime`). ADR-0008 은 값 조정만 기록하고 이름 편차는 기록하지 않음. | `scripts/emboss.py:63-72 flat_vars`, `docs/adr/0008-*.md` | ADR-0008 에 네이밍 결정(충돌 방지용 `--mx-` 접두)을 한 줄 추가하고 Rev 2.1 제안에 포함. |
| L7 | 정본 자체 불일치: §3 "AI 쓰기 = ai-drafts 및 _patches 만" vs §7.2 ALLOW 4경로 vs §7.1 Skill 범위(40_IP/candidates 포함). 구현은 ADR-0005(Level 누적)로 §7.1 을 따름. | `docs/adr/0005-*.md`, `levels.py:250-255` | 정본 Rev 2.1 제안서에 §3/§7.2 문구를 Level 누적 표로 통일(Backlog 에 이미 있음). |
| L8 | Skill 호출명이 정본의 `/ingest` 가 아니라 `/myelin:ingest`(플러그인 네임스페이스). 가이드에는 반영됨. | `plugin/README.md`, `docs/guides/user-guide.md` | Rev 2.1 에서 호출명 표기 갱신. |
| L9 | §10.1 `tests/e2e/` 가 비어 있고 Playwright e2e 는 `packages/myelin-hub/web/e2e/` 에 있다. | `tests/e2e/__init__.py` | `tests/e2e/README.md` 한 줄로 위치 안내 또는 디렉터리 제거. |
| L10 | 작업 트리에 미커밋 변경 4건(`web/src/index.css`, `pages/Settings.tsx`, `e2e/hub.spec.ts`, 사용자 가이드 docx). 프로토콜 "Task 완료마다 commit" 위반 상태. | `git status --short` | 검토 후 `P9: fix(hub): settings grid layout` 등으로 커밋(또는 되돌리기). |
| L11 | `stats.orphan_ratio` 와 `doctor orphan` 의 정의가 다름(stats 는 Inbox/Archive/MOC 도 고아로 셈). 대시보드 고아 비율이 doctor 경고 수와 어긋날 수 있다. | `stats.py:667`, `index.py:526`, `doctor.py:569` | 두 쪽 모두 doctor 정의(Inbox·Archive·MOC 제외)로 통일하고 `test_index_stats_match_full_scan` 유지. |
| L12 | theme `manifest.json` version 0.1.0 vs tokens/plugin 1.0.0. | `theme/obsidian-myelin-emboss/manifest.json:3` | `emboss.py build` 가 tokens version 을 manifest 에 쓰도록 생성 대상에 포함. |
| L13 | §9.3 60분 워크숍 자료가 11줄 개요 수준. | `docs/guides/workshop-60min.md` | 세션별 실습 지시·체크포인트 추가(파일럿 전). |
| L14 | §11.2 "Commons 공개 수" 가 로컬 `publish` 이벤트 수(브랜치 생성)이며 merge 여부를 반영하지 않음. | `metrics.py:450` | `aggregate` 에서 Commons `notes/**` 파일 수를 월별로 세어 "merged" 열 추가. |
| L15 | P8-T3 "uv tool install" → 실제는 `uv --directory <repo> run` 런처. PHASE_STATE 결정에만 기록, ADR 없음. | `scripts/install.sh:234-247` | ADR-0011(설치 방식) 또는 ADR-0001 보강. |
| L16 | §8.2 "ai-draft 카드 Cyan glow" — Hub 는 Cyan 칩만 쓰고 `.mx-glow--ai` 를 사용하지 않음(갤러리에만). | `Review.tsx:325`, `emboss.py .mx-glow--ai` | Review 초안 행 또는 Dashboard 대기 타일에 `mx-glow--ai` 적용. |
| L17 | §8.3 "Domain Orb 클릭 시 MOC 이동" — Orb 클릭은 상세 패널 선택, MOC 열기는 별도 버튼. | `Domains.tsx:231,241` | 의도된 UX 면 components.md 에 기록; 아니면 Orb 더블클릭/보조 링크로 MOC 열기. |
| L18 | §5.6 Org Starter Pack 6종 중 2종만 존재(cloud-security·privacy·ai-engineering·dev 없음). P7 산출물 "Org Pack 2종 확정" 과는 일치. | `packs/` | Wave 1 전 챔피언과 함께 4종 초안 추가(Pack = 데이터, 코드 변경 없음). |
| L19 | §4.1 L1 Capture(Web Clipper·음성 메모·Claude 대화 Export)는 `00_Inbox/clips` 폴더만 존재. | `vault.py:188` | 범위 밖임을 Rev 2.1/README 에 명시하거나 Clipper 템플릿 가이드 추가. |
| L20 | §4.3 Offline 모드(로컬 LLM 전용)에 대한 구현·가이드가 없다(`llm.default: local` 은 파싱만). | `config.py:100-102` | H3 과 함께 ADR 로 범위 확정; 가이드에 "v1 미지원" 명시. |
| L21 | §9.1 Pack 진화 제안은 CLI(`pack-propose`)만, Hub Domain Packs 화면에 버튼 없음. | `Packs.tsx`, `app.py:522-542` | Packs 화면 개인 Pack 카드에 "Org Pack 으로 제안"(클릭 헤더 + 확인) 추가. |
| L22 | `docs/guides/mcp-setup.md` 의 버전 문자열 `0.1.0a0` 은 실제와 일치하지만 plugin/tokens 1.0.0 과 패키지 버전 체계가 어긋남. | `packages/myelin-mcp/src/myelin_mcp/__init__.py` | 릴리스 시 패키지 `__version__` 을 1.1.0 으로 통일. |

---

## 3. 전체 표

범례 — 상태: IMPLEMENTED / PARTIAL / MISSING / DEVIATES / UNTESTED. "근거" 의 경로는 저장소 루트 기준. 테스트 열은 해당 요구를 고정하는 테스트(없으면 `-`).

### 3.1 §1~§3 설계 결정·원칙

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R001 | §1.2 | Vault 개인 소유; 공유는 opt-in, verified·보안등급 통과 노트만 | IMPLEMENTED | `commons.py:255-282 check_publishable`, `frontmatter.py:145 is_publishable` | `test_commons.py::test_publish_blocks_confidential_and_share_false_100_percent` |
| R002 | §1.2/§3 | Domain 은 데이터(YAML Pack), 추가에 코드 변경 없음 | IMPLEMENTED | `packs/*/pack.yaml`, `packs/loader.py`, 온보딩 개인 Pack `service.py:687-728` | `test_loader.py`, `test_api.py::test_onboarding_with_custom_domains` |
| R003 | §1.2/§3 | Fail-closed 는 장치: PreToolUse Hook 이 허용 외 Write/Edit 차단(exit 2) | IMPLEMENTED | `plugin/hooks/guard_write.py`, `guard_common.py:228-240` | `tests/plugin/test_guard_write.py` (10 테스트, Level 매트릭스) |
| R004 | §3/§7.2 | Bash 우회 경로도 차단(settings.json deny) | PARTIAL | `guard_bash.py`, `settings_template.py:308-343`; 12개 우회 실측 통과(§4) | `test_guard_bash.py` 는 90 케이스 차단만 고정 — **H1** |
| R005 | §3 | AI 쓰기 허용 = `00_Inbox/ai-drafts/` 및 `_patches/` 만 | DEVIATES | ADR-0005: Level 누적(L1 ai-drafts·50_Journal, L2 +_patches·80_Outputs/drafts, L3 +40_IP/candidates) `levels.py:250-255` | `test_guard_sync.py::test_level_allow_in_sync`; 정본 내부 불일치 L7 |
| R006 | §3 | Deterministic Auditability — 모든 변경은 Git commit | PARTIAL | Hub 쓰기는 전부 commit(`service.py:144-148`); CLI `init`/`add-domain` 은 git 미사용(`scaffold.py`) | `test_api.py::test_promote_creates_commit_and_moves_note` — **M2** |
| R007 | §3 | AI 커밋 `[myelin:<skill>]` 접두사 | IMPLEMENTED | `_COMMON.md:9`, `service.py:369,402,430,468,553`, `commons.py:377,440` | `hub.spec.ts:344` |
| R008 | §3 | frontmatter `origin` 으로 AI 기여 추적 | IMPLEMENTED | `frontmatter.py:55-58`; 승격 시 claude→mixed `service.py:355-356` | `test_api.py:101` |
| R009 | §3 | Phase-gated Autonomy Level 0~3 단계 개방 | IMPLEMENTED | `levels.py`, `guard_common.py:114-119`, `render.py:134-141` | `test_skills.py::test_level_gating_table`, `test_guard_write.py::test_level_matrix` |
| R010 | §3 | HITL: verified 승격·MOC 편집·Commons 공개는 사람만, Hub Review Gate 유일 경로 | IMPLEMENTED | `app.py:221-264 require_user_click`, `patches.apply_plan` 호출은 `service.py:428` 만, `commons.publish_note(confirmed=…)` | `test_api.py::test_writes_require_user_click`, `test_commons.py::test_publish_requires_confirmation_and_deid` |
| R011 | §3 | Personal Ownership — 조직 열람 없음, 공유는 명시 publish 한정 | IMPLEMENTED | `metrics.py:459 payload_is_anonymous`, `commons.py:314-331` | `test_metrics.py::test_payload_is_anonymous` |
| R012 | §3 | Low-friction Onboarding — 설치→첫 verified 15분 | PARTIAL | `scripts/time_to_first_verified.py` 자동 측정 0.4s(합성); 사람 파일럿 0명 | `docs/reports/P8/time-to-first-verified.json`; **M7** |
| R013 | §1.2/§10.2 | Phase 는 Gate 통과 + 사람 승인 후에만 다음으로 | DEVIATES | P7 Gate pending 상태에서 P8·v1.0.0 진행(Brian "GO P8" 기록) `PHASE_STATE.md`, `docs/reports/P7.md` | ADR 없음(PHASE_STATE 기록) — **M7** |

### 3.2 §2 브랜드·제품군

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R014 | §2.1 | verified 노트 = "myelinated", Hub 에서 형광 라임 링 | IMPLEMENTED | `Review.tsx:319 mx-ring--verified is-myelinating`, `emboss.py @keyframes myelinate` | `hub.spec.ts:340` |
| R015 | §2.2 | KIPRIS(9류·42류)·도메인·GitHub 조직명 확인을 P8 에서 수행 | PARTIAL | `docs/reports/P8/naming-check.md`: USPTO·도메인·GitHub 완료, KIPRIS 직접 조회 미완 | 사람 항목 — **M7** |
| R016 | §2.3 | MYELIN CLI: init·add-domain·doctor·stats | IMPLEMENTED | `myelin_cli/app.py:141,254,279,306` | `test_cli.py` |
| R017 | §2.3 | Plugin: 7 Skill + Fail-closed Guard | IMPLEMENTED | `plugin/skills/*/SKILL.md`, `plugin/hooks/*` | `test_skills.py::test_seven_skills_exist_and_match_table` |
| R018 | §2.3 | MCP: Vault 검색·조회, 기본 읽기 전용 | IMPLEMENTED | `myelin_mcp/server.py:68-186` | `test_server.py::test_default_tools_are_read_only` |
| R019 | §2.3 | Hub: 지식 현황·Domain Map·Review Gate·온보딩 마법사·Pack 편집기 | IMPLEMENTED | `web/src/pages/{Dashboard,Domains,Review,Onboarding,Packs,Settings}.tsx` | `hub.spec.ts` |
| R020 | §2.3 | Emboss: Hub·Obsidian Theme 공용 | IMPLEMENTED | `scripts/emboss.py gen_css/gen_theme`, `design/dist/*`, `theme/obsidian-myelin-emboss/theme.css` | `test_emboss.py::test_generated_outputs_in_sync` |
| R021 | §2.3 | Commons: Pack Registry + 공개 승인 Evergreen 노트 | IMPLEMENTED | `commons.py:76-167 init_commons/registry`, `publish_note` | `test_commons.py` |

### 3.3 §4 아키텍처·기술 스택

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R022 | §4.1 L0 | Packs(YAML) + Frontmatter JSON Schema | IMPLEMENTED | `schema/export.py`, `docs/spec/schema/*.json` | `test_export.py`, gate P1 `export_schemas.py --check` |
| R023 | §4.1 L1 | Capture: Obsidian(모바일)·Web Clipper·음성 메모·Claude 대화 Export → 00_Inbox | PARTIAL | `00_Inbox/clips` 폴더만(`vault.py:188`); 도구 없음 | - — **L19** |
| R024 | §4.1 L2 | 개인 Vault + Git = 단일 정본 | PARTIAL | Hub 는 git 보장(`service.py:121`); CLI 경로는 git 없음 | **M2** |
| R025 | §4.1 L3 | myelin-core·CLI·Plugin·MCP·**Local LLM 라우팅** | PARTIAL | 라우팅은 `llm.route` 파싱·CLAUDE.md 출력만(`render.py:144`) | **H3** |
| R026 | §4.1 L4 | Hub(Web) + Obsidian Emboss Theme | IMPLEMENTED | `packages/myelin-hub`, `theme/` | - |
| R027 | §4.1 L5 | A3 Pack Registry · Commons Vault(Git) | IMPLEMENTED | `commons.py` registry/notes/proposals/metrics | `test_commons.py::test_init_commons_structure_and_idempotent` |
| R028 | §4.2 | Capture→Inbox→/ingest·/distill→ai-drafts(origin claude, status draft) | IMPLEMENTED | `ingest/SKILL.md`, `distill/SKILL.md`; doctor fail-closed 위치 규칙 `doctor.py:504-517` | `test_skills.py::test_skill_output_fixture_passes_doctor` |
| R029 | §4.2 | Review Gate promote → git commit → 10_Domains/<D>/ verified | IMPLEMENTED | `service.py:325-379` | `test_api.py::test_promote_creates_commit_and_moves_note`, e2e |
| R030 | §4.2 | /link patch 제안 → 사람 승인 | IMPLEMENTED | `patches.py`, `service.py:407-442` | `test_patches.py`, `test_api.py::test_patches_preview_apply_reject` |
| R031 | §4.2 | /compose → 80_Outputs | IMPLEMENTED | `compose/SKILL.md`(80_Outputs/drafts; 완성본 이동은 사람) | `test_skills.py`(compose fixture) |
| R032 | §4.2 | publish(opt-in, classification ≤ internal) → Commons | IMPLEMENTED | `commons.py:255-282,314-395` | `test_commons.py` |
| R033 | §4.3 | Personal 모드: Vault+CLI+Plugin+MCP+Hub(localhost) | IMPLEMENTED | `hub_api/__main__.py:302-307` loopback 강제 | `test_api.py::test_host_and_origin_guard` |
| R034 | §4.3 | Team 모드: Personal + Commons Git + 사내 Registry(인증은 Team 모드) | PARTIAL | Commons/Registry 구현; Hub 인증 없음(Backlog) | 정본이 인증 시점을 명시하지 않아 경미 |
| R035 | §4.3 | Offline 모드: 로컬 LLM 전용 | MISSING | `llm.default: local` 파싱만(`config.py:100`) | **L20** |
| R036 | §4.4 | Python 3.12·uv workspace·Pydantic v2·Typer·ruamel·pytest; 단일 core 공유 | IMPLEMENTED | `pyproject.toml`, 각 패키지의 `from myelin_core …` | `tests/test_repo_layout.py` |
| R037 | §4.4 | 색인 SQLite FTS5, Vault 외부 `.myelin/index.db`(git ignore) | IMPLEMENTED | `index.py:32,224`, `.gitignore` 생성 `scaffold.py:62` | `test_index.py` |
| R038 | §4.4 | (선택) 로컬 임베딩 | MISSING | ADR-0007 대안 절에서 범위 밖 선언 | 선택 항목 |
| R039 | §4.4 | MCP Python SDK, stdio 기본, Vault 루트 밖 차단 | IMPLEMENTED | `server.py:200`, `service.py:254-265 safe_rel` | `test_service.py::test_get_note_path_escape_rejected`, `::test_symlink_escape_rejected` |
| R040 | §4.4 | Hook 스크립트는 Python 표준 라이브러리만 | IMPLEMENTED | `plugin/hooks/*.py` import 검사 | `test_guard_sync.py::test_hooks_are_stdlib_only` |
| R041 | §4.4 | Hub FastAPI + React 18·Vite·TS·Tailwind(Emboss preset), localhost 기본 | IMPLEMENTED | `web/package.json`, `tailwind.config.cjs`(preset), `hub_api/__main__.py` | gate `npm run build` |
| R042 | §4.4 | Theme 는 tokens.json 에서 생성 | IMPLEMENTED | `emboss.py gen_theme`, gate `emboss.py check` | `test_emboss.py::test_generated_outputs_in_sync` |

### 3.4 §5 Domain Pack

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R043 | §5.1 | Pack 유형 core/reference/org/personal; Core 는 note types·템플릿만(필수) | IMPLEMENTED | `schema/pack.py:216-220,378-392`, `config.py:141 myelin.core 필수` | `test_pack_schema.py::test_core_pack_rules` |
| R044 | §5.2 | Pack 스키마(pack/version/kind/maintainer/requires/domains[...]) | IMPLEMENTED | `schema/pack.py:296-357` | `test_pack_schema.py::test_spec_example_pack` |
| R045 | §5.2 | Pack 필드는 정본 그대로(ADR-0003 §1) | DEVIATES | `Pack.description/templates/taxonomy_seed` 추가(`pack.py:353-357`) — ADR 미기재 | **L4** |
| R046 | §5.2 | `requires: [myelin.core>=1.0]` 의존성·버전 해석 | IMPLEMENTED | `pack.py:224-290 Version/Requirement`, `loader.py:540-588 resolve_packs` | `test_loader.py::test_resolve_*` |
| R047 | §5.2 | `accent` 는 Emboss accent 토큰 | IMPLEMENTED | `pack.py:208 ACCENTS`, tokens `semantic.domain.accent.values` | `test_pack_schema.py::test_accents_match_design_tokens` |
| R048 | §5.2 | Pack 미지 필드 거부(오타 조기 검출) | IMPLEMENTED | `pack.py:292 extra="forbid"` | `test_invalid_packs.py`(14 fixture) |
| R049 | §5.3 | myelin.yaml: owner/language/packs/domains/level/llm/commons | IMPLEMENTED | `config.py:52-133` | `test_config.py::test_spec_example` |
| R050 | §5.3 | 필드 집합 정본 그대로 | DEVIATES | `domains.extra`(ADR-0004), `commons.local/metrics_opt_in`(ADR-0010), `mcp.*`(ADR-0007) | ADR 3건으로 정당화 |
| R051 | §5.3 | `level` 0 read-only / 1 drafts / 2 link-patch / 3 scheduled review | IMPLEMENTED | `config.py:34-38`, `levels.py:257` | `test_config.py` |
| R052 | §5.3 | `llm.route` 로 confidential·40_IP 를 로컬 LLM 으로 | PARTIAL | 설정 모델만 | **H3** |
| R053 | §5.3 | `commons.enabled/remote` | PARTIAL | `remote` 는 `enabled` 검증과 Hub 설정 표시(`service.py:216`)에만 쓰임; publish 가 사용하지 않음 | **M9** |
| R054 | §5.4 | 3+1 규칙: Primary/Research/Growth + 선택 +1 | IMPLEMENTED | `config.py:65-93 Domains(extra)`, CLI 마법사 `app.py:181-194`, Hub `Onboarding.tsx:87-90` | `test_cli_interactive.py`, `test_config.py::test_domains_extra_roles` |
| R055 | §5.4 | Research/Growth 도 설정(3개) | DEVIATES | primary 만 필수(ADR-0004 §3, 온보딩 마찰 완화) | ADR 있음 |
| R056 | §5.5 | Reference Pack brian.physical-ai D1~D4 + Sub-MOC 표 | IMPLEMENTED | `packs/brian.physical-ai/pack.yaml`(golden CLAUDE.md 에 D1/D3/D4 Sub-MOC 일치) | `test_loader.py::test_brian_reference_pack` |
| R057 | §5.5 | /interview 질문 은행 제공 | IMPLEMENTED | `packs/brian.physical-ai/interviews.yaml`, `app.py:362-412 interview-bank` | `test_cli_skills.py::test_interview_bank` |
| R058 | §5.6 | Org Starter Pack 6종(초안) | PARTIAL | 2종(`a3.security-consulting`, `a3.incident-response`); P7 "2종 확정" 과는 일치 | **L18** |
| R059 | §5.6 | a3.security-consulting: 진단 방법론 체크리스트·고객 유형별 lesson 템플릿 | IMPLEMENTED | `packs/a3.security-consulting/templates/{assessment-checklist,lesson-customer-type}.md` | `test_loader.py::test_a3_org_pack` |
| R060 | §5.6 | a3.incident-response: Timeline·IoC(비식별 규칙)·Post-mortem | IMPLEMENTED | `packs/a3.incident-response/templates/{timeline,ioc,post-mortem}.md` | `test_loader.py::test_a3_incident_response_pack` |

### 3.5 §6 Vault 표준

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R061 | §6.1 | 폴더 구조(myelin.yaml, CLAUDE.md, 00_Inbox/{ai-drafts,clips}, 10_Domains/<ID>/_MOC.md, 20/30/40/50/80, 90_System/{templates,prompts,taxonomy.md}, 99_Archive, _patches, .myelin) | IMPLEMENTED | `vault.py:185-224 STANDARD_DIRS`, `scaffold.py:142-157 plan_init` | `test_scaffold.py::test_init_creates_standard_layout`, `test_golden.py` |
| R062 | §6.1 | CLAUDE.md = Pack 에서 렌더링(자동 생성 + 개인 섹션 보존) | IMPLEMENTED | `render.py:385-445`, personal 마커 | `test_render.py::test_render_claude_md_levels_and_personal` |
| R063 | §6.1 | `.myelin/` 색인·로그, git ignore | IMPLEMENTED | `scaffold.py:62-67`, `service.py:124-130` | `test_golden.py`(.gitignore 포함) |
| R064 | §6.1 | init 은 기존 Vault 를 덮어쓰지 않음(fail-closed) | IMPLEMENTED | `scaffold.py:171-183` (충돌 검사 + `open("x")`) | `test_scaffold.py::test_init_is_fail_closed`, `test_cli.py::test_init_fail_closed_on_existing` |
| R065 | §6.2 | Frontmatter v2 12필드·enum(type 9종, status 4, origin 3, classification 3) | IMPLEMENTED | `schema/frontmatter.py:36-104` | `test_frontmatter.py::test_spec_example_validates`, `::test_enum_fields_rejected` |
| R066 | §6.2 | id 자동 생성·불변 | IMPLEMENTED | `render.py:289 make_note_id`; patch 로 id 변경 불가 `patches.py:62`; 승격 시 보존 | `test_patches.py::test_frontmatter_allowlist` |
| R067 | §6.2 | `share: true` 일 때만 Commons 후보 | IMPLEMENTED | `commons.py:285-295 candidates` | `test_commons.py::test_candidates_lists_share_true_only` |
| R068 | §6.2 | doctor: 스키마 위반 검출 | IMPLEMENTED | `doctor.py:449-452` | `test_doctor.py::test_seeded_vault_detected_100_percent` |
| R069 | §6.2 | doctor: verified 노트가 미검증 `origin: claude` 노트를 링크(fail-closed 위반) | IMPLEMENTED | `doctor.py:534-550` | seeded `Verified Links AI.md` |
| R070 | §6.2 | doctor: 고아 노트 | IMPLEMENTED | `doctor.py:565-574`(Inbox·Archive·MOC 제외) | seeded `Lonely.md` |
| R071 | §6.2 | doctor: confidential + share:true 모순 | IMPLEMENTED | `doctor.py:466-474` | seeded `Secret Shared.md` |
| R072 | P2 | doctor 규칙 8종(+깨진 링크·id 중복·미등록 domain·날짜 역전) | IMPLEMENTED | `doctor.py:361-370 RULES` | `test_doctor.py`(시드 100%, 오탐 0) |
| R073 | §6.2/§11.1 | 고아 정의의 doctor·stats 일관성 | DEVIATES | `stats.py:667`/`index.py:526` 은 Inbox·MOC 포함 | ADR 없음 — **L11** |

### 3.6 §7.1 Plugin Skills

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R074 | §7.1 | Skill 7종·최소 Level·쓰기 범위 표 | IMPLEMENTED | `levels.py:232-247 SKILLS` | `test_skills.py::test_seven_skills_exist_and_match_table`, `test_guard_sync.py::test_every_skill_scope_is_allowed_at_its_level` |
| R075 | §7.1 | /ingest(L1): 파일·URL·PDF → literature 초안(출처·핵심 주장·인용 위치) → ai-drafts | IMPLEMENTED | `plugin/skills/ingest/SKILL.md:14-20` | fixture `tests/fixtures/skill-outputs/ingest` doctor 통과 |
| R076 | §7.1 | /distill(L1): 원자 노트 분해·frontmatter·중복 검사·용어 정규화 | IMPLEMENTED | `distill/SKILL.md:12-19` | fixture 통과 |
| R077 | §7.1 | /interview(L1): Pack 질문 은행 기반 → lesson 초안 | IMPLEMENTED | `interview/SKILL.md:13`(`myelin interview-bank --json`) | `test_cli_skills.py::test_interview_bank`, fixture |
| R078 | §7.1 | /link(L2): 링크 후보+근거, MOC patch → _patches | IMPLEMENTED | `link/SKILL.md`, `patches.py` | `test_skills.py::test_link_patch_fixtures_parse` |
| R079 | §7.1 | /compose(L2): 목적·독자 기반 산출물 → 80_Outputs/drafts | IMPLEMENTED | `compose/SKILL.md` | fixture |
| R080 | §7.1 | /review(L1): 주간 품질 보고서(doctor+지표) → 50_Journal | IMPLEMENTED | `review/SKILL.md:13-17` | fixture |
| R081 | §7.1 | /ip-scan(L3): Cross-domain verified → 특허 후보 → 40_IP/candidates, **로컬 LLM 라우팅** | PARTIAL | Level·`disable-model-invocation` 은 구현; 라우팅은 SKILL 문장만(`ip-scan/SKILL.md:14`) | **H3** |
| R082 | P3 Gate | Level 0 에서 쓰기 Skill 비활성 | IMPLEMENTED | 소프트: `_COMMON.md:4`(`myelin skills --json`); 하드: `guard_common.py:230` L0 전체 차단 | `test_cli_skills.py::test_skills_level_0_all_disabled`, `test_guard_write.py::test_level_matrix` |
| R083 | 부록 B | "Level 0 에서는 Skill 자체를 비노출" | DEVIATES | 플러그인 Skill 은 정적이라 Vault 별 숨김 불가 → 3겹 소프트/하드 가드(ADR-0005 §7) | ADR 있음 |
| R084 | §7.1 | Skill 호출명 `/ingest` 등 | DEVIATES | 플러그인 네임스페이스 `/myelin:ingest`(플랫폼 제약) | **L8** |

### 3.7 §7.2 Fail-closed Guard

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R085 | §7.2 | hooks.json PreToolUse matcher `Write\|Edit\|MultiEdit` → guard_write.py | IMPLEMENTED | `plugin/hooks/hooks.json:12-25`(+NotebookEdit); `args`·`timeout`·`onFailure`·`statusMessage` 는 공식 문서상 유효 필드 | `test_guard_sync.py::test_hooks_json_wires_both_guards`; `onFailure` 는 2.1.295+ — **L1** |
| R086 | §7.2 | exit 2 로 차단, 사유를 Claude 에 전달 | IMPLEMENTED | `guard_common.py:132-135 block()` stderr | 전 Guard 테스트 |
| R087 | §7.2 | Vault 밖 쓰기 차단(resolve 후 relative_to) | IMPLEMENTED | `guard_common.py:204-225 resolve_inside` | `test_guard_write.py::test_outside_vault_and_dotdot`, `::test_symlink_escape` |
| R088 | §7.2 | 허용 외 경로 → "사람 승인 영역, _patches 에 제안" 안내 | IMPLEMENTED | `guard_common.py:237-240` | `::test_blocked_paths_at_level_1` |
| R089 | §7.2 | `MYELIN_VAULT` 환경변수(없으면 cwd) | IMPLEMENTED | `guard_common.py:168-190 find_vault`(MYELIN_VAULT→CLAUDE_PROJECT_DIR→cwd) | `::test_vault_discovery_order` |
| R090 | §7.2 | 판단 불가 입력(비JSON·빈 경로·Vault 없음·level 없음) 차단 | IMPLEMENTED | `guard_common.py:157-201` | `::test_undecidable_input_is_blocked`, `::test_no_vault_is_blocked`, `::test_bad_or_missing_level_blocks` |
| R091 | §7.2 | 허용 디렉터리 안이라도 안전하지 않은 쓰기(스크립트 파일·숨김 디렉터리·`_patches/applied\|rejected`) | MISSING | `check_allowed` 는 디렉터리 접두만 검사; `.sh/.py` 와 `_patches/applied/` 쓰기 실측 허용 | **H2** |
| R092 | §7.2 | Bash 우회 제한(settings.json deny) | IMPLEMENTED | `settings_template.py:295-346`(`Edit(...)` deny 15경로, Bash 접두어 deny 15종, ask 5종); init 이 `.claude/settings.json` 생성 | `test_levels_settings.py`, golden |
| R093 | §7.2 | Bash Guard(ADR-0005 §5) 리다이렉션·writer·인라인 인터프리터·git·`$(…)`·cd 차단 | PARTIAL | 블록리스트 방식 → 12개 우회 통과(§4) | `test_guard_bash.py` — **H1** |
| R094 | §7.2 | Hook 입력 필드명·환경변수를 현행 문서로 재확인하고 테스트로 고정 | IMPLEMENTED | `docs/adr/0002-plugin-spec.md §3`; 공식 문서 재확인(2026-10-18) 일치 | `test_guard_write.py::test_notebook_edit_uses_notebook_path` |
| R095 | §7.2 | MultiEdit 매칭 | IMPLEMENTED | 공식 문서상 legacy 도구이나 matcher 에 남겨도 무해(ADR-0002 D1) | - |
| R096 | 부록 B | Guard 차단 이벤트 Hub 표시(Backlog 예시) | IMPLEMENTED | `guard_common.py:138-154 guard.log`, `service.py:308-322`, `Dashboard.tsx:181` | `test_api.py::test_guard_events_surface` |

### 3.8 §7.3 MCP

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R097 | §7.3 | search_notes: FTS + domain/status/type 필터 | IMPLEMENTED | `server.py:75-93`, `index.py:429-466`(trigram + LIKE 하이브리드) | `test_index.py::test_search_and_filters`, `test_service.py` |
| R098 | §7.3 | search_notes (+선택 임베딩) | MISSING | 선택 항목(ADR-0007 대안) | - |
| R099 | §7.3 | get_note: 본문+frontmatter; confidential 은 local 클라이언트만 | DEVIATES | ADR-0007 §3: "local" = 소유자 opt-in `mcp.expose_confidential`(`service.py:242-252`); 클라이언트 지역성 자동 판별 없음 | `test_service.py::test_get_note_redacts_confidential`, `::test_expose_confidential_opt_in` |
| R100 | §7.3 | query_frontmatter(Dataview 류) | IMPLEMENTED | `server.py:102-140`, `index.py:468-479` | `test_service.py::test_query_frontmatter_and_limits` |
| R101 | §7.3 | list_domains / vault_stats | IMPLEMENTED | `server.py:142-161` | `test_service.py::test_list_domains_and_stats` |
| R102 | §7.3/P4 | write_draft: Level ≥ 1 + myelin.yaml 명시 허용 시만 **등록** | IMPLEMENTED | `server.py:163-184`, `service.py:245-247` | `test_server.py::test_write_draft_registered_only_when_enabled`, `test_service.py::test_write_draft_requires_level` |
| R103 | §7.3 | write_draft 는 ai-drafts 에만, 덮어쓰기 금지 | IMPLEMENTED | `service.py:421-431`(`open("x")`, 경로 재검증) | `test_service.py::test_write_draft_enabled` |
| R104 | P4 Gate | 경로 이탈(.., 절대경로, ~, symlink) 차단 | IMPLEMENTED | `service.py:254-265` | `test_service.py` escape 2건 |
| R105 | P4 Gate | 기본 읽기 전용 확인 | IMPLEMENTED | `server.py` 조건부 등록 | `test_server.py::test_default_tools_are_read_only` |
| R106 | P4 Gate | 5,000 노트 search p95 < 300ms | IMPLEMENTED | `tests/test_perf_index.py`(17ms 보고) — `MYELIN_PERF=1` 전용, CI gate 에서 설정됨 | `ci.yml:171-172` |
| R107 | P4 | 색인 증분 갱신(mtime/hash) | IMPLEMENTED | `index.py:257-298` | `test_index.py::test_incremental_refresh` |
| R108 | P4 | Claude Desktop/Code 설정 가이드 | IMPLEMENTED | `docs/guides/mcp-setup.md` | gate P4 |
| R109 | §7.3 | 40_IP/** 도 기밀로 취급(정본 §5.3 route 와 정합) | IMPLEMENTED | `service.py:252 _hidden` | `test_service.py::test_search_hides_confidential_by_default` |

### 3.9 §8 Emboss 디자인 시스템

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R110 | §8.1 | 토큰 surface/shadow-light/shadow-dark/raised/inset/ink/violet-600/violet-50/neon-lime/neon-cyan/neon-magenta/radius(28/20/999) | IMPLEMENTED | `design/tokens.json:8-39` | `test_emboss.py::test_spec_values_preserved_or_recorded` |
| R111 | §8.1 | `--muted #6B6F85`, lime-ink `#4D7C0F`, cyan-ink `#0891B2` | DEVIATES | ADR-0008: 4.5:1 미달 → #5F6378 / #3F6A0A / #0E7490(`tokens.json` `spec` 필드 보존) | `test_emboss.py::test_contrast_all_pairs` |
| R112 | §8.4 | `.mx-input` border `#E2E5EE` | DEVIATES | ADR-0008 추가 결정 → `--border #DADEE9` | ADR 있음 |
| R113 | §8.4 | 변수명 `--surface --ink --muted --sh-l --sh-d --violet --lime --cyan --magenta --raised --inset` | DEVIATES | 구현 `--mx-*` 접두(`emboss.py:63-72`); ADR 미기재 | **L6** |
| R114 | §8.4 | 클래스 `.mx-card .mx-input(:focus) .mx-btn-primary .mx-chip--verified .mx-chip--ai .mx-glow--ai .mx-badge--blocked` | IMPLEMENTED | `emboss.py gen_css` | `test_emboss.py::test_gallery_uses_only_tokens_and_labels_states` |
| R115 | §8.2 | draft = Violet 외곽선 칩 | IMPLEMENTED | `.mx-chip--draft` | 갤러리 테스트 |
| R116 | §8.2 | ai-draft = Cyan 채움 칩 + 카드 Cyan glow | PARTIAL | 칩 구현·사용; `.mx-glow--ai` 는 Hub 미사용(0건) | **L16** |
| R117 | §8.2 | verified = Lime 칩 + Lime ring + 승격 순간 "myelinated" 애니메이션 | IMPLEMENTED | `emboss.py @keyframes myelinate`, `Review.tsx:318-319` | e2e `promoted-card` |
| R118 | §8.2 | blocked = Magenta 외곽선 배지 | IMPLEMENTED | `.mx-badge--blocked`; Hub invalid/blocked/오류 표시 | - |
| R119 | §8.2 | Domain 정체성 = Pack accent → Orb glow | IMPLEMENTED | `.mx-orb[data-accent]`, `Domains.tsx:231` | e2e `orb-D1` |
| R120 | §8.3 | Card/KPI Tile raised, 숫자 상태색·라벨 muted | IMPLEMENTED | `.mx-kpi__value--verified/--ai/--blocked`, `Dashboard.tsx:178-183` | - |
| R121 | §8.3 | Primary Button violet 채움+glow, 화면당 1개 | UNTESTED | 각 페이지 `.mx-btn-primary` 0~1개(수동 확인) | 자동 검사 없음 — **M8** |
| R122 | §8.3 | Secondary Button raised → 누르면 inset | IMPLEMENTED | `.mx-btn:active, [aria-pressed="true"]` | - |
| R123 | §8.3 | Input inset, focus 2px violet ring | IMPLEMENTED | `.mx-input:focus { outline: var(--mx-focus-ring) }` | - |
| R124 | §8.3 | Nav Item 활성 시 inset + violet | IMPLEMENTED | `.mx-nav-item.is-active`, `App.tsx:35` | - |
| R125 | §8.3 | Status Chip pill, 네온 위 텍스트 = ink | IMPLEMENTED | `.mx-chip--ai/--verified { color: var(--mx-ink) }` | `emboss.py a11y` NEON-AS-TEXT |
| R126 | §8.3 | Domain Orb 클릭 시 MOC 이동 | PARTIAL | 클릭 = 상세 선택; MOC 는 별도 버튼(`Domains.tsx:241`) | **L17** |
| R127 | §8.3 | Review Row 좌측 칩 + Promote(Lime)/Reject | IMPLEMENTED | `.mx-review-row`, `Review.tsx:324-331` | e2e |
| R128 | §8.3 가드레일1 | 네온을 텍스트 색으로 쓰지 않음, 숫자 강조는 어두운 변형 | IMPLEMENTED | `emboss.py:49 NEON_TEXT_RE`, `--lime-ink/--cyan-ink` | `test_emboss.py::test_neon_as_text_detected` |
| R129 | 가드레일2 | 텍스트 대비 4.5:1 스크립트 검증(P5 Gate) | IMPLEMENTED | `emboss.py a11y`(13쌍), gate P5/P8/P9 | `test_emboss.py::test_contrast_all_pairs` |
| R130 | 가드레일3 | 경계 요소는 1px 경계선 또는 focus ring | IMPLEMENTED | `.mx-input/.mx-btn border: 1px solid var(--mx-border)` | - |
| R131 | 가드레일4 | 상태는 색만으로 전달하지 않음(칩 텍스트 라벨) | UNTESTED | Hub 칩은 텍스트 포함(수동 확인); 자동 검사는 갤러리만 | **M8** |
| R132 | 가드레일5 | 다크 모드 범위 밖, 토큰 구조만 대비 | IMPLEMENTED | `tokens.json modes`, theme `.theme-dark` 에 light 값, RELEASE_NOTES | gate P8 "다크 모드" 문구 |
| R133 | P5 Gate | 토큰 하드코딩 0(lint) | IMPLEMENTED | `emboss.py lint` 12파일 0건(실행 확인); web/src 색 리터럴 0 | `test_emboss.py::test_lint_no_raw_colors_in_ui` |
| R134 | P5 | tokens → CSS vars / Tailwind preset 생성 | IMPLEMENTED | `design/dist/{emboss.css,tailwind.preset.cjs}` | gate `emboss.py check` |
| R135 | P5 | 컴포넌트 스펙 문서 + 정적 갤러리 + 스크린샷 승인 | IMPLEMENTED | `design/components.md`, `design/gallery/index.html`, `docs/reports/P5/gallery.png` | gate P5 |
| R136 | P5 | theme/obsidian-myelin-emboss(manifest, theme.css) | IMPLEMENTED | 생성물; manifest version 0.1.0 | **L12** |

### 3.10 §9 조직 확장

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R137 | §9.1 | 개인 Vault 불가침, 지표는 opt-in 익명 집계만 | IMPLEMENTED | `metrics.py:480-491`(opt-in 아니면 PermissionError), `payload_is_anonymous` | `test_metrics.py::test_write_requires_opt_in_and_aggregates` |
| R138 | §9.1 | Publish 조건 share+verified+≤internal, Hub "Commons 제안" → Commons Git **PR** | PARTIAL | 조건·브랜치·커밋·확인 단계 구현; Hub 는 push/PR 미연결(`Review.tsx:374 push 미지정`) | `test_api.py::test_commons_candidates_and_publish` — **M1** |
| R139 | §9.1 | 챔피언 PR 리뷰(비식별 확인) 후 merge | IMPLEMENTED | 프로세스 문서 `commons.py CHAMPIONS`, `registry champions`, `admin-guide §2`; 자동 비식별 스캔 `commons.py:171-228` | `test_commons.py::test_builtin_deid_patterns` |
| R140 | §9.1 | 출처 보존(작성자·원 id) | IMPLEMENTED | `commons.py:347-350`(author, published_from, published_by, published) | `test_commons.py::test_publish_success_branch_commit_provenance` |
| R141 | §9.1 | Pack 진화: Personal → Org Pack 제안 | PARTIAL | CLI `pack-propose`(`commons.py:398-445`); Hub UI 없음 | `test_commons.py::test_propose_pack` — **L21** |
| R142 | §9.1 | 사전 합의 정책(지식 소유권·외부 AI 범위·특허) | IMPLEMENTED | 문서 `docs/guides/admin-guide.md §3` (정책 항목, 코드 대상 아님) | - |
| R143 | P7 | 개인 Vault 내용을 외부로 보내는 모든 경로에 사용자 확인 | IMPLEMENTED | publish/propose/metrics 3경로 모두 `confirmed`/`--yes`/체크박스 요구 | `test_cli_commons.py`, `test_api.py:334-344` |
| R144 | P7 Gate | confidential / share:false publish 차단 100% | IMPLEMENTED | `commons.py:265-282` 쓰기 전 차단 | `test_commons.py::test_publish_blocks_confidential_and_share_false_100_percent` |
| R145 | P7 Gate | 파일럿 5명 이상 온보딩 15분, 피드백 리포트 | PARTIAL | `scripts/pilot.py` 도구 준비; 기록 0건, `pilot-feedback.md` TBD | **M7** |
| R146 | §9.2 | Rollout Alpha→Pilot→Wave 1/2 | PARTIAL | 문서(`admin-guide §4`, `pilot-guide.md`); 운영 미실시 | 운영 항목 |
| R147 | §9.3 | 60분 워크숍 교육 키트 | IMPLEMENTED | `docs/guides/workshop-60min.md`(11줄 개요) | **L13** |
| R148 | 부록 D | 구성원 Day 1 체크리스트 | IMPLEMENTED | `docs/guides/day1-checklist.md` | gate P7 |

### 3.11 §10 Phase 구현 계획·Gate

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R149 | §10.1 | Monorepo 구조(CLAUDE.md, PHASE_STATE.md, Makefile, docs/{spec,phases,adr,reports}, packs, packages/{core,cli,mcp,hub/{api,web}}, plugin, design/tokens.json, theme, tests/{fixtures/vaults,e2e}) | IMPLEMENTED | 디렉터리 존재(`tests/test_repo_layout.py`) | `tests/e2e/` 비어 있음 — **L9** |
| R150 | §10.2 | 세션 시작 CLAUDE.md→PHASE_STATE→phases 읽기; Task 단위 테스트→구현→commit; PHASE_STATE 갱신 | IMPLEMENTED | `CLAUDE.md`, `PHASE_STATE.md`(Done/Next/Blockers/Decisions/Backlog) | 미커밋 변경 4건 — **L10** |
| R151 | §10.2 | 되돌리기 어려운 결정은 ADR | IMPLEMENTED | `docs/adr/0001~0010` | 일부 편차 ADR 누락(L4·L6·L15) |
| R152 | §10.2 | Phase 종료: gate → reports/P{n}.md → tag → 멈춤 | IMPLEMENTED | `docs/reports/P0~P8.md`, 태그 phase-P0~P6·P8·P9, v1.0.0·v1.1.0; P7 태그 없음(정직) | - |
| R153 | §10.2 | 다음 Phase 는 "GO" 후에만 | DEVIATES | P7 pending 중 P8 진행(승인 기록 있음) | **M7** |
| R154 | §10.3 | Gate 기준을 Phase 별로 스크립트화 | IMPLEMENTED | `scripts/gate.py GATES[0..9]`; 미구현 Phase 는 fail-closed | `make gate P=<n>` |
| R155 | P0 Gate | gate P=0, CI green, PHASE_STATE 에 P1 Task | IMPLEMENTED | `gate.py:79-91`, `.github/workflows/ci.yml` | - |
| R156 | P1 Gate | Pack 3종 검증, 커버리지 ≥ 90%, 잘못된 Pack 10종 명확한 오류 | IMPLEMENTED | `gate.py:92-126`; invalid fixture 14종 | `test_invalid_packs.py` |
| R157 | P2 Gate | golden snapshot 일치, doctor 100%/오탐 0, init < 10s | IMPLEMENTED | `gate.py:127-179` | `test_golden.py`, `test_doctor.py` |
| R158 | P3 Gate | Guard 차단 100%(허용 외·Vault 밖·symlink·..), ingest/distill 결과 doctor 통과, L0 비활성 | PARTIAL | Write/Edit 경로는 100%; Bash 경로는 우회 존재 | **H1/H2** |
| R159 | P3 | Vault용 settings.json(permissions) 템플릿 | IMPLEMENTED | `settings_template.py`, golden `.claude/settings.json` | `test_levels_settings.py` |
| R160 | P3 | `claude plugin validate --strict` | IMPLEMENTED | `gate.py:209-212`, marketplace 검증 `gate.py:463-466` | - |
| R161 | P4 Gate | 경로 이탈·읽기 전용·p95 | IMPLEMENTED | `gate.py:229-288` | - |
| R162 | P5 Gate | 토큰 단일 원천·대비·하드코딩 0·갤러리 승인 | IMPLEMENTED | `gate.py:289-310` | - |
| R163 | P6 Gate | Playwright e2e 온보딩→첫 승격, commit 확인, 클릭 없는 쓰기 0 | IMPLEMENTED | `web/e2e/hub.spec.ts`(4 테스트, git status clean 확인) | CI 미실행 — **M5** |
| R164 | P6 Gate | 쓰기 경로 감사 테스트(모든 쓰기 403 without header) | UNTESTED | `/api/patches/{name}/reject` 403 미검증(코드는 요구) | **M6** |
| R165 | P6 | 화면별 스크린샷 docs/reports/P6/ | IMPLEMENTED | 8 PNG | gate ≥5 |
| R166 | P6 | 온보딩 마법사 = init 과 동일 로직 | IMPLEMENTED | `service.py:560-597` → `init_vault` 재사용 | `test_api.py::test_onboarding_flow` |
| R167 | P6 | UI 는 P5 토큰만 | IMPLEMENTED | lint 0건; `index.css` 는 `var(--mx-*)` 만 | `test_emboss.py::test_lint_no_raw_colors_in_ui` |
| R168 | P7 Gate | 사람 항목(파일럿·피드백) | PARTIAL | `gate.py:425-436` HUMAN 체크 FAIL 상태 | **M7** |
| R169 | P8 Gate | 위협 모델 High 0 | DEVIATES | T08·T09 조치; T02(Bash 우회)는 자체 High 정의에 해당하나 Medium 기재 | **M3** |
| R170 | P8 Gate | 신규 사용자 설치→첫 verified < 15분 | PARTIAL | 합성 측정 0.4s(`time-to-first-verified.json`); 신규 환경·사람 측정 없음 | **M7** |
| R171 | P8 Gate | KIPRIS 검색 결과 기록 | PARTIAL | `naming-check.md` 에 "직접 조회 미완료" | 사람 항목 |
| R172 | P8 | 설치 스크립트(uv tool install, plugin 등록, MCP 설정, Theme 복사) | DEVIATES | 런처(`uv --directory run`) 방식(`install.sh:234-247`); plugin/MCP 는 `--claude` opt-in | `tests/test_install.py` — **L15** |
| R173 | P8 | 사용자·관리자 가이드·릴리스 노트(알려진 제약 명시) | IMPLEMENTED | `docs/guides/{user,admin}-guide.md`, `docs/RELEASE_NOTES.md` | gate P8 |
| R174 | P8 | 위협 모델(STRIDE) 문서 + High 조치 회귀 테스트 | IMPLEMENTED | `docs/security/threat-model.md`(19 위협) | `test_api.py::test_host_and_origin_guard`, `::test_static_no_path_traversal` |
| R175 | P0 | CI: lint + typecheck + test + gate | IMPLEMENTED | `.github/workflows/ci.yml`(현재 Phase 자동 해석) | e2e 미포함 — **M5** |

### 3.12 §11 지표 · §12 위험

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R176 | §11.1 | 개인 KPI 6종(Inbox 체류·Evergreen 증가·AI 승격률·고아·Cross-domain·재투입) + 목표 | IMPLEMENTED | `stats.py:601-608 TARGETS`, `index.py:498-550`, `Dashboard.tsx:184-194`, MCP `vault_stats` | `test_stats.py`, `test_index.py::test_index_stats_match_full_scan` |
| R177 | §11.1/§12 | AI 승격률 40~70% 초과 시 "검토 부실 신호"(상한 경보) | PARTIAL | Dashboard 는 값·목표만; `/review` SKILL 문장 | **M4** |
| R178 | §11.2 | 활성 사용자(주 1회 verified) | IMPLEMENTED | `metrics.py:447,505-516` | `test_metrics.py` |
| R179 | §11.2 | 온보딩 시간(설치→첫 verified ≤ 15분) | IMPLEMENTED | `metrics.py:421-428`, 이벤트 `onboard_start/first_promote` | `test_metrics.py::test_events_and_onboarding_minutes` |
| R180 | §11.2 | Commons 공개 노트 수(월) | PARTIAL | 로컬 `publish` 이벤트 수(merge 미반영) | **L14** |
| R181 | §11.2 | 재사용(Commons 노트 인용 횟수) | MISSING | 계산 코드 없음 | **H4** |
| R182 | §11.2 | Pack 진화 제안 건수 | IMPLEMENTED | `metrics.py:451 proposals` | `test_metrics.py` |
| R183 | §12 | 뉴모피즘 가독성 → 가드레일·대비 검사·경계선·focus ring | IMPLEMENTED | R128~R130 | - |
| R184 | §12 | 기밀 유출 → classification + LLM 라우팅 + publish 차단 + 챔피언 리뷰 | PARTIAL | 라우팅 미구현(H3); 나머지 구현 | - |
| R185 | §12 | AI 과의존 → 승격률 상한 경보·origin 추적·월간 샘플 감사 | PARTIAL | 경보 없음(M4), 감사는 프로세스 미도구화 | - |
| R186 | §12 | 소유권 분쟁 → §9.1 정책 사전 합의 명문화 | IMPLEMENTED | `admin-guide §3`, `commons.py README` | - |
| R187 | §12 | 상표 충돌 → P8 이전 KIPRIS, 대안명 | PARTIAL | USPTO 조사·대안(MYELIN KOS) 기록; KIPRIS 미완 | - |

### 3.13 부록 · 저장소 규칙 · 금지 행위 점검

| ID | § | 요구사항(요지) | 상태 | 근거 | 테스트 / 비고 |
|---|---|---|---|---|---|
| R188 | 부록 A | 저장소 CLAUDE.md(Context/Session Protocol/Engineering Rules/Commit) | IMPLEMENTED | `CLAUDE.md`(부록 A 확장판) | - |
| R189 | 부록 B | PHASE_STATE.md 템플릿(Done/Next/Blockers/Decisions/Backlog) | IMPLEMENTED | `PHASE_STATE.md` | `test_repo_layout.py::test_phase_state_has_header` |
| R190 | CLAUDE.md | Hub 쓰기 경로는 모두 사용자 클릭 헤더 요구(금지 행위 점검) | IMPLEMENTED | `app.py` 8개 POST/PUT 전부 `Depends(require_user_click)`; 예외 `POST /api/packs/validate` 는 순수 검증(`service.py:516-522`, 쓰기 없음) | `test_api.py::test_reads_never_write` |
| R191 | CLAUDE.md | AI 가 허용 범위 밖에 쓰는 코드 경로 없음 | IMPLEMENTED | MCP `write_draft` → ai-drafts 만; Hub `_write_welcome` → ai-drafts(`service.py:603`); Skill 은 Guard 대상 | - |
| R192 | CLAUDE.md | web/src 색 리터럴 0 | IMPLEMENTED | `emboss.py lint` 실행 0건; `grep '#[0-9a-f]{3,8}'` web/src 0건 | `test_emboss.py` |
| R193 | CLAUDE.md | Hook 스크립트 비표준 라이브러리 import 없음 | IMPLEMENTED | `guard_*.py` import: json/os/re/sys/time/pathlib/shlex | `test_guard_sync.py::test_hooks_are_stdlib_only` |
| R194 | CLAUDE.md | fixtures 는 합성 데이터만; 비밀·개인 Vault 미커밋 | IMPLEMENTED | `tests/fixtures/vaults/*`(합성), `.local/` gitignore | - |
| R195 | CLAUDE.md | 테스트 없는 기능 merge 금지 | PARTIAL | 전반 양호(421 tests); R121/R131/R164 는 테스트 공백 | **M6/M8** |
| R196 | README | "Fail-closed … Bash 차단, 판단 불가 = 차단" | DEVIATES | 과대 서술(우회 12종) | **L3** |
| R197 | README | "Claude Code 2.1.275+" | DEVIATES | `onFailure` 는 2.1.295+ | **L1** |
| R198 | README | "406 tests" | DEVIATES | 실측 421 | **L2** |
| R199 | ADR-0003 | "Pack 필드 추가 없음" | DEVIATES | description/templates/taxonomy_seed 추가 | **L4** |
| R200 | ADR-0009 | "쓰기 동작 6종" | DEVIATES | 실제 8종 | **L5** |

---

## 4. Guard 실측 로그 (fixture Vault `tests/fixtures/vaults/basic`, level 2)

`printf '<event JSON>' | MYELIN_VAULT=<vault> python3 plugin/hooks/guard_bash.py` 결과. rc=0 은 **허용**, rc=2 는 차단.

| 명령 | rc | 판정 |
|---|---|---|
| `bash 00_Inbox/ai-drafts/x.sh` · `sh …/x.sh` · `python3 …/x.py` · `perl …/x.pl` · `ruby …/x.rb` · `node …/x.js` · `uv run python …/x.py` | 0 | **우회** — AI 가 만든 스크립트 실행(부작용 미검사). settings.json ask 는 python/node/uv run python 만 |
| `python3 -` (stdin 스크립트) | 0 | **우회** — ask 는 걸림(`Bash(python3 *)`) |
| `curl -s -o 10_Domains/D1/x.md …` · `wget -O 10_Domains/D1/x.md …` | 0 | **우회** — 사람 승인 영역에 파일 생성 |
| `find 10_Domains -name "*.md" -delete` | 0 | **우회** — 삭제 |
| `awk '{print > "10_Domains/D1/x.md"}' README.md` | 0 | **우회** — 프로그램 내부 리다이렉션 |
| `patch -p0 < …/x.diff` · `cat …/x.diff \| patch -p0` | 0 | **우회** |
| `xargs rm < list.txt` | 0 | **우회** |
| `git apply …/x.diff` · `git am …/x.patch` · `git read-tree HEAD` · `git checkout-index -a -f` · `git update-index --assume-unchanged x` | 0 | **우회** — 작업 트리 변경 git 하위 명령이 GIT_BLOCKED 에 없음 |
| `echo hi > 10_Domains/D1/x.md` · `tee 10_Domains/D1/x.md` · `sed -i … 10_Domains/D1/x.md` · `rsync -a 00_Inbox/ 10_Domains/` · `ln -s /etc …` | 2 | 차단(정상) |
| `git checkout -- .` · `git stash` · `git mv a b` · `git restore .` · `git worktree add x` | 2 | 차단(정상) |
| `perl -pi -e s/a/b/ 10_Domains/D1/x.md` | 2 | 차단(정상, 인라인) |
| `echo hi > 00_Inbox/ai-drafts/ok.md` · `myelin doctor` · `git commit -m x` · `sqlite3 .myelin/index.db .dump` | 0 | 허용(정상) |

`guard_write.py`: `Write 00_Inbox/ai-drafts/x.sh` rc=0 · `Write _patches/applied/fake.patch.md` rc=0 · `Write 00_Inbox/ai-drafts/.hidden/x.md` rc=0 (모두 **허용** — H2).

### 4.1 재검증 (보고서 작성 중 수정된 `plugin/hooks/*` 기준, 동일 fixture)

| 명령 | 이전 | 재검증 |
|---|---|---|
| `bash 00_Inbox/ai-drafts/x.sh` · `python3 00_Inbox/ai-drafts/x.py` | 0 | **0 (여전히 허용)** — docstring 에 "`python3 script.py` stays allowed (ADR-0005)" 로 명시; settings.json ask 가 python/node 만 덮는 문제는 그대로 |
| `python3 -` | 0 | 2 |
| `curl -s -o 10_Domains/D1/x.md …` · `wget -O …` | 0 | 2 |
| `find 10_Domains -name "*.md" -delete` · `xargs rm < list.txt` · `patch -p0 < …` | 0 | 2 |
| `awk '{print > "10_Domains/D1/x.md"}' README.md` | 0 | 2 |
| `git apply …` · `git read-tree HEAD` | 0 | 2 |
| `echo hi > 00_Inbox/ai-drafts/ok.md` · `myelin doctor` | 0 | 0 (정상 허용) |
| `Write 00_Inbox/ai-drafts/x.sh` · `Write _patches/applied/fake.patch.md` | 0 | **0 (여전히 허용)** — H2 유효 |
| `Write 00_Inbox/ai-drafts/.hidden/x.md` | 0 | 2 |

재검증 후 H1 의 잔여 범위: AI 가 허용 디렉터리에 스크립트를 쓴 뒤 `bash|sh|python3|perl|ruby|node <path>` 로 실행하는 경로(ask 는 python/node/uv run python 만). H2(guard_write 확장자·`_patches/applied|rejected` 허용)를 닫으면 이 경로의 발판이 사라지므로 **H2 를 먼저 조치**하는 것이 가장 비용이 적다.

---

## 5. 참고 — 긍정 확인 사항 (금지 행위 점검 결과)

- Hub: 쓰기 8 엔드포인트 전부 `X-Myelin-Intent: user-click` 필수(`app.py`), UI 는 onClick 핸들러에서만 헤더 부착(`lib/api.ts:114-116`). GET 15종 + `POST /api/packs/validate` 는 Vault 트리 해시 불변(`test_reads_never_write`). Host/Origin 가드·정적 경로 이탈 방지 구현·테스트.
- MCP: 기본 도구 5종 읽기 전용, `write_draft` 는 설정+Level 로 **등록 자체**가 조건부, ai-drafts 외 생성 불가·덮어쓰기 불가.
- 디자인: `design/tokens.json` 단일 원천, 생성물 3종 동기화, 13 텍스트 쌍 ≥ 4.5:1, 네온 텍스트 0, web/src·gallery·theme 색 리터럴 0.
- Hook: 표준 라이브러리만, hooks.json 스키마(`args/timeout/onFailure/statusMessage`, `${CLAUDE_PLUGIN_ROOT}`, matcher 문법, stdin 필드명)는 2026-10-18 공식 문서와 일치.
- Commons: 공개 하드 게이트가 쓰기 전에 차단, 비식별 스캔 7종 + deid.yaml, 익명 지표 허용 키 집합, 세 외부 전송 경로 모두 확인 단계.
