---
id: 20261126-0900-rediagnosis-rd-sample-001
type: checklist
domain: []
status: draft
origin: claude
confidence: low
classification: internal
share: false
source: ["onecycle-request:rd-sample-001"]
created: 2026-11-26
tags: [onecycle, argus, rediagnosis, simulated]
source_platform: argus
simulated: true
---
# 재진단 요청 rd-sample-001 — 로그인 실패 급증 캠페인

> ARGUS 가 만든 `onecycle.rediagnosis-request/v1` 파일의 Markdown 사본(가상의 표본)이다.

- 심각도: medium · 경보: `campaign-sample-001` · MITRE: TA0006, T1110
- 요청 단계: ssc
- 근거: 인증 통제(다중 인증)가 이행됐는지 재평가가 필요하다.

## 확인할 것
- [ ] SSC 에서 재평가 요청을 승인했는가
- [ ] 재평가 결과 finding 의 `links.upstream` 에 이 요청의 경보 id 가 들어 있는가
