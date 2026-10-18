---
id: 20261018-1430-lit-ros2-executor-ai
type: literature
domain: [D2, D3]
status: draft
origin: claude
confidence: medium
classification: internal
share: false
source: ["https://docs.ros.org/en/rolling/Concepts/Intermediate/About-Executors.html"]
created: 2026-10-18
tags: [ros2, executor]
---
# Lit - ROS2 Executor (ai)

## 출처
- ROS 2 Documentation, "About Executors", Rolling (접근 2026-10-18)

## 핵심 주장 (인용 위치 포함)
1. SingleThreadedExecutor 는 콜백을 순차 처리하므로 긴 콜백이 전체 지연을 만든다 — §Executor types, 2문단
2. MultiThreadedExecutor 는 callback group 으로 상호배제를 제어한다 — §Callback groups

## 내 해석 · 반론
- (AI 초안: 사람이 채운다)

## 파생 원자 노트 후보
- [[WCET 예산은 측정값의 1.5배로 잡는다]]
