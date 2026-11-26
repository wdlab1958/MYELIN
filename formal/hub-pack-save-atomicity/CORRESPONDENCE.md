# Correspondence: hub-pack-save-atomicity

Spec commit: `c29d83f` + 2026-11-18 패치(F5·F6). 줄 번호는 패치 적용 후 기준. 수정 전 `save_pack` 은 `c29d83f` 의 `service.py` 794~834행.

| Model element | Kind | Source (file:line) | Abstraction / Assumption |
|---|---|---|---|
| `content[r]` | variable | `PUT /api/packs/<name>` body `pack_yaml` — `packages/myelin-hub/api/src/myelin_hub_api/app.py:521-523` | A/B 두 값(A1) |
| `good` | variable | `myelin_core.packs.loader.load_pack` 의 판정 — 호출 `packages/myelin-hub/api/src/myelin_hub_api/service.py:1060` | 텍스트의 함수(A1) |
| `tmp` | variable | `<Vault>/packs/<name>/pack.yaml.tmp` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1047` | 요청 간 공유되는 고정 이름 |
| `final` | variable | `<Vault>/packs/<name>/pack.yaml` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1048` | |
| `backup[r]` | variable | 지역 변수 `backup` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:1039` | |
| `head` | variable | git HEAD 의 pack.yaml — `packages/myelin-hub/api/src/myelin_hub_api/service.py:395-399` _commit() | 한 파일 스냅샷(A4) |
| `lock` | variable | `HubService._write_lock` — `packages/myelin-hub/api/src/myelin_hub_api/service.py:124-135` `_serialised` | |
| `resp`, `saved`, `raceError` | history | HTTP 200/422/500 — `packages/myelin-hub/api/src/myelin_hub_api/app.py:252-306` (OSError→500) | |
| `WriteTmp(r)` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1011` (`@_serialised` 로 lock 획득), `packages/myelin-hub/api/src/myelin_hub_api/service.py:1047` | |
| `ReadBackup(r)` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1039` | 수정 후엔 쓰기 전에 읽지만 lock 아래라 순서 무관 |
| `Move(r)` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1048` `shutil.move(tmp, final)` | tmp 없으면 FileNotFoundError |
| `LoadRejected(r)` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1049-1062` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1068-1070` → `packages/myelin-hub/api/src/myelin_hub_api/service.py:1073-1117` _undo_pack_write() | |
| `LoadOkCommit(r)` | action | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1063-1067` | |
| `LoadOkCommitFails(r)` | action (env) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1063-1070`, 복원 `packages/myelin-hub/api/src/myelin_hub_api/service.py:1073-1117` | `Rollback` 토글 |
| `Serialised` | constant (fix F5) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1011` | `evidence/patches/F5-F6-save-pack-serialised-atomic.diff` |
| `Rollback` | constant (fix F6) | `packages/myelin-hub/api/src/myelin_hub_api/service.py:1068-1070`, `packages/myelin-hub/api/src/myelin_hub_api/service.py:1073-1117` | 같은 diff |
| `P4_DiskLoadable` | invariant | ← `packages/myelin-hub/api/src/myelin_hub_api/service.py:1012-1018`, `docs/adr/0009-hub-write-policy.md:9` | 동결 |
| `P5_OkMeansSaved` | invariant | ← `packages/myelin-hub/web/src/pages/Packs.tsx:41`, `docs/adr/0009-hub-write-policy.md:9` | 동결 |
| `P6_AllOrNothing` | invariant | ← `packages/myelin-hub/api/src/myelin_hub_api/service.py:304-310`, `docs/adr/0009-hub-write-policy.md:9` | 동결 |
| `P7_NoRaceError` | invariant | ← `packages/myelin-hub/api/src/myelin_hub_api/service.py:124-128` | 동결 |
