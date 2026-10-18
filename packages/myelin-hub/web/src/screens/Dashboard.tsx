import { Card, Chip, ErrorBox, Kpi, Muted, pct, useLoad } from "../components/ui";
import type { Dashboard as Data } from "../types";

export default function Dashboard() {
  const { data, error } = useLoad<Data>("/api/dashboard");
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;
  const s = data.stats;
  const rate = s.ai_promotion_rate;
  const rateNote =
    rate === null ? "AI 노트 없음" : rate > 0.7 ? "70% 초과 — 검토가 느슨하지 않은지" : "목표 40–70%";
  const errors = data.findings.filter((f) => f.severity === "error");
  return (
    <div className="flex flex-col gap-mx-6">
      <div className="grid grid-cols-4 gap-mx-5">
        <Kpi
          label="Verified"
          value={s.verified_notes}
          sub={`MOC 제외 · 전체 노트 ${s.notes} · 7일 +${s.verified_last_7d}`}
          tone="violet"
        />
        <Kpi label="AI Drafts" value={s.ai_drafts} sub={`검토 대기 ${data.review_count}`} tone="cyan" glow="ai" />
        <Kpi label="AI 승격률" value={pct(rate)} sub={rateNote} tone="lime" glow="verified" />
        <Kpi label="Cross-domain" value={pct(s.cross_domain_ratio)} sub="목표 ≥ 15%" />
      </div>
      <div className="grid grid-cols-[1fr_1fr] gap-mx-6 items-start">
        <Card title="Vault 상태" testId="doctor">
          <dl className="grid grid-cols-2 gap-y-mx-2 text-sm mb-mx-4">
            <dt className="text-mx-muted">Inbox</dt>
            <dd>
              {s.inbox_items}건 · 평균 {s.inbox_avg_age_days}일
            </dd>
            <dt className="text-mx-muted">고아 노트</dt>
            <dd>{pct(s.orphan_ratio)} (목표 ≤ 10%)</dd>
            <dt className="text-mx-muted">읽을 수 없는 노트</dt>
            <dd>{s.parse_errors}</dd>
          </dl>
          {data.findings.length === 0 ? (
            <p>
              <Chip kind="verified">clean</Chip> <span className="text-sm">doctor 위반 없음</span>
            </p>
          ) : (
            <>
              {errors.length ? (
                <div className="mx-badge--blocked mb-mx-3">● fail-closed: doctor 오류 {errors.length}건</div>
              ) : null}
              <ul className="flex flex-col gap-mx-2 text-sm">
                {data.findings.slice(0, 12).map((f, i) => (
                  <li key={i} className="flex gap-mx-2 items-start">
                    <Chip kind={f.severity === "error" ? "blocked" : "draft"}>{f.severity}</Chip>
                    <span>
                      <code className="text-mx-muted">{f.path}</code> {f.msg}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
        <Card title="최근 기록 (git)" testId="commits">
          {data.commits.length === 0 ? (
            <Muted>아직 commit이 없습니다. Settings에서 로컬 git을 시작하세요.</Muted>
          ) : (
            <ul className="flex flex-col">
              {data.commits.map((c) => (
                <li key={c.sha} className="mx-review-row">
                  <code className="text-mx-muted text-xs">{c.sha.slice(0, 7)}</code>
                  <span className="mx-review-row__title text-sm">{c.subject}</span>
                  <span className="mx-review-row__meta">{c.when.slice(0, 16).replace("T", " ")}</span>
                </li>
              ))}
            </ul>
          )}
          {data.review_count > 0 ? (
            <a className="mx-btn mt-mx-4 inline-block" href="#/review">
              Review Gate로 — {data.review_count}건 대기
            </a>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
