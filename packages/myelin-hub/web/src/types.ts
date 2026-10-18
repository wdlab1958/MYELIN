export type Issue = { loc: string; msg: string; code?: string };

export type State = {
  vault: string;
  initialized: boolean;
  git: boolean;
  git_available: boolean;
  owner?: string;
  level?: number;
  version: string;
};

export type Finding = { path: string; rule: string; severity: "error" | "warning"; msg: string };
export type Commit = { sha: string; subject: string; when: string };

export type Stats = {
  notes: number;
  parse_errors: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_domain: Record<string, number>;
  inbox_items: number;
  inbox_avg_age_days: number;
  ai_drafts: number;
  ai_promotion_rate: number | null;
  orphan_ratio: number;
  cross_domain_ratio: number;
  verified_last_7d: number;
  verified_notes: number;
};

export type Dashboard = {
  owner: string;
  stats: Stats;
  review_count: number;
  findings: Finding[];
  commits: Commit[];
};

export type Accent = "violet" | "cyan" | "lime" | "magenta" | "amber" | "slate";

export type DomainRow = {
  id: string;
  label: string | null;
  name: string;
  accent: Accent;
  role: string;
  notes: number;
  verified: number;
  moc: string;
};

export type Addable = { id: string; label: string | null; name: string; accent: Accent; pack: string };
export type Domains = { domains: DomainRow[]; open_roles: string[]; addable: Addable[] };

export type ReviewItem = {
  path: string;
  id: string;
  title: string;
  type: string;
  status: string;
  origin: string;
  domain: string[];
  classification: string;
  created: string;
  ai: boolean;
};

export type NoteView = {
  path: string;
  title: string;
  frontmatter: Record<string, unknown>;
  body: string;
};

export type ReviewResult = { action: string; id: string; path: string; commit: string };

export type PackDomain = {
  id: string;
  label: string | null;
  name: string;
  accent: Accent;
  description: string;
  sub_mocs: string[];
};

export type Pack = {
  name: string;
  version: string;
  kind: string;
  maintainer: string;
  description: string;
  installed: boolean;
  terms: number;
  questions: number;
  domains: PackDomain[];
};

export type Validation = { ok: boolean; issues: Issue[]; pack?: string; domains?: string[] };

export type Settings = {
  vault: string;
  owner: { name: string; team: string | null; email: string | null };
  language: string;
  level: number;
  levels: Record<string, string>;
  mcp_write_drafts: boolean;
  llm: { default: string; route: Record<string, string> };
  git: boolean;
  git_available: boolean;
  location: Finding[];
  commit?: string | null;
};

export type Onboarding = {
  target: string;
  initialized: boolean;
  target_issues: Issue[];
  packs: Pack[];
  levels: Record<string, string>;
  git_available: boolean;
};

export type OnboardingBody = {
  owner: string;
  packs: string[];
  primary: string;
  research: string | null;
  growth: string | null;
  extra: string | null;
  level: number;
  language: string;
  git: boolean;
};

export type Preview = { files: number; domains: string[]; packs: string[]; level: number; sample: string[] };
