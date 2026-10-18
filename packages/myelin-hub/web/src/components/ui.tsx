import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, get } from "../api";
import type { Accent } from "../types";

export function Card(props: { title?: ReactNode; children: ReactNode; className?: string; testId?: string }) {
  return (
    <section className={`mx-card ${props.className ?? ""}`} data-testid={props.testId}>
      {props.title ? <h2 className="text-lg font-bold mb-mx-4">{props.title}</h2> : null}
      {props.children}
    </section>
  );
}

export type KpiTone = "violet" | "lime" | "cyan" | "ink";

export function Kpi(props: { label: string; value: ReactNode; sub?: ReactNode; tone?: KpiTone; glow?: "ai" | "verified" }) {
  const tone = props.tone && props.tone !== "ink" ? `mx-kpi__value--${props.tone}` : "";
  const glow = props.glow ? `mx-glow--${props.glow}` : "";
  return (
    <div className={`mx-card ${glow}`} data-testid={`kpi-${props.label}`}>
      <div className="mx-kpi__label">{props.label}</div>
      <div className={`mx-kpi__value ${tone}`}>{props.value}</div>
      {props.sub ? <div className="mx-kpi__sub">{props.sub}</div> : null}
    </div>
  );
}

export type ChipKind = "verified" | "ai" | "draft" | "blocked";

export function Chip(props: { kind: ChipKind; children: ReactNode }) {
  return <span className={`mx-chip mx-chip--${props.kind}`}>{props.children}</span>;
}

/** 노트 상태 → 칩. 색만으로 전달하지 않고 항상 라벨을 붙인다 (가드레일 4). */
export function StatusChip(props: { status: string; ai: boolean }) {
  if (props.status === "verified") return <Chip kind="verified">verified</Chip>;
  if (props.status === "deprecated") return <Chip kind="blocked">deprecated</Chip>;
  if (props.ai) return <Chip kind="ai">ai-draft</Chip>;
  return <Chip kind="draft">{props.status}</Chip>;
}

export function Orb(props: { label: string; name: string; accent: Accent }) {
  return (
    <div className="mx-orb" data-accent={props.accent}>
      <span className="mx-orb__label">{props.label}</span>
      <span className="mx-orb__name">{props.name}</span>
    </div>
  );
}

export function ErrorBox(props: { error: unknown }) {
  if (!props.error) return null;
  const err = props.error;
  const message = err instanceof Error ? err.message : String(err);
  const issues = err instanceof ApiError ? err.issues : [];
  return (
    <div className="mx-badge--blocked my-mx-3" role="alert" data-testid="error">
      <div>● {message}</div>
      {issues.length ? (
        <ul className="font-normal text-sm mt-mx-1">
          {issues.map((i, n) => (
            <li key={n}>
              <code>{i.loc}</code> — {i.msg}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function Muted(props: { children: ReactNode; className?: string }) {
  return <p className={`text-mx-muted text-sm ${props.className ?? ""}`}>{props.children}</p>;
}

/** GET 하나를 읽는다. reload()는 화면 갱신 — 읽기만 한다. */
export function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const reload = useCallback(() => {
    get<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch(setError);
  }, [path]);
  useEffect(reload, [reload]);
  return { data, error, reload };
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;
}
