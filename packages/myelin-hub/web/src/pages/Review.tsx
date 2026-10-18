import { useCallback, useEffect, useState } from "react";
import { get, userPost, type NoteRow, type PatchRow } from "../lib/api";

export default function Review({ onChanged }: { onChanged: () => void }) {
  const [drafts, setDrafts] = useState<NoteRow[]>([]);
  const [patches, setPatches] = useState<PatchRow[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [justPromoted, setJustPromoted] = useState<string | null>(null);
  const load = useCallback(() => get<{ drafts: NoteRow[]; patches: PatchRow[] }>("/api/review").then((r) => { setDrafts(r.drafts); setPatches(r.patches); }), []);
  useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<{ commit?: string; path?: string }>, label: string) => {
    try {
      const r = await fn();
      setMsg(`${label} · commit ${r.commit?.slice(0, 7) ?? ""}`);
      if (label.startsWith("Promote") && r.path) setJustPromoted(r.path);
      await load(); onChanged();
    } catch (e) { setMsg(`실패: ${String(e)}`); }
  };

  return (
    <>
      <h1 className="hub-h1">Inbox / Review Gate</h1>
      <p className="hub-sub">AI 초안과 패치 제안. 승격·적용은 여기서 사람의 클릭으로만 일어나고 git commit 으로 기록됩니다.</p>
      {msg && <div className={"mx-card hub-toast " + (msg.startsWith("실패") ? "" : "mx-ring--verified is-myelinating")} role="status" data-testid="review-toast">{msg}</div>}
      {justPromoted && <div className="mx-card mx-ring--verified is-myelinating" data-testid="promoted-card"><span className="mx-chip mx-chip--verified">verified</span> <strong>myelinated</strong> · <span className="mx-mono">{justPromoted}</span></div>}
      <h2 className="hub-h2">AI 초안 ({drafts.length})</h2>
      <div className="mx-card" style={{ padding: "0 var(--mx-space-4)" }} data-testid="draft-list">
        {drafts.length === 0 && <div className="mx-review-row mx-muted">대기 중인 초안이 없습니다.</div>}
        {drafts.map((d) => (
          <div className="mx-review-row" key={d.path} data-testid="draft-row">
            {d.doctor_ok === false ? <span className="mx-badge--blocked">invalid</span> : <span className="mx-chip mx-chip--ai">ai-draft</span>}
            <div><div className="mx-review-row__title">{d.title}</div><div className="mx-review-row__meta">{d.type} · {d.domains.join(", ") || "domain 없음"} · {d.created}{d.error ? ` · ${d.error}` : ""}</div></div>
            <div className="hub-row">
              <button type="button" className="mx-btn mx-btn-promote" disabled={d.doctor_ok === false} onClick={() => act(() => userPost(`/api/review/promote/${encodeURI(d.path)}`), `Promote ${d.title}`)} data-testid="promote">Promote</button>
              <button type="button" className="mx-btn" onClick={() => act(() => userPost(`/api/review/reject/${encodeURI(d.path)}`), `Reject ${d.title}`)} data-testid="reject">Reject</button>
            </div>
          </div>
        ))}
      </div>
      <h2 className="hub-h2">패치 제안 ({patches.length})</h2>
      <div className="mx-card" style={{ padding: "0 var(--mx-space-4)" }} data-testid="patch-list">
        {patches.length === 0 && <div className="mx-review-row mx-muted">_patches/ 가 비어 있습니다.</div>}
        {patches.map((p) => (
          <div className="mx-review-row" key={p.file}>
            {p.error ? <span className="mx-badge--blocked">invalid</span> : <span className={"mx-chip " + (p.status === "proposed" ? "mx-chip--draft" : "mx-chip--unverified")}>{p.status}</span>}
            <div><div className="mx-review-row__title">{p.file}</div><div className="mx-review-row__meta">{p.error ?? `${p.kind} → ${p.target} · /${p.skill} · ${p.rationale}`}</div>{p.sections && <pre className="hub-pre">{Object.entries(p.sections).map(([k, v]) => `## ${k}\n${v}`).join("\n")}</pre>}</div>
            <div className="hub-row">
              <button type="button" className="mx-btn mx-btn-promote" disabled={!!p.error || p.status !== "proposed"} onClick={() => act(() => userPost(`/api/patches/${encodeURIComponent(p.file)}/apply`), `Apply ${p.file}`)}>Apply</button>
              <button type="button" className="mx-btn" disabled={!!p.error || p.status !== "proposed"} onClick={() => act(() => userPost(`/api/patches/${encodeURIComponent(p.file)}/reject`), `Reject ${p.file}`)}>Reject</button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
