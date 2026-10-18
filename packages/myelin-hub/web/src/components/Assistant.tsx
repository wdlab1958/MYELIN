import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { get, obsidianOpen, post, type AssistantCitation, type AssistantReply, type AssistantStatus, type VaultSummary } from "../lib/api";

/**
 * 우측 하단 말풍선 → 도움말 챗봇 모달 (ADR-0013). SSC Platform · ARGUS-X · WDLAB-LLMOps · AlphaForge 와 같은 방식.
 * 읽기 전용: /api/assistant/chat 은 Vault 를 바꾸지 않으므로 클릭 헤더 없이 `post` 로 보낸다.
 * 답변 근거(관련 노트)는 Obsidian 링크로 연다. 로컬 LLM 이 없으면 서버가 지식 기반 모드로 답한다.
 */
type Msg = { role: "user" | "assistant"; content: string; reply?: AssistantReply };

const WELCOME: Msg = {
  role: "assistant",
  content: "안녕하세요, MYELIN 도우미(AI)입니다.\nMYELIN 의 개념·사용법·절차와 이 Vault 의 상태(Domain · Level · KPI · 관련 노트)를 물어보세요.",
};
const SUGGESTIONS = ["AI 초안을 승격(Promote)하는 절차는?", "Level 2 에서 쓸 수 있는 Skill 은?", "기밀 노트는 외부 LLM 에 가나요?", "Commons 에 노트를 공유하는 방법은?"];

export default function Assistant({ vault }: { vault: VaultSummary }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const composing = useRef(false); // 한글 IME 조합 중 Enter/ESC 오동작 방지

  useEffect(() => { if (open) void get<AssistantStatus>("/api/assistant/status").then(setStatus).catch(() => setStatus(null)); }, [open]);
  useEffect(() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight }); }, [msgs, busy, open]);
  useEffect(() => { if (open && !busy) inputRef.current?.focus(); }, [open, busy]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape" && !e.isComposing && !composing.current) setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setError(null); setInput("");
    const next: Msg[] = [...msgs, { role: "user", content: q }];
    setMsgs(next); setBusy(true);
    try {
      const history = next.filter((m) => m !== WELCOME).map((m) => ({ role: m.role, content: m.content }));
      const r = await post<AssistantReply>("/api/assistant/chat", { messages: history });
      setMsgs([...next, { role: "assistant", content: r.content, reply: r }]);
      if (status && r.mode !== "refused" && (r.mode === "llm") !== status.available) void get<AssistantStatus>("/api/assistant/status").then(setStatus).catch(() => undefined);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !composing.current) { e.preventDefault(); void send(); }
  };
  const abs = (rel: string) => `${vault.root}/${rel}`;

  return (
    <>
      {!open && (
        <button type="button" className="hub-fab" onClick={() => setOpen(true)} aria-label="도움말 챗봇 열기" title="MYELIN 도우미 — 질문하기" data-testid="assistant-fab">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-3.6-.8L3 21l1.9-4.6A8.4 8.4 0 0 1 3 11.5a8.4 8.4 0 0 1 9-8.4 8.4 8.4 0 0 1 9 8.4z" />
          </svg>
          도우미
        </button>
      )}
      {open && (
        <>
          <div className="hub-chat-backdrop" onClick={() => setOpen(false)} data-testid="assistant-backdrop" />
          <section className="hub-chat" role="dialog" aria-modal="true" aria-label="MYELIN 도우미" data-testid="assistant-dialog">
            <header className="hub-chat__head">
              <div>
                <div className="hub-chat__title">MYELIN 도우미</div>
                <div className="hub-chat__sub">AI 도움말 · 읽기 전용 · 대화는 저장하지 않음</div>
              </div>
              {status && (status.available
                ? <span className="mx-chip mx-chip--verified" data-testid="assistant-mode">로컬 LLM · {status.model}</span>
                : <span className="mx-chip mx-chip--unverified" title={status.error ?? ""} data-testid="assistant-mode">지식 기반 모드</span>)}
              <button type="button" className="mx-btn hub-chat__close" onClick={() => setOpen(false)} aria-label="닫기" data-testid="assistant-close">닫기</button>
            </header>
            <div className="hub-chat__body" ref={bodyRef} aria-live="polite" data-testid="assistant-messages">
              {msgs.map((m, i) => (
                <div key={i} className={"hub-msg " + (m.role === "user" ? "hub-msg--user" : "hub-msg--assistant")} data-testid={`assistant-msg-${m.role}`}>
                  {renderText(m.content)}
                  {m.reply && m.reply.citations.length > 0 && <Citations items={m.reply.citations} abs={abs} />}
                  {m.reply && m.reply.notice && <div className="hub-msg__meta">{m.reply.notice}</div>}
                </div>
              ))}
              {busy && <div className="hub-msg hub-msg--assistant mx-muted" data-testid="assistant-busy">답변을 만들고 있습니다…</div>}
              {error && <div className="mx-badge--blocked" role="alert">실패: {error}</div>}
            </div>
            {msgs.length === 1 && (
              <div className="hub-chat__suggest" data-testid="assistant-suggestions">
                {SUGGESTIONS.map((s) => <button type="button" key={s} className="mx-btn" onClick={() => void send(s)} disabled={busy}>{s}</button>)}
              </div>
            )}
            <form className="hub-chat__input" onSubmit={(e) => { e.preventDefault(); void send(); }}>
              <input ref={inputRef} className="mx-input" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown}
                onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }}
                placeholder="MYELIN 에 대해 물어보세요…" disabled={busy} aria-label="질문 입력" data-testid="assistant-input" />
              <button type="submit" className="mx-btn" disabled={busy || !input.trim()} data-testid="assistant-send">보내기</button>
            </form>
            <div className="hub-chat__foot">AI 도우미는 안내만 합니다. 승격·적용·공개는 사람이 Hub 버튼으로 합니다.</div>
          </section>
        </>
      )}
    </>
  );
}

function Citations({ items, abs }: { items: AssistantCitation[]; abs: (rel: string) => string }) {
  return (
    <ul className="hub-msg__cites" data-testid="assistant-citations">
      {items.map((c) => (
        <li key={c.path}><a href={obsidianOpen(abs(c.path))} title={c.snippet}>{c.title}</a> <span className="mx-muted">· {c.status} · <span className="mx-mono">{c.path}</span></span></li>
      ))}
    </ul>
  );
}

/** 마크다운 최소 렌더: `**굵게**` 와 `` `코드` `` 만. 줄바꿈은 CSS pre-wrap 이 처리한다. */
function renderText(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i}>{p.slice(1, -1)}</code>;
    return p;
  });
}
