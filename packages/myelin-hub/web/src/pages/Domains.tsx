import { useEffect, useState } from "react";
import { get, obsidianNew, obsidianOpen, type Domain, type NoteRow, type SearchHit, type VaultSummary } from "../lib/api";

export default function Domains({ vault }: { vault: VaultSummary }) {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [selected, setSelected] = useState<Domain | null>(null);
  const [notes, setNotes] = useState<NoteRow[]>([]);
  const [sub, setSub] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  useEffect(() => { void get<Domain[]>("/api/domains").then((d) => { setDomains(d); setSelected(d[0] ?? null); }); }, []);
  useEffect(() => {
    if (!selected) return;
    setSub(null); setHits(null);
    void get<NoteRow[]>(`/api/notes?domain=${encodeURIComponent(selected.id)}&limit=50`).then(setNotes);
  }, [selected]);
  const pickSub = async (name: string) => {
    if (sub === name) { setSub(null); setHits(null); return; }
    setSub(name);
    try { setHits(await get<SearchHit[]>(`/api/search?q=${encodeURIComponent(name)}&limit=20`)); } catch { setHits([]); }
  };
  const abs = (rel: string) => `${vault.root}/${rel}`;
  const subInfo = selected?.sub_moc_notes?.find((s) => s.name === sub);
  return (
    <>
      <h1 className="hub-h1">My Domains</h1>
      <p className="hub-sub">3+1 규칙 · Orb 를 누르면 Domain 상세, Sub-MOC 를 누르면 그 주제의 노트를 찾고 Obsidian 에서 MOC 를 연다.</p>
      <div className="hub-row" style={{ gap: "var(--mx-space-5)" }} data-testid="domain-map">
        {domains.map((d) => (
          <button key={d.id} type="button" className="mx-orb" data-accent={d.accent} aria-pressed={selected?.id === d.id} onClick={() => setSelected(d)} aria-label={`${d.id} ${d.name ?? ""}`} data-testid={`orb-${d.id}`}>{d.id}</button>
        ))}
      </div>
      {selected && (
        <article className="mx-card" style={{ marginTop: "var(--mx-space-6)" }} data-testid="domain-detail">
          <div className="hub-row"><h2 style={{ margin: 0 }}>{selected.id} · {selected.name}</h2><span className="mx-chip mx-chip--draft">{selected.role}</span></div>
          <p className="mx-muted">{selected.description} · Pack {selected.pack}</p>
          <div className="hub-row">
            <span className="mx-chip mx-chip--verified">verified {selected.verified}</span>
            <span className="mx-chip mx-chip--unverified">notes {selected.notes}</span>
            {selected.moc && <a className="mx-btn" href={obsidianOpen(abs(selected.moc))} title="Obsidian 에서 MOC 열기" data-testid="open-moc">Obsidian 에서 _MOC 열기</a>}
          </div>
          <h3>Sub-MOC <span className="mx-muted" style={{ fontWeight: 400, fontSize: "var(--mx-font-size-sm)" }}>— 누르면 주제별 노트 검색</span></h3>
          <div className="hub-row" data-testid="sub-moc-list">
            {(selected.sub_moc_notes ?? selected.sub_mocs?.map((n) => ({ name: n, path: "", note: null })) ?? []).map((s) => (
              <button key={s.name} type="button" className="mx-btn" aria-pressed={sub === s.name} onClick={() => pickSub(s.name)} data-testid="sub-moc">
                {s.name}{s.note ? " ●" : ""}
              </button>
            ))}
          </div>
          {sub && (
            <div className="mx-card" style={{ marginTop: "var(--mx-space-4)", boxShadow: "var(--mx-shadow-inset)" }} data-testid="sub-moc-panel">
              <div className="hub-row">
                <strong>{selected.id} - {sub}</strong>
                {subInfo?.note
                  ? <a className="mx-btn mx-btn-promote" href={obsidianOpen(abs(subInfo.note))}>Obsidian 에서 열기</a>
                  : <a className="mx-btn" href={obsidianNew(abs(subInfo?.path ?? `10_Domains/${selected.id}/${selected.id} - ${sub}.md`))} title="MOC 노트가 아직 없다 — Obsidian 에서 새로 만든다">Obsidian 에서 MOC 노트 만들기</a>}
                <span className="mx-muted">{subInfo?.note ? "MOC 노트 있음" : "MOC 노트 없음 (사람이 만든다)"}</span>
              </div>
              <h4 style={{ margin: "var(--mx-space-3) 0 var(--mx-space-2)" }}>"{sub}" 검색 결과 {hits ? hits.length : "…"}</h4>
              {hits && hits.length === 0 && <div className="mx-muted">아직 이 주제의 노트가 없다. /myelin:ingest 나 /myelin:distill 로 첫 노트를 만든다.</div>}
              {hits && hits.length > 0 && (
                <table className="mx-table"><thead><tr><th>제목</th><th>status</th><th>경로</th></tr></thead>
                  <tbody>{hits.map((h) => (
                    <tr key={h.path}><td><a href={obsidianOpen(abs(h.path))}>{h.title}</a></td><td><span className={"mx-chip " + chip(h)}>{h.status}</span></td><td className="mx-mono mx-muted">{h.path}</td></tr>
                  ))}</tbody></table>
              )}
            </div>
          )}
          <h3>노트</h3>
          <table className="mx-table"><thead><tr><th>제목</th><th>type</th><th>status</th><th>origin</th><th>created</th></tr></thead>
            <tbody>{notes.map((n) => (
              <tr key={n.path}><td><a href={obsidianOpen(abs(n.path))} title="Obsidian 에서 열기">{n.title}</a></td><td>{n.type}</td><td><span className={"mx-chip " + chip(n)}>{n.status}</span></td><td>{n.origin}</td><td className="mx-mono">{n.created}</td></tr>
            ))}</tbody></table>
        </article>
      )}
    </>
  );
}

export function chip(n: { status: string; origin: string }): string {
  if (n.status === "verified") return "mx-chip--verified";
  if (n.origin === "claude") return "mx-chip--ai";
  if (n.status === "draft") return "mx-chip--draft";
  return "mx-chip--unverified";
}
