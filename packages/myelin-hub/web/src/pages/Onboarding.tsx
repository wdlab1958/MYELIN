import { useEffect, useState } from "react";
import { get, userPost, type PackRow } from "../lib/api";

type Custom = { id: string; name: string; description: string; accent: string; sub_mocs: string };
const KIND_LABEL: Record<string, string> = { org: "조직 업무 Pack (A3)", reference: "참고용 지형도 (Reference — 선택 사항)", personal: "개인 Pack", core: "Core" };
const KIND_ORDER = ["org", "personal", "reference"];

/** Same inputs and validation as `myelin init` (MyelinConfig + init_vault on the server).
 *  A new user may define their own domains here; Brian's reference pack is only one of the options. */
export default function Onboarding({ root, onDone }: { root: string; onDone: () => void }) {
  const [packs, setPacks] = useState<PackRow[]>([]);
  const [form, setForm] = useState({ name: "", team: "", email: "", primary: "", research: "", growth: "", level: 1 });
  const [custom, setCustom] = useState<Custom[]>([]);
  const [draft, setDraft] = useState<Custom>({ id: "", name: "", description: "", accent: "violet", sub_mocs: "" });
  const [msg, setMsg] = useState<string>("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void get<PackRow[]>("/api/packs").then(setPacks); }, []);

  const packDomains = packs.filter((p) => p.kind !== "core").flatMap((p) => p.domains.map((d) => ({ ...d, pack: p.name, kind: p.kind })));
  const customDomains = custom.map((c) => ({ id: c.id, name: c.name, accent: c.accent, sub_mocs: c.sub_mocs.split(",").map((s) => s.trim()).filter(Boolean), pack: "me.my-domains", kind: "custom" }));
  const all = [...customDomains, ...packDomains];
  const packFor = (id: string) => all.find((d) => d.id === id)?.pack;
  const addCustom = () => {
    const id = draft.id.trim().toUpperCase().replace(/\s+/g, "-");
    if (!/^[A-Z][A-Z0-9-]{0,31}$/.test(id)) { setMsg("Domain ID 는 영문 대문자·숫자·하이픈 (예: CLOUD-SEC)"); return; }
    if (!draft.name.trim()) { setMsg("Domain 이름을 적어 주세요"); return; }
    if (all.some((d) => d.id === id)) { setMsg(`${id} 는 이미 있는 ID 입니다`); return; }
    setCustom([...custom, { ...draft, id }]); setDraft({ id: "", name: "", description: "", accent: "violet", sub_mocs: "" }); setMsg("");
    if (!form.primary) setForm({ ...form, primary: id });
  };
  const submit = async () => {
    setBusy(true); setMsg("");
    try {
      const chosen = [form.primary, form.research, form.growth].filter(Boolean);
      const packList = Array.from(new Set(chosen.map(packFor).filter((x): x is string => !!x && x !== "me.my-domains")));
      const used = customDomains.filter((d) => chosen.includes(d.id)).map((d) => custom.find((c) => c.id === d.id)!);
      await userPost("/api/onboarding", {
        ...form, research: form.research || null, growth: form.growth || null, packs: packList,
        custom_domains: used.map((c) => ({ id: c.id, name: c.name, description: c.description, accent: c.accent, sub_mocs: c.sub_mocs.split(",").map((s) => s.trim()).filter(Boolean) })),
      });
      onDone();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const Select = ({ k, label, required }: { k: "primary" | "research" | "growth"; label: string; required?: boolean }) => (
    <label className="hub-stack" style={{ gap: "var(--mx-space-1)" }}>
      <span className="mx-muted">{label}{required ? " *" : ""}</span>
      <select className="mx-input" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`select-${k}`}>
        <option value="">{required ? "선택" : "(없음)"}</option>
        {customDomains.length > 0 && <optgroup label="내가 정의한 Domain">{customDomains.map((d) => <option key={d.id} value={d.id}>{d.id} · {d.name}</option>)}</optgroup>}
        {KIND_ORDER.map((kind) => {
          const items = packDomains.filter((d) => d.kind === kind);
          return items.length ? <optgroup key={kind} label={KIND_LABEL[kind] ?? kind}>{items.map((d) => <option key={d.id} value={d.id}>{d.id} · {d.name} [{d.pack}]</option>)}</optgroup> : null;
        })}
      </select>
    </label>
  );
  return (
    <main className="hub-main" style={{ maxWidth: 760 }}>
      <h1 className="hub-h1">MYELIN 시작하기</h1>
      <p className="hub-sub">15분 안에 첫 verified 노트까지. 3+1 규칙 — Primary(업무 근간) · Research(연구) · Growth(성장). Vault: <span className="mx-mono">{root}</span></p>
      <div className="mx-card hub-stack" data-testid="onboarding">
        <label className="hub-stack" style={{ gap: "var(--mx-space-1)" }}><span className="mx-muted">이름 *</span><input className="mx-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="input-name" /></label>
        <div className="hub-row">
          <label className="hub-stack" style={{ gap: "var(--mx-space-1)", flex: 1 }}><span className="mx-muted">팀</span><input className="mx-input" value={form.team} onChange={(e) => setForm({ ...form, team: e.target.value })} /></label>
          <label className="hub-stack" style={{ gap: "var(--mx-space-1)", flex: 1 }}><span className="mx-muted">이메일</span><input className="mx-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        </div>

        <h3 style={{ margin: "var(--mx-space-3) 0 0" }}>1. 내 Domain 정하기</h3>
        <p className="mx-muted" style={{ margin: 0 }}>조직 Pack 에서 고르거나, 아래에서 <strong>내 업무와 관심사에 맞는 Domain 을 직접 정의</strong>한다. Reference Pack(brian.physical-ai)은 한 엔지니어의 지식 지형도를 참고용으로 제공할 뿐, 따라 할 필요가 없다.</p>
        <div className="mx-card hub-stack" style={{ boxShadow: "var(--mx-shadow-inset)" }} data-testid="custom-domain">
          <strong>직접 정의</strong>
          <div className="hub-row">
            <input className="mx-input" style={{ maxWidth: 160 }} placeholder="ID (예: CLOUD-SEC)" value={draft.id} onChange={(e) => setDraft({ ...draft, id: e.target.value })} data-testid="custom-id" />
            <input className="mx-input" style={{ flex: 1 }} placeholder="이름 (예: 클라우드 보안)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} data-testid="custom-name" />
            <select className="mx-input" style={{ maxWidth: 140 }} value={draft.accent} onChange={(e) => setDraft({ ...draft, accent: e.target.value })} aria-label="accent">
              {["violet", "lime", "cyan", "magenta"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <input className="mx-input" placeholder="한 줄 설명 (선택)" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          <input className="mx-input" placeholder="Sub-MOC 주제들, 쉼표로 구분 (예: IAM, 네트워크, 로깅)" value={draft.sub_mocs} onChange={(e) => setDraft({ ...draft, sub_mocs: e.target.value })} data-testid="custom-submocs" />
          <div className="hub-row">
            <button type="button" className="mx-btn" onClick={addCustom} data-testid="custom-add">+ Domain 추가</button>
            {custom.map((c) => <span key={c.id} className="mx-chip mx-chip--draft">{c.id} · {c.name} <button type="button" className="mx-btn" style={{ padding: "0 6px", marginLeft: 6 }} onClick={() => setCustom(custom.filter((x) => x.id !== c.id))} aria-label={`${c.id} 제거`}>×</button></span>)}
          </div>
        </div>

        <h3 style={{ margin: "var(--mx-space-3) 0 0" }}>2. 3+1 역할 배정</h3>
        <Select k="primary" label="Primary — 지금 내 업무의 근간" required />
        <Select k="research" label="Research — 스스로 파고드는 주제" />
        <Select k="growth" label="Growth — 1~2년 안에 갖추고 싶은 역량" />
        <div className="hub-row" role="radiogroup" aria-label="level">
          <span className="mx-muted">Level</span>
          {[0, 1, 2, 3].map((l) => <button key={l} type="button" className="mx-btn" aria-pressed={form.level === l} onClick={() => setForm({ ...form, level: l })}>{l}</button>)}
          <span className="mx-muted">0 읽기 전용 · 1 초안 · 2 링크 패치 · 3 정기 리뷰</span>
        </div>
        <div className="hub-row">
          <button type="button" className="mx-btn-primary" disabled={busy || !form.name || !form.primary} onClick={submit} data-testid="onboarding-submit">Vault 만들기</button>
          {msg && <span className="mx-badge--blocked" data-testid="onboarding-error">{msg}</span>}
        </div>
      </div>
    </main>
  );
}
