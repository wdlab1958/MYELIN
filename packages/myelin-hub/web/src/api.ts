// Hub API 클라이언트. 쓰기(POST)는 반드시 `act()` — 사람의 클릭 핸들러에서만 부른다 (ADR-0008).
import type { Issue } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly issues: Issue[],
  ) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  const body: unknown = await res.json().catch(() => ({}));
  if (!res.ok) {
    const b = body as { error?: string; issues?: Issue[]; detail?: unknown };
    const issues = b.issues ?? (Array.isArray(b.detail) ? detailIssues(b.detail) : []);
    throw new ApiError(b.error ?? `요청 실패 (${res.status})`, res.status, issues);
  }
  return body as T;
}

function detailIssues(detail: unknown[]): Issue[] {
  return detail.map((d) => {
    const item = d as { loc?: unknown[]; msg?: string };
    return { loc: (item.loc ?? []).join("."), msg: item.msg ?? "" };
  });
}

export async function get<T>(path: string): Promise<T> {
  return parse<T>(await fetch(path, { headers: { Accept: "application/json" } }));
}

/** 사용자 행위로 일어나는 요청. 의도 헤더가 없으면 서버가 거부한다. */
export async function act<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Myelin-Intent": "user",
    },
    body: JSON.stringify(body),
  });
  return parse<T>(res);
}
