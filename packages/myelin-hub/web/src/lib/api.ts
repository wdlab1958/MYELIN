/** Hub API client. Writes always carry the user-click intent header and are only called from click handlers (ADR-0009). */
export const INTENT_HEADER = "X-Myelin-Intent";

/** A failed request: `status` lets a click handler tell "changed since you looked" (409 / 412) from other errors. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

/** Team mode (ADR-0016): the bearer token lives in sessionStorage only — per tab, gone when the tab closes, never in a cookie. */
const TOKEN_KEY = "myelin.team.token";
const teamToken = () => { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } };
let asking: Promise<string | null> | null = null;
/** A 401 means the Hub runs in team mode: ask once (shared by concurrent requests), keep for this tab. */
const askToken = () => (asking ??= Promise.resolve().then(() => {
  const t = window.prompt("이 Hub 는 팀 모드입니다. 발급받은 접근 토큰을 붙여 넣으세요.")?.trim() || null;
  try { if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
  setTimeout(() => { asking = null; }, 0);
  return t;
}));

async function request<T>(method: string, url: string, body?: unknown, userClick = false, extra?: Record<string, string>, retried = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(extra ?? {}) };
  if (userClick) headers[INTENT_HEADER] = "user-click";
  const token = teamToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (res.status === 401 && !retried) {
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
    if (await askToken()) return request<T>(method, url, body, userClick, extra, true);
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError((data && data.detail) || `${method} ${url} → ${res.status}`, res.status);
  return data as T;
}

/** Encode a Vault-relative path for use inside a URL path: each segment separately, so `#`, `?`, `%` in titles survive. */
/** Product display name in one place (WBS 1.6 — the name is provisional). Identifiers such as the `X-Myelin-Intent` header stay as they are. */
export const PRODUCT_NAME = "MYELIN";
export const refPath = (rel: string) => rel.split("/").map(encodeURIComponent).join("/");
export const get = <T,>(url: string) => request<T>("GET", url);
/** Only call from an onClick handler: the header is the UI's promise that a human clicked. */
export const userPost = <T,>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}, true);
export const userPut = <T,>(url: string, body?: unknown, headers?: Record<string, string>) => request<T>("PUT", url, body ?? {}, true, headers);
export const post = <T,>(url: string, body?: unknown) => request<T>("POST", url, body ?? {});

export type VaultSummary = {
  ready: boolean; root: string; owner?: { name: string; team: string; email: string }; level?: number; level_name?: string;
  domains?: Record<string, string>; packs?: string[]; mcp?: { write_draft: boolean; expose_confidential: boolean };
  skills?: { skill: string; min_level: number; enabled: boolean; write_scope: string; summary: string }[];
  git?: { repo: boolean; clean: boolean; changes: string[] };
  commons?: {
    configured: boolean; error: string | null; local: string | null; enabled: boolean; remote: string | null; metrics_opt_in: boolean;
    published_count?: number; cited_total?: number;
  };
};
export type Stats = {
  as_of: string; notes: number; kpi: { kpi: string; value: string | number | null; target: string; status: "ok" | "alert" | null }[];
  by_status: Record<string, number>; by_origin: Record<string, number>; by_domain: Record<string, number>;
  guard_blocks_7d: number; review_queue: number; parse_errors: number;
  /** ADR-0012 myelin strength histogram ("0".."3") and reuse KPIs */
  by_strength?: Record<string, number>; reuse_ratio?: number | null; reuse_lag_days?: number | null; compose_sources_avg?: number | null;
};
export type Domain = {
  id: string; role: string; notes: number; verified: number; moc: string | null; name?: string; accent?: string;
  description?: string; pack?: string; sub_mocs?: string[]; compose_targets?: string[];
  sub_moc_notes?: { name: string; path: string; note: string | null }[];
};
export type SearchHit = NoteRow & { snippet: string; rank: number };
/** Obsidian URI helpers (path-based, no vault name needed). */
export const obsidianOpen = (abs: string) => `obsidian://open?path=${encodeURIComponent(abs)}`;
export const obsidianNew = (abs: string) => `obsidian://new?path=${encodeURIComponent(abs)}`;
/** GET /api/obsidian — Graph View readiness of <Vault>/.obsidian and the URIs to open it. */
export type ObsidianStatus = {
  root: string; vault_name: string; config_dir: boolean; graph_enabled: boolean; color_groups: number;
  domains_without_group: string[]; theme: string | null; ready: boolean; registered: boolean | null; advanced_uri: boolean;
  open_url: string; graph_url: string; error: string | null;
};
export type NoteRow = {
  path: string; id: string; title: string; type: string; status: string; origin: string; domains: string[]; tags: string[];
  created: string; reviewed: string | null; classification: string; doctor_ok?: boolean; error?: string;
  /** ADR-0012 reuse counters: strength 0 = not verified · 1 verified · 2 reused · 3 hub / cited in Commons */
  inbound?: number; output_uses?: number; commons_cited?: number; strength?: number;
};
export type PatchRow = {
  file: string; target?: string; kind?: string; under?: string | null; skill?: string; rationale?: string; status: string; group?: string;
  sections?: Record<string, string>; error?: string;
};
export type PatchPlan = {
  name: string; target: string; kind: string; ok: boolean; issues: string[]; diff: string; digest: string; rationale: string;
};
export type PackRow = {
  name: string; version: string; kind: string; maintainer: string; description: string; active: boolean; editable: boolean;
  /** `configured` = already one of the Vault's Domains (myelin.yaml); false → can be added with POST /api/domains */
  domains: { id: string; name: string; accent: string; sub_mocs: string[]; configured: boolean }[];
};
export type Candidate = {
  path: string; title: string; eligible: boolean; ok: boolean; reasons: string[];
  deid_hits: { kind: string; line: number; excerpt: string }[];
  /** already in the Commons clone, and how often others cite that copy (ADR-0012) */
  published?: boolean; cited?: number;
};
export type PublishResult = {
  branch: string; commit: string; dest: string; pushed: boolean; pr_url: string | null;
  push_error?: string | null; pr_error?: string | null; next_step?: string | null;
};
export type AssistantStatus = {
  available: boolean; mode: "llm" | "kb"; model: string | null; url: string; local: boolean; name: string; error: string | null;
};
export type AssistantCitation = { path: string; title: string; status: string; classification: string; snippet: string };
export type AssistantReply = {
  content: string; mode: "llm" | "kb" | "refused"; model: string | null; citations: AssistantCitation[]; sections: string[];
  notice: string | null; finish_reason: string;
};
