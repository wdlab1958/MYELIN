import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, type Stats, type VaultSummary } from "../lib/api";

const LABEL: Record<string, string> = {
  inbox_dwell_days: "Inbox 체류 (일)", verified_per_week: "주간 verified", ai_promotion_rate: "AI 초안 승격률",
  orphan_ratio: "고아 노트 비율", cross_domain_ratio: "Cross-domain 비율", outputs_per_month: "월간 산출물",
};

export default function Dashboard({ vault }: { vault: VaultSummary }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [log, setLog] = useState<{ hash: string; date: string; subject: string }[]>([]);
  useEffect(() => {
    void get<Stats>("/api/stats").then(setStats);
    void get<{ hash: string; date: string; subject: string }[]>("/api/git/log?limit=8").then(setLog);
  }, []);
  return (
    <>
      <h1 className="hub-h1">Dashboard</h1>
      <p className="hub-sub">{vault.owner?.name} 의 지식 신경망 · {stats?.notes ?? "…"} notes · as of {stats?.as_of ?? "…"}</p>
      <div className="hub-grid" data-testid="kpi-grid">
        <article className="mx-card mx-kpi"><div className="mx-kpi__value mx-kpi__value--verified" data-testid="kpi-verified">{stats?.by_status.verified ?? 0}</div><div className="mx-kpi__label">verified · myelinated</div></article>
        <article className="mx-card mx-kpi"><div className="mx-kpi__value mx-kpi__value--ai" data-testid="kpi-queue">{stats?.review_queue ?? 0}</div><div className="mx-kpi__label">Review Gate 대기 <Link to="/review">→</Link></div></article>
        <article className="mx-card mx-kpi"><div className="mx-kpi__value mx-kpi__value--blocked">{stats?.guard_blocks_7d ?? 0}</div><div className="mx-kpi__label">Guard 차단 (7일)</div></article>
        <article className="mx-card mx-kpi"><div className="mx-kpi__value">{stats?.parse_errors ?? 0}</div><div className="mx-kpi__label">doctor 파싱 오류</div></article>
      </div>
      <h2 className="hub-h2">지표 (정본 §11.1)</h2>
      <div className="mx-card" style={{ padding: 0 }}>
        <table className="mx-table">
          <thead><tr><th>KPI</th><th>값</th><th>목표</th></tr></thead>
          <tbody>
            {stats?.kpi.map((k) => (
              <tr key={k.kpi}><td>{LABEL[k.kpi] ?? k.kpi} <span className="mx-muted mx-mono">{k.kpi}</span></td><td className="mx-mono">{k.value ?? "-"}</td><td>{k.target}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2 className="hub-h2">최근 커밋</h2>
      <div className="mx-card hub-stack" data-testid="git-log">
        {log.length === 0 && <span className="mx-muted">아직 커밋이 없습니다.</span>}
        {log.map((c) => (<div key={c.hash} className="hub-row"><span className="mx-mono mx-muted">{c.hash.slice(0, 7)}</span><span>{c.subject}</span></div>))}
      </div>
    </>
  );
}
