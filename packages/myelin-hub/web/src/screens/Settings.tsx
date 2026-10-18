import { useEffect, useState } from "react";
import { act } from "../api";
import { Card, Chip, ErrorBox, Muted, useLoad } from "../components/ui";
import type { Settings as Data } from "../types";

export default function Settings(props: { onChange: () => void }) {
  const { data, error, reload } = useLoad<Data>("/api/settings");
  const [level, setLevel] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<boolean | null>(null);
  const [metrics, setMetrics] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  useEffect(() => {
    if (data) {
      setLevel(data.level);
      setDrafts(data.mcp_write_drafts);
      setMetrics(data.metrics_opt_in);
    }
  }, [data]);

  if (error) return <ErrorBox error={error} />;
  if (!data || level === null || drafts === null || metrics === null) return <Muted>불러오는 중…</Muted>;
  const dirty = level !== data.level || drafts !== data.mcp_write_drafts || metrics !== data.metrics_opt_in;

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setActionError(null);
    setMessage(null);
    try {
      setMessage(await fn());
      reload();
      props.onChange();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      const res = await act<Data>("/api/settings", { level, mcp_write_drafts: drafts, metrics_opt_in: metrics });
      return res.commit ? `저장했습니다 · commit ${res.commit.slice(0, 7)}` : "저장했습니다";
    });
  const startGit = () =>
    run(async () => {
      const res = await act<{ commit: string }>("/api/git/init", {});
      return `로컬 git을 시작했습니다 · commit ${res.commit.slice(0, 7)}`;
    });

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-mx-6 items-start">
      <Card title="Claude 권한 Level" testId="settings-level">
        <fieldset className="flex flex-col gap-mx-2">
          <legend className="sr-only">Level</legend>
          {Object.entries(data.levels).map(([k, desc]) => (
            <label
              key={k}
              className={`flex gap-mx-3 items-start p-mx-3 rounded-control ${Number(k) === level ? "shadow-inset-sm" : ""}`}
            >
              <input
                type="radio"
                name="level"
                className="mx-check mt-mx-1"
                checked={Number(k) === level}
                onChange={() => setLevel(Number(k))}
              />
              <span>
                <b>Level {k}</b> <span className="text-sm text-mx-muted">— {desc}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <label className="flex gap-mx-3 items-center mt-mx-4">
          <input
            type="checkbox"
            className="mx-check"
            checked={drafts}
            onChange={(e) => setDrafts(e.target.checked)}
          />
          <span>
            MCP <code>write_draft</code> 허용 <span className="text-sm text-mx-muted">— ai-drafts 에만 씁니다</span>
          </span>
        </label>
        <label className="flex gap-mx-3 items-start mt-mx-3">
          <input
            type="checkbox"
            className="mx-check mt-mx-1"
            checked={metrics}
            onChange={(e) => setMetrics(e.target.checked)}
            data-testid="metrics-opt-in"
          />
          <span>
            익명 지표 수집 동의 (opt-in){" "}
            <span className="block text-sm text-mx-muted">
              구간으로 뭉갠 숫자만, 파일로만 만듭니다 — <code>myelin metrics --out</code> 으로 내용을 확인한 뒤 직접 제출.
              네트워크 전송 없음.
            </span>
          </span>
        </label>
        <div className="flex gap-mx-3 items-center mt-mx-5">
          <button className="mx-btn mx-btn--primary" disabled={!dirty || busy} onClick={save} data-testid="save-settings">
            저장
          </button>
          {message ? <span className="text-sm" role="status">{message}</span> : null}
        </div>
        <ErrorBox error={actionError} />
      </Card>
      <div className="flex flex-col gap-mx-6">
        <Card title="기밀 경계 (LLM 라우팅)" testId="settings-llm">
          <table className="text-sm w-full">
            <tbody>
              <tr>
                <td className="text-mx-muted py-mx-1">기본</td>
                <td>{data.llm.default}</td>
              </tr>
              {Object.entries(data.llm.route).map(([k, v]) => (
                <tr key={k}>
                  <td className="py-mx-1">
                    <code>{k}</code>
                  </td>
                  <td>{v === "local" ? <Chip kind="blocked">local — Claude로 보내지 않음</Chip> : v}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Muted className="mt-mx-3">
            기밀 경계는 Hub에서 바꾸지 않습니다. 바꾸려면 <code>myelin.yaml</code> 을 직접 고치세요.
          </Muted>
        </Card>
        <Card title="Vault" testId="settings-vault">
          <p className="text-sm break-all">
            <code>{data.vault}</code>
          </p>
          <p className="text-sm mt-mx-2">
            {data.owner.name}
            {data.owner.email ? ` · ${data.owner.email}` : ""} · {data.language}
          </p>
          <div className="mt-mx-4 flex items-center gap-mx-3">
            {data.git ? (
              <>
                <Chip kind="verified">git</Chip>
                <span className="text-sm">로컬 git 사용 중 — 승격·반려가 commit으로 남습니다.</span>
              </>
            ) : (
              <>
                <button className="mx-btn" disabled={busy || !data.git_available} onClick={startGit} data-testid="git-init">
                  로컬 git 시작
                </button>
                <Muted>승격하려면 필요합니다. 원격(push)은 설정하지 않습니다.</Muted>
              </>
            )}
          </div>
          {data.location.map((f, i) => (
            <div key={i} className="mx-badge--blocked mt-mx-3 text-sm">
              ● {f.msg}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
