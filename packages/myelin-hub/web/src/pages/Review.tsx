import { useCallback, useEffect, useState } from "react";
import { get, refPath, userPost, type Candidate, type NoteRow, type PatchPlan, type PatchRow, type VaultSummary } from "../lib/api";

export default function Review({ vault, onChanged }: { vault: VaultSummary; onChanged: () => void }) {
  const commonsReady = vault.commons?.configured ?? false;
  const [drafts, setDrafts] = useState<NoteRow[]>([]);
  const [patches, setPatches] = useState<PatchRow[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [justPromoted, setJustPromoted] = useState<string | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [plans, setPlans] = useState<Record<string, PatchPlan | { error: string }>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [bodies, setBodies] = useState<Record<string, string>>({}); // 읽음 확인: Promote 는 본문을 연 뒤에만
  const [withPr, setWithPr] = useState<Record<string, boolean>>({});
  const openBody = async (path: string) => {
    if (bodies[path] !== undefined) { const next = { ...bodies }; delete next[path]; setBodies(next); return; }
    try { const n = await get<{ body: string }>(`/api/notes/${refPath(path)}`); setBodies({ ...bodies, [path]: n.body }); }
    catch (e) { setBodies({ ...bodies, [path]: `(본문을 읽을 수 없다: ${String(e)})` }); }
  };
  const publish = async (c: Candidate) => {
    const pr = !!withPr[c.path];
    try {
      const r = await userPost<{ commit: string; branch: string; pushed: boolean; pr_url: string | null; next_step?: string }>(`/api/commons/publish/${refPath(c.path)}`, { confirmed: true, push: pr, pr });
      setMsg(`Commons 제안 ${c.title} · commit ${r.commit.slice(0, 7)} · ${r.branch}` + (r.pr_url ? ` · PR ${r.pr_url}` : r.next_step ? ` · 다음: ${r.next_step}` : ""));
      await load(); onChanged();
    } catch (e) { setMsg(`실패: ${String(e)}`); }
  };
  const load = useCallback(() => get<{ drafts: NoteRow[]; patches: PatchRow[] }>("/api/review").then((r) => { setDrafts(r.drafts); setPatches(r.patches); }), []);
  useEffect(() => { void load(); void get<Candidate[]>("/api/commons/candidates").then(setCands).catch(() => setCands([])); }, [load]);

  const preview = async (file: string) => {
    try { const p = await get<PatchPlan>(`/api/patches/${encodeURIComponent(file)}/preview`); setPlans({ ...plans, [file]: p }); }
    catch (e) { setPlans({ ...plans, [file]: { error: String(e) } }); }
  };
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
            <div>
              <div className="mx-review-row__title">{d.title}</div>
              <div className="mx-review-row__meta">{d.type} · {d.domains.join(", ") || "domain 없음"} · {d.created}{d.error ? ` · ${d.error}` : ""}</div>
              {bodies[d.path] !== undefined && <pre className="hub-pre" style={{ maxHeight: 320, overflow: "auto" }} data-testid="draft-body">{bodies[d.path]}</pre>}
            </div>
            <div className="hub-row">
              <button type="button" className="mx-btn" disabled={d.doctor_ok === false} onClick={() => openBody(d.path)} aria-pressed={bodies[d.path] !== undefined} data-testid="draft-read">{bodies[d.path] !== undefined ? "닫기" : "내용 읽기"}</button>
              <button type="button" className="mx-btn mx-btn-promote" disabled={d.doctor_ok === false || bodies[d.path] === undefined} title={bodies[d.path] === undefined ? "승격은 사람이 읽은 뒤에만 — 먼저 내용을 읽는다" : ""} onClick={() => act(() => userPost(`/api/review/promote/${refPath(d.path)}`), `Promote ${d.title}`)} data-testid="promote">Promote</button>
              <button type="button" className="mx-btn" onClick={() => act(() => userPost(`/api/review/reject/${refPath(d.path)}`), `Reject ${d.title}`)} data-testid="reject">Reject</button>
            </div>
          </div>
        ))}
      </div>
      <h2 className="hub-h2">패치 제안 ({patches.length})</h2>
      <div className="mx-card" style={{ padding: "0 var(--mx-space-4)" }} data-testid="patch-list">
        {patches.length === 0 && <div className="mx-review-row mx-muted">_patches/ 가 비어 있습니다.</div>}
        {patches.map((p) => {
          const plan = plans[p.file];
          const ready = plan && !("error" in plan) && plan.ok;
          return (
          <div className="mx-review-row" key={p.file} data-testid="patch-row">
            {p.error ? <span className="mx-badge--blocked">invalid</span> : <span className={"mx-chip " + (p.status === "proposed" ? "mx-chip--draft" : "mx-chip--unverified")}>{p.status}</span>}
            <div>
              <div className="mx-review-row__title">{p.file}</div>
              <div className="mx-review-row__meta">{p.error ?? `${p.kind}${p.under ? ` (under ${p.under})` : ""} → ${p.target} · /${p.skill} · ${p.rationale}`}</div>
              {plan && "error" in plan && <div className="mx-review-row__meta">✗ {plan.error}</div>}
              {plan && !("error" in plan) && plan.issues.map((i) => <div key={i} className="mx-review-row__meta">✗ {i}</div>)}
              {plan && !("error" in plan) && plan.ok && <pre className="hub-pre" data-testid="patch-diff">{plan.diff || "(변경 없음)"}</pre>}
            </div>
            <div className="hub-row">
              <button type="button" className="mx-btn" disabled={!!p.error} onClick={() => preview(p.file)} data-testid="patch-preview">미리보기</button>
              <button type="button" className="mx-btn mx-btn-promote" disabled={!ready} title={ready ? "" : "먼저 미리보기로 검사 결과를 확인한다"} onClick={() => act(() => userPost(`/api/patches/${encodeURIComponent(p.file)}/apply`, { digest: (plan as PatchPlan).digest }), `Apply ${p.file}`)} data-testid="patch-apply">Apply</button>
              <button type="button" className="mx-btn" disabled={!!p.error || p.status !== "proposed"} onClick={() => act(() => userPost(`/api/patches/${encodeURIComponent(p.file)}/reject`), `Reject ${p.file}`)}>Reject</button>
            </div>
          </div>
          );
        })}
      </div>
      <h2 className="hub-h2">Commons 후보 ({cands.length})</h2>
      <p className="hub-sub">share: true 인 verified 노트. 비식별 검사를 통과하고 사람이 확인한 것만 Commons 브랜치에 제안된다 (ADR-0010).</p>
      <p className="hub-sub" data-testid="commons-identity">두 가지 정체성 — Commons 노트에는 <strong>작성자 이름(author)과 원 노트 id 가 실명으로</strong> 남아 기여가 평판이 된다. 반면 Settings 의 익명 지표(opt-in)는 owner 해시와 개수만 보내며 실명·제목·본문은 포함하지 않는다.</p>
      {!commonsReady && cands.length > 0 && <div className="mx-card" style={{ marginBottom: "var(--mx-space-3)" }} data-testid="commons-notice"><span className="mx-badge--blocked">설정 필요</span> {vault.commons?.error ?? "Commons clone 이 설정되지 않았다"} — Settings › Commons 에서 로컬 clone 경로를 지정한다.</div>}
      <div className="mx-card" style={{ padding: "0 var(--mx-space-4)" }} data-testid="commons-list">
        {cands.length === 0 && <div className="mx-review-row mx-muted">share: true 로 표시된 노트가 없습니다.</div>}
        {cands.map((c) => (
          <div className="mx-review-row" key={c.path} data-testid="commons-row">
            {c.ok ? <span className="mx-chip mx-chip--verified">publishable</span> : <span className="mx-badge--blocked">blocked</span>}
            <div>
              <div className="mx-review-row__title">{c.title}</div>
              <div className="mx-review-row__meta">{c.path}</div>
              {c.reasons.map((r) => <div key={r} className="mx-review-row__meta">✗ {r}</div>)}
              {c.deid_hits.map((h, i) => <div key={i} className="mx-review-row__meta">✗ 비식별 {h.kind} (line {h.line}): {h.excerpt}</div>)}
              {c.ok && <label className="hub-row mx-review-row__meta"><input type="checkbox" checked={!!confirmed[c.path]} onChange={(e) => setConfirmed({ ...confirmed, [c.path]: e.target.checked })} /> 고객명·IP·기밀이 없음을 확인했습니다</label>}
              {c.ok && <label className="hub-row mx-review-row__meta"><input type="checkbox" checked={!!withPr[c.path]} onChange={(e) => setWithPr({ ...withPr, [c.path]: e.target.checked })} data-testid="commons-pr" /> push 하고 PR 을 만든다 (gh 필요 · 끄면 로컬 브랜치까지만)</label>}
            </div>
            <div className="hub-row">
              <button type="button" className="mx-btn mx-btn-promote" disabled={!commonsReady || !c.ok || !confirmed[c.path]} title={commonsReady ? "" : "Settings › Commons 에서 로컬 clone 을 먼저 지정한다"} onClick={() => publish(c)} data-testid="commons-publish">Commons 제안</button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
