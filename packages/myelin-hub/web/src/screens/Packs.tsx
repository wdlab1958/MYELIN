import { useState } from "react";
import { act, get } from "../api";
import { Card, Chip, ErrorBox, Muted, useLoad } from "../components/ui";
import type { Pack, Validation } from "../types";

/** Domain Packs — 목록과 편집기(검증 전용). Pack은 데이터이며 저장은 Pack 저장소에서 git으로 한다. */
export default function Packs() {
  const { data, error } = useLoad<Pack[]>("/api/packs");
  const [editing, setEditing] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [result, setResult] = useState<Validation | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  async function open(name: string) {
    setResult(null);
    setActionError(null);
    try {
      const src = await get<{ name: string; yaml: string }>(`/api/packs/${encodeURIComponent(name)}/source`);
      setEditing(name);
      setText(src.yaml);
    } catch (e) {
      setActionError(e);
    }
  }

  async function validate() {
    setActionError(null);
    try {
      setResult(await act<Validation>("/api/packs/validate", { yaml: text }));
    } catch (e) {
      setActionError(e);
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-mx-6 items-start">
      <div className="flex flex-col gap-mx-5" data-testid="pack-list">
        {data.map((p) => (
          <Card key={p.name}>
            <div className="flex items-center gap-mx-2 mb-mx-2">
              <h3 className="text-lg font-bold flex-1">{p.name}</h3>
              <span className="text-xs text-mx-muted">
                v{p.version} · {p.kind}
              </span>
              {p.installed ? <Chip kind="verified">사용 중</Chip> : <Chip kind="draft">미사용</Chip>}
            </div>
            {p.description ? <Muted>{p.description}</Muted> : null}
            <ul className="flex flex-wrap gap-mx-2 my-mx-3">
              {p.domains.map((d) => (
                <li key={d.id} className="mx-chip mx-chip--draft" title={d.description}>
                  {d.label ? `${d.label} · ` : ""}
                  {d.name}
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-mx-3">
              <span className="text-xs text-mx-muted flex-1">
                용어 {p.terms} · 인터뷰 질문 {p.questions} · {p.maintainer}
              </span>
              <button className="mx-btn" onClick={() => open(p.name)}>
                pack.yaml 보기
              </button>
            </div>
          </Card>
        ))}
      </div>
      <Card title="Pack 편집기" testId="pack-editor">
        {editing === null ? (
          <Muted>
            Pack을 고르면 pack.yaml 이 열립니다. 고친 내용을 검증할 수 있고, 저장은 Pack 저장소(git)에서 합니다 —
            Pack은 코드가 아니라 데이터입니다.
          </Muted>
        ) : (
          <div className="flex flex-col gap-mx-3">
            <label htmlFor="pack-yaml" className="text-sm text-mx-muted">
              {editing}/pack.yaml
            </label>
            <textarea
              id="pack-yaml"
              className="mx-input font-mono text-sm min-h-[420px]"
              spellCheck={false}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setResult(null);
              }}
            />
            <div className="flex gap-mx-3 items-center">
              <button className="mx-btn mx-btn--primary" onClick={validate} data-testid="validate-pack">
                검증
              </button>
              {result?.ok ? (
                <span role="status">
                  <Chip kind="verified">valid</Chip> {result.pack} · Domain {result.domains?.join(", ")}
                </span>
              ) : null}
            </div>
            {result && !result.ok ? (
              <div className="mx-badge--blocked" role="alert">
                <div>● 검증 실패 {result.issues.length}건</div>
                <ul className="font-normal text-sm mt-mx-1">
                  {result.issues.map((i, n) => (
                    <li key={n}>
                      <code>{i.loc}</code> — {i.msg}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
        <ErrorBox error={actionError} />
      </Card>
    </div>
  );
}
