import { useEffect, useState } from "react";
import { get, post, userPut, type PackRow } from "../lib/api";

const TEMPLATE = `pack: me.my-domain
version: 1.0.0
kind: personal
maintainer: me
requires: [myelin.core>=1.0]
domains:
  - id: MY-DOMAIN
    name: 내 관심 Domain
    accent: violet
    description: 무엇을 기록하는 Domain 인지 한 줄
    sub_mocs: [주제 1, 주제 2, 주제 3]
    note_types: [evergreen, lesson]
    classification_default: internal
`;

export default function Packs({ onChanged }: { onChanged: () => void }) {
  const [packs, setPacks] = useState<PackRow[]>([]);
  const [name, setName] = useState<string>("me.my-domain");
  const [text, setText] = useState<string>(TEMPLATE);
  const [check, setCheck] = useState<string>("");
  const load = () => get<PackRow[]>("/api/packs").then(setPacks);
  useEffect(() => { void load(); }, []);
  const open = async (p: PackRow) => { const src = await get<{ pack_yaml: string }>(`/api/packs/${p.name}`); setName(p.name); setText(src.pack_yaml); setCheck(""); };
  const validate = async () => { const r = await post<{ ok: boolean; error?: string; domains?: string[] }>("/api/packs/validate", { pack_yaml: text }); setCheck(r.ok ? `ok · domains ${r.domains?.join(", ")}` : `오류: ${r.error}`); };
  const save = async () => { try { const r = await userPut<{ commit: string }>(`/api/packs/${name}`, { pack_yaml: text }); setCheck(`저장됨 · commit ${r.commit.slice(0, 7)}`); await load(); onChanged(); } catch (e) { setCheck(`저장 실패: ${String(e)}`); } };
  return (
    <>
      <h1 className="hub-h1">Domain Packs</h1>
      <p className="hub-sub">Domain 은 코드가 아니라 선언(Pack). 개인 Pack(me.*) 은 여기서 편집하고, Org/Reference Pack 은 Registry 에서 온다.</p>
      <div className="hub-grid" data-testid="pack-list">
        {packs.map((p) => (
          <article key={p.name} className={"mx-card hub-stack" + (p.active ? " mx-ring--verified" : "")}>
            <div className="hub-row"><strong>{p.name}</strong><span className="mx-chip mx-chip--unverified">{p.kind} v{p.version}</span>{p.active && <span className="mx-chip mx-chip--verified">active</span>}</div>
            <div className="mx-muted">{p.description || p.maintainer}</div>
            <div className="hub-row">{p.domains.map((d) => <span key={d.id} className="mx-orb" data-accent={d.accent} style={{ width: 44, height: 44, fontSize: "var(--mx-font-size-xs)" }}>{d.id}</span>)}</div>
            <div className="hub-row"><button type="button" className="mx-btn" onClick={() => open(p)}>{p.editable ? "편집" : "보기"}</button></div>
          </article>
        ))}
      </div>
      <h2 className="hub-h2">Pack 편집기 · <span className="mx-mono">{name}</span></h2>
      <div className="hub-row" style={{ marginBottom: "var(--mx-space-3)" }}>
        <input className="mx-input" style={{ maxWidth: 320 }} value={name} onChange={(e) => setName(e.target.value)} aria-label="pack name" />
        <button type="button" className="mx-btn" onClick={() => { setName("me.my-domain"); setText(TEMPLATE); setCheck(""); }}>새 개인 Pack</button>
        <button type="button" className="mx-btn" onClick={validate}>검증</button>
        <button type="button" className="mx-btn-primary" onClick={save} data-testid="pack-save">저장 (commit)</button>
        {check && <span className={check.startsWith("오류") || check.startsWith("저장 실패") ? "mx-badge--blocked" : "mx-chip mx-chip--verified"}>{check}</span>}
      </div>
      <textarea className="hub-textarea" value={text} onChange={(e) => setText(e.target.value)} aria-label="pack.yaml" spellCheck={false} />
    </>
  );
}
