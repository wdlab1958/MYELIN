# ADR-0016: Hub Team 모드 — 인증·역할·기밀 차단·접근 기록 (선택 기능)

- 상태: Accepted · 일자: 2026-11-26 · Phase: P10 (One Cycle 선결 과제, WBS 2.5.5)
- 근거: Hub 는 개인 PC(loopback) 전용이고 인증이 없어 팀이 검토 대기열을 함께 볼 방법이 없었다. `__main__` 은 "Team mode auth arrives in P7" 이라며 비-loopback 바인딩을 거부만 했다(Backlog "Team 모드 인증"). 정본 §4.4(Personal 모드 무인증), ADR-0009(쓰기 = 사람의 클릭), ADR-0011 §3(기밀은 로컬 세션만).

## 결정

1. **Personal 모드가 기본이며 바뀌지 않는다.** 인증 파일을 주지 않으면 loopback 전용·무인증으로 이전과 같다(회귀 테스트 `test_loopback_personal_mode_is_unchanged`).
2. **Team 모드는 인증 파일로만 켠다** — `myelin-hub --auth-file <yaml>` 또는 `$MYELIN_HUB_AUTH_FILE`. 파일은 `users[] {name, role, token_sha256}` 와 `allowed_hosts[]` 만 가진다(모르는 키 거부). 토큰 원문은 서버에 저장하지 않는다(SHA-256 만). 토큰은 256비트 난수(`myelin-hub --new-token <name> --role read|write`, 한 번만 출력)라 느린 해시는 쓰지 않는다. 파일이 group/others 에게 읽히면(POSIX mode & 077) 기동을 거부한다.
3. **비-loopback 바인딩은 세 조건이 모두 맞아야 한다** — ① 인증 파일 ② `allowed_hosts` ③ 암호화 채널(`--tls-cert/--tls-key` 또는 TLS 프록시 뒤임을 밝히는 `--behind-tls-proxy`). 하나라도 없으면 exit 2. 토큰이 평문으로 흐르는 구성은 기본값으로 만들 수 없다.
4. **인증** — 모든 `/api/*` 는 `Authorization: Bearer <token>`. 비교는 `hmac.compare_digest` 로 모든 사용자에 대해 수행한다(조기 종료 없음). 실패는 401 + `WWW-Authenticate: Bearer`, 같은 클라이언트의 연속 실패 20회/5분은 429. `/api/health` 만 열려 있고 Team 모드에서는 Vault 경로를 말하지 않는다.
5. **역할과 허용 목록** — Team 채널은 *검토 채널*이다. `read`: 허용 목록의 조회(`vault·stats·domains·notes·search·review·packs·patches·assistant`). `write`: 여기에 승격·기각·patch 적용·기각(ADR-0009 의 클릭 헤더는 그대로 필요). **소유자 작업은 채널에 없다**(403): settings·packs 저장·domains 추가·onboarding·commons·obsidian·git·doctor·guard 로그·OpenAPI. `mcp.expose_confidential` 같은 설정을 팀원이 바꿀 수 없게 하기 위해서다. 목록에 없는 경로는 거부(fail-closed) — 새 라우트는 명시적으로 올려야 열린다.
6. **기밀은 Team 채널로 나가지 않는다.** 규칙은 MCP 서버와 같다: `classification: confidential` 또는 `40_IP/**`. 목록·검색·검토 대기열·백링크에서 빠지고, 단건 조회·승격·기각·patch 는 **없는 노트와 같은 404** 다. 분류를 알 수 없는 노트(파싱 오류)는 숨긴다. 도우미 챗봇의 Vault 발췌도 EXTERNAL 로 취급해 기밀을 제외한다. 역할과 무관하다 — 소유자는 자기 기밀 노트를 Personal 모드에서 본다.
7. **철회는 재시작 없이 반영된다.** 인증 파일은 요청마다 바이트를 비교해 바뀌었으면 다시 읽는다(`LiveTeamAuth`). 줄을 지운 토큰은 다음 요청부터 401, 역할을 낮추면 다음 요청부터 403. 파일이 깨지거나 권한이 풀리거나 사라지면 고칠 때까지 모든 요청이 503 이다(옛 권한을 유지하지 않는다) — formal `mcp-config-revocation-stale` 과 같은 결함 유형을 처음부터 막는다.
8. **접근 기록** — `/api/*` 요청마다 `<Vault>/.myelin/hub-access.log` 에 JSON 한 줄(`ts·user·role·method·path·status·client`). 토큰·해시는 쓰지 않는다. 5 MB 에서 `.log.1` 로 한 번 돌린다. 런타임 디렉터리라 Vault 커밋에 들어가지 않는다.
9. **CSRF / CORS** — 인증이 쿠키가 아니라 헤더라 교차 사이트 요청이 세션을 탈 수 없다. CORS 헤더는 어떤 모드에서도 보내지 않는다. Host 와 Origin 은 loopback 또는 `allowed_hosts` 여야 한다(와일드카드 금지). 응답은 `Cache-Control: no-store`.
10. **웹 UI** — 401 을 받으면 토큰을 한 번 묻고 `sessionStorage`(탭 단위)에만 둔다.

## 결과
- 코드: `myelin_hub_api/team.py`(정책·설정·기록), `app.py`(`TeamGate` 미들웨어, 기밀 필터), `__main__.py`(바인딩 정책·토큰 발급).
- 테스트: `packages/myelin-hub/api/tests/test_team_mode.py` 38건 — 무인증 거부(22개 경로), 쓰기 무인증 시 Vault 불변, 역할, 소유자 작업 403, 기밀 미제공(목록·검색·단건·백링크·검토·도우미), 재분류 즉시 반영, 접근 기록, Host/Origin/CORS, 바인딩 정책, Personal 모드 불변.
- 위협 모델 T24.

## 남은 한계 (구현하지 않은 것)
- 사용자 관리 화면·토큰 만료·SSO 없음. 토큰 폐기는 인증 파일에서 줄을 지우면 된다.
- 실패 제한은 프로세스 메모리 기준이라 재시작하면 초기화된다. 프록시 뒤에서는 클라이언트 주소가 프록시 주소로 보인다.
- 여러 사람이 같은 Vault 에 쓰는 구조가 아니다 — 한 소유자의 Vault 를 팀이 검토하는 채널이다. "조직은 Vault 를 열람하지 않는다"(정본 Personal Ownership)는 소유자가 Team 모드를 켤 때에만 완화된다.
- 외부 침투 시험·부하 시험은 하지 않았다.
