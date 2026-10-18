import { useEffect, useState } from "react";
import { get, userPost, type PackRow } from "../lib/api";

/** Same inputs and validation as `myelin init` (MyelinConfig + init_vault on the server). */
export default function Onboarding({ root, onDone }: { root: string; onDone: () => void }) {
  const [packs, setPacks] = useState<PackRow[]>([]);
  const [form, setForm] = useState({ name: "", team: "", email: "", primary: "", research: "", growth: "", level: 1 });
  const [msg, setMsg] = useState<string>("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void get<PackRow[]>("/api/packs").then(setPacks); }, []);
  const domains = packs.flatMap((p) => p.domains.map((d) => ({ ...d, pack: p.name })));
  const packFor = (id: string) => domains.find((d) => d.id === id)?.pack;
  const submit = async () => {
    setBusy(true); setMsg("");
    try {
      const chosen = [form.primary, form.research, form.growth].filter(Boolean);
      const packList = Array.from(new Set(chosen.map(packFor).filter((x): x is string => !!x)));
      await userPost("/api/onboarding", { ...form, research: form.research || null, growth: form.growth || null, packs: packList });
      onDone();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const Select = ({ k, label, required }: { k: "primary" | "research" | "growth"; label: string; required?: boolean }) => (
    <label className="hub-stack" style={{ gap: "var(--mx-space-1)" }}>
      <span className="mx-muted">{label}{required ? " *" : ""}</span>
      <select className="mx-input" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`select-${k}`}>
        <option value="">{required ? "선택" : "(없음)"}</option>
        {domains.map((d) => <option key={d.id} value={d.id}>{d.id} · {d.name} [{d.pack}]</option>)}
      </select>
    </label>
  );
  return (
    <main className="hub-main" style={{ maxWidth: 720 }}>
      <h1 className="hub-h1">MYELIN 시작하기</h1>
      <p className="hub-sub">15분 안에 첫 verified 노트까지. 3+1 규칙 — Primary(업무 근간) · Research(연구) · Growth(성장). Vault: <span className="mx-mono">{root}</span></p>
      <div className="mx-card hub-stack" data-testid="onboarding">
        <label className="hub-stack" style={{ gap: "var(--mx-space-1)" }}><span className="mx-muted">이름 *</span><input className="mx-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="input-name" /></label>
        <div className="hub-row">
          <label className="hub-stack" style={{ gap: "var(--mx-space-1)", flex: 1 }}><span className="mx-muted">팀</span><input className="mx-input" value={form.team} onChange={(e) => setForm({ ...form, team: e.target.value })} /></label>
          <label className="hub-stack" style={{ gap: "var(--mx-space-1)", flex: 1 }}><span className="mx-muted">이메일</span><input className="mx-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        </div>
        <Select k="primary" label="Primary — 지금 내 업무의 근간" required />
        <Select k="research" label="Research — 스스로 파고드는 주제" />
        <Select k="growth" label="Growth — 1~2년 안에 갖추고 싶은 역량" />
        <div className="hub-row" role="radiogroup" aria-label="level">
          <span className="mx-muted">Level</span>
          {[0, 1, 2, 3].map((l) => <button key={l} type="button" className="mx-btn" aria-pressed={form.level === l} onClick={() => setForm({ ...form, level: l })}>{l}</button>)}
        </div>
        <div className="hub-row">
          <button type="button" className="mx-btn-primary" disabled={busy || !form.name || !form.primary} onClick={submit} data-testid="onboarding-submit">Vault 만들기</button>
          {msg && <span className="mx-badge--blocked" data-testid="onboarding-error">{msg}</span>}
        </div>
      </div>
    </main>
  );
}
