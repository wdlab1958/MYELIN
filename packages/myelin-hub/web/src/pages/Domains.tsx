import { useEffect, useState } from "react";
import { get, type Domain, type NoteRow } from "../lib/api";

export default function Domains() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [selected, setSelected] = useState<Domain | null>(null);
  const [notes, setNotes] = useState<NoteRow[]>([]);
  useEffect(() => { void get<Domain[]>("/api/domains").then((d) => { setDomains(d); setSelected(d[0] ?? null); }); }, []);
  useEffect(() => {
    if (!selected) return;
    void get<NoteRow[]>(`/api/notes?domain=${encodeURIComponent(selected.id)}&limit=50`).then(setNotes);
  }, [selected]);
  return (
    <>
      <h1 className="hub-h1">My Domains</h1>
      <p className="hub-sub">3+1 규칙 · Orb 를 누르면 Domain Map 과 MOC 로.</p>
      <div className="hub-row" style={{ gap: "var(--mx-space-5)" }} data-testid="domain-map">
        {domains.map((d) => (
          <button key={d.id} type="button" className="mx-orb" data-accent={d.accent} aria-pressed={selected?.id === d.id} onClick={() => setSelected(d)} aria-label={`${d.id} ${d.name ?? ""}`} data-testid={`orb-${d.id}`}>{d.id}</button>
        ))}
      </div>
      {selected && (
        <article className="mx-card" style={{ marginTop: "var(--mx-space-6)" }} data-testid="domain-detail">
          <div className="hub-row"><h2 style={{ margin: 0 }}>{selected.id} · {selected.name}</h2><span className="mx-chip mx-chip--draft">{selected.role}</span></div>
          <p className="mx-muted">{selected.description} · Pack {selected.pack}</p>
          <div className="hub-row"><span className="mx-chip mx-chip--verified">verified {selected.verified}</span><span className="mx-chip mx-chip--unverified">notes {selected.notes}</span>{selected.moc && <span className="mx-mono mx-muted">{selected.moc}</span>}</div>
          <h3>Sub-MOC</h3>
          <div className="hub-row">{selected.sub_mocs?.map((s) => <span key={s} className="mx-btn" style={{ cursor: "default" }}>{s}</span>)}</div>
          <h3>노트</h3>
          <table className="mx-table"><thead><tr><th>제목</th><th>type</th><th>status</th><th>origin</th><th>created</th></tr></thead>
            <tbody>{notes.map((n) => (
              <tr key={n.path}><td>{n.title}</td><td>{n.type}</td><td><span className={"mx-chip " + chip(n)}>{n.status}</span></td><td>{n.origin}</td><td className="mx-mono">{n.created}</td></tr>
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
