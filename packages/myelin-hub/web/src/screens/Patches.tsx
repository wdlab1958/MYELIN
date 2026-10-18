import { useEffect, useState } from "react";
import { act, get } from "../api";
import { Card, Chip, ErrorBox, Muted, useLoad } from "../components/ui";
import type { PatchPreview, PatchRow } from "../types";

/** 링크·MOC 변경 제안 (ADR-0010) — diff를 보고 사람이 적용·반려한다. */
export default function Patches() {
  const { data, error, reload } = useLoad<PatchRow[]>("/api/patches");
  const [selected, setSelected] = useState<PatchRow | null>(null);
  const [preview, setPreview] = useState<PatchPreview | null>(null);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  useEffect(() => {
    setPreview(null);
    setPreviewError(null);
    if (!selected || !selected.structured) return;
    get<PatchPreview>(`/api/patches/preview?path=${encodeURIComponent(selected.path)}`)
      .then(setPreview)
      .catch(setPreviewError);
  }, [selected]);

  async function decide(kind: "apply" | "reject") {
    if (!selected) return;
    setBusy(true);
    setActionError(null);
    try {
      const res = await act<{ commit: string }>(`/api/patches/${kind}`, {
        path: selected.path,
        digest: preview?.digest ?? "",
      });
      setMessage(`${kind === "apply" ? "적용" : "반려"}했습니다 · commit ${res.commit.slice(0, 7)}`);
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
      <Card title={`링크·MOC 제안 · ${data.length}`} testId="patch-list">
        {message ? (
          <p className="text-sm mb-mx-3" role="status" data-testid="patch-message">
            {message}
          </p>
        ) : null}
        {data.length === 0 ? (
          <Muted>제안이 없습니다. Claude Code의 /myelin:link (Level 2)가 _patches/ 에 만듭니다.</Muted>
        ) : (
          <ul>
            {data.map((p) => (
              <li key={p.path}>
                <button
                  className={`mx-review-row w-full text-left ${selected?.path === p.path ? "mx-nav__item is-active" : ""}`}
                  onClick={() => {
                    setMessage(null);
                    setSelected(p);
                  }}
                  data-testid="patch-row"
                >
                  {p.structured ? <Chip kind="ai">{p.kind}</Chip> : <Chip kind="draft">수동</Chip>}
                  <span className="mx-review-row__title text-sm">
                    {p.structured ? p.target : p.path}
                  </span>
                  <span className="mx-review-row__meta">{p.structured ? p.skill : ""}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="변경 미리보기" testId="patch-preview">
        {!selected ? <Muted>왼쪽에서 제안을 고르면 대상 노트의 변경(diff)이 보입니다.</Muted> : null}
        {selected && !selected.structured ? (
          <div className="flex flex-col gap-mx-3">
            <Muted>구조화되지 않은 patch입니다 ({selected.reason}). Obsidian에서 직접 반영한 뒤 보관하세요.</Muted>
            <button className="mx-btn self-start" disabled={busy} onClick={() => decide("reject")}>
              보관 (반려)
            </button>
          </div>
        ) : null}
        <ErrorBox error={previewError} />
        {preview ? (
          <div className="flex flex-col gap-mx-3">
            <p className="text-sm">
              <code>{preview.target}</code> · {preview.rationale}
            </p>
            {preview.warnings.map((w) => (
              <p key={w} className="mx-chip mx-chip--draft self-start">
                {w}
              </p>
            ))}
            <pre className="mx-pre max-h-[380px] overflow-auto" data-testid="patch-diff">
              {preview.diff}
            </pre>
            <div className="flex gap-mx-3 items-center">
              <button
                className="mx-btn mx-btn--promote"
                disabled={busy}
                onClick={() => decide("apply")}
                data-testid="patch-apply"
              >
                적용
              </button>
              <button className="mx-btn" disabled={busy} onClick={() => decide("reject")}>
                반려
              </button>
              <Muted>적용·반려는 git commit으로 남고 patch는 _patches/applied·rejected 에 보관됩니다.</Muted>
            </div>
          </div>
        ) : null}
        <ErrorBox error={actionError} />
      </Card>
    </div>
  );
}
