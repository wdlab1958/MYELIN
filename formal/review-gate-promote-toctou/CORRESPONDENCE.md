# Correspondence: review-gate-promote-toctou

Spec commit: `c29d83f` + 2026-11-18 패치(F4). 줄 번호는 패치 적용 후 기준.

| Model element | Kind | Source (file:line) | Abstraction / Assumption |
|---|---|---|---|
| `draft[n]` | variable | `<Vault>/00_Inbox/ai-drafts/<n>.md` — 읽는 곳 `packages/myelin-hub/api/src/myelin_hub_api/service.py:685` | 파일 바이트 = 버전 번호(A1) |
| `shown[n]` | variable | `packages/myelin-hub/web/src/pages/Review.tsx:13` `bodies` state | 화면에 보이는 본문 |
| `pending[n]` | variable | `packages/myelin-hub/web/src/pages/Review.tsx:14` `digests` state → Promote 요청 body `{ digest }` (`packages/myelin-hub/web/src/pages/Review.tsx:79`), `packages/myelin-hub/api/src/myelin_hub_api/app.py:151-154 PromoteBody` | 클릭이 실어 보내는 "읽은 내용"(A4) |
| `verified[n]` | variable | `<Vault>/10_Domains/<D>/<n>.md` — 쓰는 곳 `packages/myelin-hub/api/src/myelin_hub_api/service.py:662-768` promote() | status verified 로 쓰인 내용 |
| `approved[n]`, `refused` | history | — | 속성 판정용 |
| `WriterRewrite(n)` | action (env) | `plugin/hooks/guard_bash.py:1-5`, `docs/adr/0009-hub-write-policy.md:14` | Hub 밖의 프로세스. 횟수만 `MaxVer` 로 제한 |
| `BrowserRead(n)` | action | `packages/myelin-hub/web/src/pages/Review.tsx:16-20` openBody() → `packages/myelin-hub/api/src/myelin_hub_api/app.py:389-393` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:587-606` note() | 본문·digest 를 같은 바이트에서(A3) |
| `HumanClick(n)` | action | `packages/myelin-hub/web/src/pages/Review.tsx:79` (본문을 연 뒤에만 활성) | |
| `HubPromote(n)` | action | `packages/myelin-hub/api/src/myelin_hub_api/app.py:472-475` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:662-768` promote(): 한 번 읽기(663), digest 검사→409(664-668), 파싱·검증, 대상 쓰기, 원본 unlink, commit | 한 action(A2); 다른 거부 사유 생략(A5) |
| `DigestCheck` | constant (fix) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:686-690`; digest 정의 `packages/myelin-hub/api/src/myelin_hub_api/service.py:103-106` content_digest() | `evidence/patches/F4-promote-digest.diff` |
| `P3_VerifiedIsWhatWasRead` | invariant | `tla/Properties.tla` ← `docs/adr/0009-hub-write-policy.md:4`, `docs/adr/0009-hub-write-policy.md:14`, `packages/myelin-hub/web/src/pages/Review.tsx:13`, `packages/myelin-hub/web/src/pages/Review.tsx:79` | 프로토콜 수준(동결) |

## TLA+ ↔ Lean
| TLA+ | Lean (`lean/ReviewGate/`) |
|---|---|
| `Spec.tla` 변수 5개 (`refused` 제외) | `System.lean` `State` |
| `WriterRewrite` / `BrowserRead` / `HumanClick` | `Step.rewrite` / `Step.read` / `Step.click` |
| `HubPromote` 의 세 분기 (승격 / 409 / 404) | `Step.promote` / `Step.refuse` / `Step.gone` |
| `DigestCheck` | `check : Bool` |
| `P3_VerifiedIsWhatWasRead` | `Properties.lean` `VerifiedIsWhatWasRead`, 정리 `verified_is_what_was_read` |
| `MC_bug.cfg` 반례 | 정리 `unpatched_violates` |
| `MC_sanity.cfg` | 정리 `patched_can_promote` |

Lean 쪽이 더 일반적인 점: `rewrite` 가 임의의 새 내용으로(이전 내용으로 되돌아가는 것 포함) 바꿀 수 있고, 초기 초안이 임의이며, `Note` 가 임의 타입이다. TLA+ 는 버전이 단조 증가한다.
