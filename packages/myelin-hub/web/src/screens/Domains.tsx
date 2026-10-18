import { useState } from "react";
import { act } from "../api";
import { Card, ErrorBox, Muted, Orb, useLoad } from "../components/ui";
import type { Domains as Data } from "../types";

const ROLE_LABEL: Record<string, string> = {
  primary: "업무 근간",
  research: "연구",
  growth: "성장",
  extra: "추가",
};

export default function Domains() {
  const { data, error, reload } = useLoad<Data>("/api/domains");
  const [pick, setPick] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;
  const chosen = data.addable.find((a) => a.id === pick);
  const chosenRole = role || data.open_roles[0] || "";

  async function add() {
    if (!chosen || !chosenRole) return;
    setBusy(true);
    setActionError(null);
    try {
      await act("/api/domains/add", { domain: chosen.id, role: chosenRole, pack: chosen.pack });
      setDone(`${chosen.id} 을(를) ${ROLE_LABEL[chosenRole] ?? chosenRole} 역할로 추가했습니다.`);
      setPick("");
      reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-[1fr_340px] gap-mx-6 items-start">
      <Card title="My Domain Map" testId="domain-map">
        <div className="flex flex-wrap gap-mx-6 py-mx-3">
          {data.domains.map((d) => (
            <div key={d.id} className="flex flex-col items-center gap-mx-2" data-testid={`domain-${d.id}`}>
              <Orb label={d.label ?? d.id.slice(0, 3)} name={d.name} accent={d.accent} />
              <div className="text-sm font-bold">{ROLE_LABEL[d.role] ?? d.role}</div>
              <div className="text-xs text-mx-muted">
                노트 {d.notes} · verified {d.verified}
              </div>
              <code className="text-xs text-mx-muted">{d.moc}</code>
            </div>
          ))}
        </div>
        <Muted className="mt-mx-4">
          3+1 규칙: 업무 근간·연구·성장 각 1개 + 추가 1개. MOC는 Obsidian에서 엽니다.
        </Muted>
      </Card>
      <Card title="+ Domain 추가" testId="add-domain">
        {data.open_roles.length === 0 ? (
          <Muted>모든 역할이 차 있습니다 (3+1).</Muted>
        ) : (
          <div className="flex flex-col gap-mx-3">
            <label className="text-sm text-mx-muted" htmlFor="add-domain-id">
              Domain
            </label>
            <select
              id="add-domain-id"
              className="mx-input"
              value={pick}
              onChange={(e) => setPick(e.target.value)}
            >
              <option value="">선택…</option>
              {data.addable.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.label ? `${a.label} · ` : ""}
                  {a.name} ({a.pack})
                </option>
              ))}
            </select>
            <label className="text-sm text-mx-muted" htmlFor="add-domain-role">
              역할
            </label>
            <select
              id="add-domain-role"
              className="mx-input"
              value={chosenRole}
              onChange={(e) => setRole(e.target.value)}
            >
              {data.open_roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r] ?? r}
                </option>
              ))}
            </select>
            <button className="mx-btn mx-btn--primary" disabled={!chosen || busy} onClick={add}>
              Domain 추가
            </button>
            <Muted>MOC·사전·질문 은행만 추가합니다. 기존 노트는 건드리지 않습니다.</Muted>
          </div>
        )}
        {done ? <p className="mt-mx-3 text-sm" role="status">{done}</p> : null}
        <ErrorBox error={actionError} />
      </Card>
    </div>
  );
}
