import { useState } from "react";
import { userPut, type VaultSummary } from "../lib/api";

export default function Settings({ vault, onChanged }: { vault: VaultSummary; onChanged: () => void }) {
  const [level, setLevel] = useState<number>(vault.level ?? 1);
  const [writeDraft, setWriteDraft] = useState<boolean>(vault.mcp?.write_draft ?? false);
  const [expose, setExpose] = useState<boolean>(vault.mcp?.expose_confidential ?? false);
  const [msg, setMsg] = useState<string>("");
  const save = async () => {
    try {
      const current = await (await fetch("/api/settings")).json();
      const next = { ...current, level, mcp: { write_draft: writeDraft, expose_confidential: expose } };
      const r = await userPut<{ commit: string }>("/api/settings", next);
      setMsg(`저장됨 · commit ${r.commit.slice(0, 7)}`); onChanged();
    } catch (e) { setMsg(`저장 실패: ${String(e)}`); }
  };
  return (
    <>
      <h1 className="hub-h1">Settings</h1>
      <p className="hub-sub">myelin.yaml · 사람만 바꾼다. 저장은 git commit.</p>
      <div className="hub-grid">
        <article className="mx-card hub-stack">
          <strong>Owner</strong>
          <div>{vault.owner?.name} · {vault.owner?.team} · <span className="mx-mono">{vault.owner?.email}</span></div>
          <strong>Domains</strong>
          <div className="hub-row">{Object.entries(vault.domains ?? {}).map(([id, role]) => <span key={id} className="mx-chip mx-chip--draft">{id} · {role}</span>)}</div>
          <strong>Packs</strong>
          <div className="mx-mono mx-muted">{vault.packs?.join(", ")}</div>
        </article>
        <article className="mx-card hub-stack">
          <strong>Level — 단계적 개방</strong>
          <div className="hub-row" role="radiogroup" aria-label="level">
            {[0, 1, 2, 3].map((l) => <button key={l} type="button" className="mx-btn" aria-pressed={level === l} onClick={() => setLevel(l)} data-testid={`level-${l}`}>{l} · {["read-only", "drafts", "link-patch", "scheduled"][l]}</button>)}
          </div>
          <strong>MCP</strong>
          <label className="hub-row"><input type="checkbox" checked={writeDraft} onChange={(e) => setWriteDraft(e.target.checked)} /> write_draft 도구 등록 (level ≥ 1)</label>
          <label className="hub-row"><input type="checkbox" checked={expose} onChange={(e) => setExpose(e.target.checked)} /> confidential 노출 (로컬 LLM 세션에서만)</label>
          <div className="hub-row"><button type="button" className="mx-btn-primary" onClick={save} data-testid="settings-save">저장 (commit)</button>{msg && <span className={msg.startsWith("저장 실패") ? "mx-badge--blocked" : "mx-chip mx-chip--verified"} data-testid="settings-msg">{msg}</span>}</div>
        </article>
        <article className="mx-card hub-stack">
          <strong>Skill 개방 (현재 Level {vault.level})</strong>
          <table className="mx-table"><thead><tr><th>skill</th><th>min</th><th>enabled</th><th>scope</th></tr></thead>
            <tbody>{vault.skills?.map((s) => <tr key={s.skill}><td className="mx-mono">{s.skill}</td><td>{s.min_level}</td><td>{s.enabled ? <span className="mx-chip mx-chip--verified">yes</span> : <span className="mx-chip mx-chip--unverified">no</span>}</td><td className="mx-mono mx-muted">{s.write_scope}</td></tr>)}</tbody></table>
        </article>
      </div>
    </>
  );
}
