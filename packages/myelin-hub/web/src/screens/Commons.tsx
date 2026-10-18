import { useEffect, useState } from "react";
import { act, get } from "../api";
import { Card, Chip, ErrorBox, Muted, useLoad } from "../components/ui";
import type { CommonsCandidate, CommonsCheck, CommonsState } from "../types";

/**
 * Team Commons — 공개는 개인의 행위 (명세 §9.1, ADR-0009).
 * 1) 자격·비식별 자동 검사 2) 사람 확인 5항목 3) 제안(로컬 브랜치) 4) 별도 확인 후 push.
 */
export default function Commons() {
  const { data, error, reload } = useLoad<CommonsState>("/api/commons");
  const [selected, setSelected] = useState<CommonsCandidate | null>(null);
  const [check, setCheck] = useState<CommonsCheck | null>(null);
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [pushing, setPushing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  useEffect(() => {
    setCheck(null);
    setConfirmed([]);
    if (!selected) return;
    get<CommonsCheck>(`/api/commons/check?path=${encodeURIComponent(selected.path)}`)
      .then(setCheck)
      .catch(setActionError);
  }, [selected]);

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setActionError(null);
    setMessage(null);
    try {
      setMessage(await fn());
      reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  const propose = () =>
    run(async () => {
      if (!check) return "";
      const res = await act<{ branch: string; commit: string }>("/api/commons/propose", {
        path: check.path,
        id: check.id,
        confirmed,
      });
      setSelected(null);
      return `제안 브랜치를 만들었습니다: ${res.branch} (${res.commit.slice(0, 7)}) — 아직 조직 원격으로 보내지 않았습니다.`;
    });

  const push = (branch: string) =>
    run(async () => {
      await act("/api/commons/push", { branch, confirm: true });
      setPushing(null);
      return `${branch} 를 조직 Commons 원격으로 보냈습니다. git 호스트에서 PR(MR)을 여세요.`;
    });

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;

  if (!data.enabled) {
    return (
      <Card title="Team Commons — 꺼져 있음" testId="commons-off">
        <p>Commons는 조직 내부 Git에 공개 승인된 노트와 Pack Registry를 두는 공간입니다. 기본은 꺼져 있습니다.</p>
        <ul className="list-disc pl-mx-5 text-sm mt-mx-3 flex flex-col gap-mx-1">
          <li>개인 Vault는 불가침 — 조직·관리자는 접근하지 않습니다.</li>
          <li>공개 대상: verified + share: true + classification public/internal (40_IP·confidential 불가)</li>
          <li>자동 비식별 검사 → 작성자 확인 5항목 → 제안 브랜치 → 별도 확인 후 push → 챔피언 리뷰</li>
        </ul>
        <pre className="mx-pre mt-mx-4">myelin commons link &lt;Vault&gt; &lt;Commons clone 경로&gt;</pre>
        <Muted className="mt-mx-2">조직 정책(소유권·외부 AI·직무발명) 합의 후 켜세요.</Muted>
      </Card>
    );
  }

  const allChecked = check ? Object.keys(check.checklist).every((k) => confirmed.includes(k)) : false;
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-mx-6 items-start">
      <div className="flex flex-col gap-mx-6">
        <Card title={`Team Commons · ${data.org ?? "연결 오류"}`} testId="commons-candidates">
          {!data.ok ? (
            <div className="mx-badge--blocked" role="alert">
              ● Commons 연결 오류
              <ul className="font-normal text-sm">
                {data.issues.map((i, n) => (
                  <li key={n}>
                    <code>{i.loc}</code> — {i.msg}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="text-sm text-mx-muted mb-mx-3">공개 후보 (verified + share: true)</p>
          {data.candidates.length === 0 ? (
            <Muted>후보가 없습니다. 노트 frontmatter에 share: true 를 직접 적어야 후보가 됩니다.</Muted>
          ) : (
            <ul>
              {data.candidates.map((c) => (
                <li key={c.path}>
                  <button
                    className={`mx-review-row w-full text-left ${selected?.path === c.path ? "mx-nav__item is-active" : ""}`}
                    onClick={() => setSelected(c)}
                    data-testid="commons-row"
                  >
                    {c.blocks.length ? <Chip kind="blocked">차단</Chip> : <Chip kind="verified">verified</Chip>}
                    <span className="mx-review-row__title">{c.title}</span>
                    <span className="mx-review-row__meta">{c.classification}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="내 제안" testId="commons-proposals">
          {data.proposals.length === 0 ? (
            <Muted>아직 제안이 없습니다.</Muted>
          ) : (
            <ul>
              {data.proposals.map((p) => (
                <li key={p.branch} className="mx-review-row">
                  {p.pushed === "yes" ? <Chip kind="verified">보냄</Chip> : <Chip kind="draft">로컬</Chip>}
                  <span className="mx-review-row__title text-sm">
                    {p.subject} <code className="text-xs text-mx-muted">{p.branch}</code>
                  </span>
                  {p.pushed === "no" && pushing !== p.branch ? (
                    <button className="mx-btn" onClick={() => setPushing(p.branch)} disabled={busy}>
                      조직으로 보내기…
                    </button>
                  ) : null}
                  {pushing === p.branch ? (
                    <span className="flex gap-mx-2 items-center">
                      <span className="text-xs">노트가 조직 원격으로 나갑니다.</span>
                      <button className="mx-btn" onClick={() => push(p.branch)} disabled={busy} data-testid="confirm-push">
                        보내기
                      </button>
                      <button className="mx-btn" onClick={() => setPushing(null)}>
                        취소
                      </button>
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
        {message ? (
          <p className="text-sm" role="status" data-testid="commons-message">
            {message}
          </p>
        ) : null}
        <ErrorBox error={actionError} />
      </div>

      <Card title="공개 검사" testId="commons-check">
        {!selected ? <Muted>왼쪽에서 노트를 고르면 자격·비식별 검사 결과와 공개본이 보입니다.</Muted> : null}
        {selected && !check ? <Muted>검사 중…</Muted> : null}
        {check ? (
          <div className="flex flex-col gap-mx-4">
            {check.blocks.length || check.deid.length ? (
              <div className="mx-badge--blocked" role="alert" data-testid="commons-blocked">
                ● fail-closed: 공개할 수 없습니다
                <ul className="font-normal text-sm mt-mx-1">
                  {[...check.blocks, ...check.deid].map((i, n) => (
                    <li key={n}>
                      <code>{i.loc}</code> — {i.msg}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p>
                <Chip kind="verified">자동 검사 통과</Chip>{" "}
                <span className="text-sm">
                  → <code>{check.target}</code>
                </span>
              </p>
            )}
            <div>
              <p className="text-sm text-mx-muted mb-mx-1">공개본 (출처 노트·share 필드 제거, 작성자·원 id 추가)</p>
              <pre className="mx-pre max-h-[300px] overflow-auto" data-testid="commons-content">
                {check.content}
              </pre>
            </div>
            {check.ok ? (
              <fieldset className="flex flex-col gap-mx-2">
                <legend className="font-bold mb-mx-2">작성자 확인 — 모두 직접 확인해야 제안할 수 있습니다</legend>
                {Object.entries(check.checklist).map(([k, text]) => (
                  <label key={k} className="flex gap-mx-3 items-start text-sm">
                    <input
                      type="checkbox"
                      className="mx-check mt-mx-1"
                      checked={confirmed.includes(k)}
                      onChange={(e) =>
                        setConfirmed(e.target.checked ? [...confirmed, k] : confirmed.filter((x) => x !== k))
                      }
                      data-testid={`confirm-${k}`}
                    />
                    <span>{text}</span>
                  </label>
                ))}
                <button
                  className="mx-btn mx-btn--primary mt-mx-3 self-start"
                  disabled={!allChecked || busy}
                  onClick={propose}
                  data-testid="commons-propose"
                >
                  Commons 제안
                </button>
                <Muted>제안은 내 Commons clone에 브랜치만 만듭니다. 조직으로 보내기는 다음 단계에서 따로 확인합니다.</Muted>
              </fieldset>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
