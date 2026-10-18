/** Hub API client. Writes always carry the user-click intent header and are only called from click handlers (ADR-0009). */
export const INTENT_HEADER = "X-Myelin-Intent";

async function request<T>(method: string, url: string, body?: unknown, userClick = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (userClick) headers[INTENT_HEADER] = "user-click";
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error((data && data.detail) || `${method} ${url} → ${res.status}`);
  return data as T;
}

export const get = <T,>(url: string) => request<T>("GET", url);
/** Only call from an onClick handler: the header is the UI's promise that a human clicked. */
export const userPost = <T,>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}, true);
export const userPut = <T,>(url: string, body?: unknown) => request<T>("PUT", url, body ?? {}, true);
export const post = <T,>(url: string, body?: unknown) => request<T>("POST", url, body ?? {});

export type VaultSummary = {
  ready: boolean; root: string; owner?: { name: string; team: string; email: string }; level?: number; level_name?: string;
  domains?: Record<string, string>; packs?: string[]; mcp?: { write_draft: boolean; expose_confidential: boolean };
  skills?: { skill: string; min_level: number; enabled: boolean; write_scope: string; summary: string }[];
  git?: { repo: boolean; clean: boolean; changes: string[] };
};
export type Stats = {
  as_of: string; notes: number; kpi: { kpi: string; value: number | null; target: string }[];
  by_status: Record<string, number>; by_origin: Record<string, number>; by_domain: Record<string, number>;
  guard_blocks_7d: number; review_queue: number; parse_errors: number;
};
export type Domain = {
  id: string; role: string; notes: number; verified: number; moc: string | null; name?: string; accent?: string;
  description?: string; pack?: string; sub_mocs?: string[]; compose_targets?: string[];
};
export type NoteRow = {
  path: string; id: string; title: string; type: string; status: string; origin: string; domains: string[]; tags: string[];
  created: string; reviewed: string | null; classification: string; doctor_ok?: boolean; error?: string;
};
export type PatchRow = {
  file: string; target?: string; kind?: string; skill?: string; rationale?: string; status: string; sections?: Record<string, string>; error?: string;
};
export type PackRow = {
  name: string; version: string; kind: string; maintainer: string; description: string; active: boolean; editable: boolean;
  domains: { id: string; name: string; accent: string; sub_mocs: string[] }[];
};
export type Candidate = {
  path: string; title: string; eligible: boolean; ok: boolean; reasons: string[];
  deid_hits: { kind: string; line: number; excerpt: string }[];
};
