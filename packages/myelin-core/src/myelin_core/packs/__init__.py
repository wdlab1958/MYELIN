"""Pack discovery, loading, validation and dependency resolution.

정본 §5 — Thin Additive Routing Shell: Domain은 데이터(Pack)이며 코드가 아니다.
"""

from myelin_core.packs.loader import (
    LoadedPack,
    PackError,
    PackRegistry,
    discover_packs,
    load_pack,
    resolve_packs,
)

__all__ = [
    "LoadedPack",
    "PackError",
    "PackRegistry",
    "discover_packs",
    "load_pack",
    "resolve_packs",
]
