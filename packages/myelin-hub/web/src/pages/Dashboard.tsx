import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, type Stats, type VaultSummary } from "../lib/api";

const LABEL: Record<string, string> = {
  inbox_dwell_days: "Inbox 체류 (일)", verified_per_week: "주간 verified", ai_promotion_rate: "AI 초안 승격률",
  orphan_ratio: "고아 노트 비율", cross_domain_ratio: "Cross-domain 비율", outputs_per_month: "월간 산출물",
  reuse_ratio: "재사용 비율 (verified 중 강도 ≥ 2)", reuse_lag_days: "재사용 지연 (일, 중앙값)", compose_sources_avg: "산출물당 verified 출처",
};
/** ADR-0012 myelin strength rows: text label + meaning, never colour alone. */
const STRENGTH: { level: "1" | "2" | "3"; label: string; meaning: string }[] = [
  { level: "1", label: "myelin ×1", meaning: "verified — 검증만 됨" },
  { level: "2", label: "myelin ×2", meaning: "reused — 링크 2+ 또는 산출물에 인용" },
  { level: "3", label: "myelin ×3", meaning: "hub — Commons 인용 또는 링크 5+ · 산출물 2+" },
];

/** verified notes with strength ≥ 2 (reused), from the strength histogram. */
function reused(stats: Stats | null): number {
  const h = stats?.by_strength ?? {};
  return (h["2"] ?? 0) + (h["3"] ?? 0);
}

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
      <h2 className="hub-h2">Myelination (ADR-0012) <span className="mx-muted" style={{ fontWeight: 400, fontSize: "var(--mx-font-size-sm)" }}>— 쓸수록 빨라지는 지식 신경망: 검증되고 재사용될수록 강도가 오른다</span></h2>
      <div className="hub-grid" data-testid="myelination">
        <article className="mx-card mx-kpi mx-ring--verified">
          <div className="mx-kpi__value mx-kpi__value--verified" data-testid="kpi-reused-pct">{stats?.reuse_ratio == null ? "-" : `${Math.round(stats.reuse_ratio * 100)}%`}</div>
          <div className="mx-kpi__label">verified 중 재사용됨 (강도 ≥ 2) · {reused(stats)} / {stats?.by_status.verified ?? 0}</div>
        </article>
        <article className="mx-card hub-card--table" style={{ padding: 0 }}>
          <table className="mx-table" data-testid="strength-table">
            <thead><tr><th>강도</th><th>노트</th><th>의미</th></tr></thead>
            <tbody>
              {STRENGTH.map((s) => (
                <tr key={s.level}><td><span className={"mx-chip " + (s.level === "1" ? "mx-chip--unverified" : "mx-chip--verified")}>{s.label}</span></td><td className="mx-mono" data-testid={`strength-count-${s.level}`}>{stats?.by_strength?.[s.level] ?? 0}</td><td className="mx-muted">{s.meaning}</td></tr>
              ))}
            </tbody>
          </table>
        </article>
      </div>
      <h2 className="hub-h2">지표 (정본 §11.1 · ADR-0012)</h2>
      <div className="mx-card" style={{ padding: 0 }}>
        <table className="mx-table">
          <thead><tr><th>KPI</th><th>값</th><th>목표</th></tr></thead>
          <tbody>
            {stats?.kpi.map((k) => (
              <tr key={k.kpi}><td>{LABEL[k.kpi] ?? k.kpi} <span className="mx-muted mx-mono">{k.kpi}</span></td><td className="mx-mono">{k.value ?? "-"}</td><td>{k.target} {k.status === "alert" && <span className="mx-badge--blocked" data-testid={`kpi-alert-${k.kpi}`}>목표 이탈</span>}{k.status === "ok" && <span className="mx-chip mx-chip--verified">달성</span>}</td></tr>
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
