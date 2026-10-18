import { useEffect, useState } from "react";
import { act, get } from "../api";
import { Card, Chip, ErrorBox, Muted, StatusChip, useLoad } from "../components/ui";
import type { NoteView, ReviewItem, ReviewResult } from "../types";

/** Review Gate — verified 승격의 유일한 경로 (명세 §3 HITL). 본문을 연 노트만 승격·반려할 수 있다. */
export default function Review() {
  const { data, error, reload } = useLoad<ReviewItem[]>("/api/review");
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [note, setNote] = useState<NoteView | null>(null);
  const [noteError, setNoteError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  useEffect(() => {
    setNote(null);
    setNoteError(null);
    if (!selected) return;
    get<NoteView>(`/api/note?path=${encodeURIComponent(selected.path)}`)
      .then(setNote)
      .catch(setNoteError);
  }, [selected]);

  async function decide(kind: "promote" | "reject") {
    if (!selected || !note) return;
    setBusy(true);
    setActionError(null);
    try {
      const res = await act<ReviewResult>(`/api/review/${kind}`, { path: selected.path, id: selected.id });
      setResult(res);
      setSelected(null);
      reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-mx-6 items-start">
      <Card title={`Review Gate · 대기 ${data.length}`} testId="review-list">
        {result ? <ResultCard result={result} /> : null}
        {data.length === 0 ? (
          <Muted>검토할 노트가 없습니다. Claude의 /distill·/ingest 초안은 00_Inbox/ai-drafts 에 쌓입니다.</Muted>
        ) : (
          <ul>
            {data.map((item) => (
              <li key={item.path}>
                <button
                  className={`mx-review-row w-full text-left ${selected?.path === item.path ? "mx-nav__item is-active" : ""}`}
                  onClick={() => {
                    setResult(null);
                    setSelected(item);
                  }}
                  data-testid="review-row"
                >
                  <StatusChip status={item.status} ai={item.ai} />
                  <span className="mx-review-row__title">{item.title}</span>
                  <span className="mx-review-row__meta">{item.domain.join("·") || "domain 없음"}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="미리보기" testId="review-preview">
        {!selected ? <Muted>왼쪽에서 노트를 고르면 원문이 보입니다. 원문을 본 노트만 승격할 수 있습니다.</Muted> : null}
        <ErrorBox error={noteError} />
        {selected && note ? (
          <div className="flex flex-col gap-mx-4">
            <div className="flex items-center gap-mx-2">
              <StatusChip status={selected.status} ai={selected.ai} />
              <h3 className="text-xl font-bold">{note.title}</h3>
            </div>
            <dl className="grid grid-cols-[120px_1fr] gap-y-mx-1 text-sm">
              {Object.entries(note.frontmatter)
                .filter(([, v]) => v !== null && !(Array.isArray(v) && v.length === 0))
                .map(([k, v]) => (
                  <Frontmatter key={k} name={k} value={v} />
                ))}
              <dt className="text-mx-muted">path</dt>
              <dd>
                <code>{note.path}</code>
              </dd>
            </dl>
            <pre className="mx-pre max-h-[420px] overflow-auto" data-testid="note-body">
              {note.body}
            </pre>
            <div className="flex gap-mx-3 items-center">
              <button
                className="mx-btn mx-btn--promote"
                disabled={busy}
                onClick={() => decide("promote")}
                data-testid="promote"
              >
                Promote
              </button>
              <button className="mx-btn" disabled={busy} onClick={() => decide("reject")} data-testid="reject">
                Reject
              </button>
              <Muted>승격·반려는 git commit으로 남습니다.</Muted>
            </div>
            <ErrorBox error={actionError} />
          </div>
        ) : null}
      </Card>
    </div>
  );
}

function Frontmatter(props: { name: string; value: unknown }) {
  const v = props.value;
  const text = Array.isArray(v) ? v.join(", ") : String(v);
  return (
    <>
      <dt className="text-mx-muted">{props.name}</dt>
      <dd>{props.name === "origin" && v === "claude" ? <Chip kind="ai">claude</Chip> : text}</dd>
    </>
  );
}

function ResultCard(props: { result: ReviewResult }) {
  const r = props.result;
  const promoted = r.action === "promote";
  return (
    <div
      className={`mx-card mb-mx-4 ${promoted ? "mx-myelinate" : ""}`}
      role="status"
      data-testid="review-result"
    >
      <div className="flex items-center gap-mx-2">
        {promoted ? <Chip kind="verified">verified</Chip> : <Chip kind="blocked">rejected</Chip>}
        <span className="font-bold">{promoted ? "myelinated" : "반려했습니다"}</span>
      </div>
      <p className="text-sm mt-mx-2">
        <code>{r.path}</code>
      </p>
      <p className="text-xs text-mx-muted" data-testid="review-commit">
        commit {r.commit.slice(0, 7)}
      </p>
    </div>
  );
}
