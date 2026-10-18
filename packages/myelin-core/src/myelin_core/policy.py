"""읽기 정책 — 어떤 노트를 Claude(클라우드)로 내보내면 안 되는가 (ADR-0002 Rev 2, ADR-0006).

Guard 스크립트(`resources/myelin_guard.py`)는 표준 라이브러리만 써야 해서 같은 규칙을 따로 구현한다.
두 구현이 같은 판정을 내리는지는 테스트(test_policy.py)가 확인한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from myelin_core.config import VaultConfig
from myelin_core.frontmatter import Classification

IP_DIR = "40_IP/"
IP_OPEN = "40_IP/candidates/"


@dataclass(frozen=True)
class ReadPolicy:
    ip_local: bool = True
    confidential_local: bool = True

    @classmethod
    def from_config(cls, cfg: VaultConfig) -> ReadPolicy:
        route = cfg.llm.route
        return cls(
            ip_local=route.get("40_IP/**", "local") != "claude",
            confidential_local=route.get("confidential", "local") != "claude",
        )

    def path_blocked(self, rel: str) -> bool:
        return self.ip_local and rel.startswith(IP_DIR) and not rel.startswith(IP_OPEN)

    def blocked(self, rel: str, classification: Classification | None) -> bool:
        if self.path_blocked(rel):
            return True
        return self.confidential_local and classification is Classification.CONFIDENTIAL
