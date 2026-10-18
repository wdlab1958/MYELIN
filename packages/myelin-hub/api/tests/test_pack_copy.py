"""Hub Pack editor, copy-as-personal: sidecar files (taxonomy/templates) must come along."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import CLICK


def _as_personal(text: str, slug: str) -> str:
    text = re.sub(r"^pack:.*$", f"pack: me.{slug}", text, flags=re.M)
    text = re.sub(r"^kind:.*$", "kind: personal", text, flags=re.M)
    return re.sub(r"^maintainer:.*$", "maintainer: me", text, flags=re.M)


def test_copy_reference_pack_as_personal(client: TestClient, vault_root: Path) -> None:
    src = client.get("/api/packs/brian.physical-ai").json()["pack_yaml"]
    body = _as_personal(src, "physical-ai")
    # without copy_from the referenced taxonomy.yaml/templates do not exist → 422, nothing left
    r = client.put("/api/packs/me.physical-ai", headers=CLICK, json={"pack_yaml": body})
    assert r.status_code == 422 and "does not exist" in r.text
    assert not (vault_root / "packs/me.physical-ai/pack.yaml").exists()
    # with copy_from the sidecars are copied (pack.yaml excluded) and the pack loads + commits
    r = client.put(
        "/api/packs/me.physical-ai",
        headers=CLICK,
        json={"pack_yaml": body, "copy_from": "brian.physical-ai"},
    )
    assert r.status_code == 200, r.text
    pdir = vault_root / "packs/me.physical-ai"
    assert (pdir / "taxonomy.yaml").is_file() and (pdir / "templates").is_dir()
    assert (pdir / "pack.yaml").read_text(encoding="utf-8") == body
    packs = {p["name"]: p for p in client.get("/api/packs").json()}
    assert packs["me.physical-ai"]["editable"]
    # one click = one commit that includes the sidecars: working tree stays clean
    assert client.get("/api/git/status").json()["clean"] is True
    # unknown source → 404; bad names never escape <vault>/packs
    r = client.put(
        "/api/packs/me.z",
        headers=CLICK,
        json={"pack_yaml": _as_personal(src, "z"), "copy_from": "nope"},
    )
    assert r.status_code == 404
    assert client.put(
        "/api/packs/me.%2e%2e", headers=CLICK, json={"pack_yaml": body}
    ).status_code in (
        403,
        422,
    )
