import { useEffect, useMemo, useState } from "react";
import { act } from "../api";
import { Card, ErrorBox, Muted, Orb, useLoad } from "../components/ui";
import type { Onboarding as Data, OnboardingBody, PackDomain, Preview } from "../types";

const STEPS = ["나", "Pack", "Domain", "권한", "확인"] as const;
const ROLES = [
  { key: "primary", label: "업무 근간", required: true },
  { key: "research", label: "연구", required: false },
  { key: "growth", label: "성장", required: false },
  { key: "extra", label: "추가", required: false },
] as const;
type RoleKey = (typeof ROLES)[number]["key"];

/** 온보딩 마법사 — `myelin init` 과 같은 core 로직 (myelin_core.onboarding). 마지막 버튼 전에는 아무것도 쓰지 않는다. */
export default function Onboarding(props: { vault: string; onDone: () => void }) {
  const { data, error } = useLoad<Data>("/api/onboarding");
  const [step, setStep] = useState(0);
  const [owner, setOwner] = useState("");
  const [language, setLanguage] = useState("ko");
  const [packs, setPacks] = useState<string[]>([]);
  const [roles, setRoles] = useState<Record<RoleKey, string>>({ primary: "", research: "", growth: "", extra: "" });
  const [level, setLevel] = useState(1);
  const [git, setGit] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  const domains: PackDomain[] = useMemo(
    () => (data?.packs ?? []).filter((p) => packs.includes(p.name)).flatMap((p) => p.domains),
    [data, packs],
  );
  const body: OnboardingBody = {
    owner: owner.trim(),
    packs,
    primary: roles.primary,
    research: roles.research || null,
    growth: roles.growth || null,
    extra: roles.extra || null,
    level,
    language,
    git,
  };

  useEffect(() => {
    if (STEPS[step] !== "확인") return;
    setPreview(null);
    setActionError(null);
    act<Preview>("/api/onboarding/preview", body).then(setPreview).catch(setActionError);
    // body 는 step 진입 시점의 값으로 미리보기한다
  }, [step]);

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Muted>불러오는 중…</Muted>;

  const blocked = data.target_issues.length > 0;
  const canNext = [owner.trim().length > 0, packs.length > 0, roles.primary !== "", true, false][step] ?? false;

  async function create() {
    setBusy(true);
    setActionError(null);
    try {
      await act("/api/onboarding/apply", body);
      props.onDone();
    } catch (e) {
      setActionError(e);
      setBusy(false);
    }
  }

  return (
    <div className="max-w-[880px] mx-auto w-full flex flex-col gap-mx-5" data-testid="onboarding">
      <Card>
        <h1 className="text-2xl font-extrabold">나의 지식 신경망 시작하기</h1>
        <Muted className="mt-mx-2">
          5단계로 Vault를 만듭니다. 마지막 “Vault 만들기”를 누르기 전에는 아무것도 저장하지 않습니다.
        </Muted>
        <ol className="flex gap-mx-2 mt-mx-4" aria-label="단계">
          {STEPS.map((s, i) => (
            <li
              key={s}
              className={`mx-nav__item text-sm ${i === step ? "is-active" : "text-mx-muted"}`}
              aria-current={i === step ? "step" : undefined}
            >
              {i + 1}. {s}
            </li>
          ))}
        </ol>
        {blocked ? (
          <div className="mx-badge--blocked mt-mx-4" role="alert">
            ● 이 경로에는 Vault를 만들 수 없습니다
            <ul className="font-normal text-sm">
              {data.target_issues.map((i, n) => (
                <li key={n}>{i.msg}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      <Card>
        {STEPS[step] === "나" && (
          <div className="flex flex-col gap-mx-3">
            <label htmlFor="ob-owner" className="font-bold">
              이름
            </label>
            <input
              id="ob-owner"
              className="mx-input"
              value={owner}
              maxLength={80}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="예: Brian"
              autoFocus
            />
            <label htmlFor="ob-lang" className="font-bold mt-mx-2">
              노트 언어
            </label>
            <select id="ob-lang" className="mx-input" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="ko">한국어 (ko)</option>
              <option value="en">English (en)</option>
              <option value="ja">日本語 (ja)</option>
            </select>
            <Muted>
              Vault 위치: <code>{props.vault}</code> — 이 컴퓨터에만 저장됩니다.
            </Muted>
          </div>
        )}

        {STEPS[step] === "Pack" && (
          <fieldset className="flex flex-col gap-mx-3">
            <legend className="font-bold mb-mx-2">Domain Pack 고르기 (여러 개 가능)</legend>
            {data.packs.map((p) => (
              <label key={p.name} className="flex gap-mx-3 items-start">
                <input
                  type="checkbox"
                  className="mx-check mt-mx-1"
                  checked={packs.includes(p.name)}
                  onChange={(e) =>
                    setPacks(e.target.checked ? [...packs, p.name] : packs.filter((x) => x !== p.name))
                  }
                  data-testid={`pack-${p.name}`}
                />
                <span>
                  <b>{p.name}</b> <span className="text-xs text-mx-muted">v{p.version} · {p.kind}</span>
                  <span className="block text-sm text-mx-muted">
                    {p.domains.map((d) => d.name).join(" · ")}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        )}

        {STEPS[step] === "Domain" && (
          <div className="grid grid-cols-[1fr_auto] gap-mx-6">
            <div className="flex flex-col gap-mx-3">
              <p className="font-bold">3+1 규칙 — 업무 근간은 필수, 나머지는 선택</p>
              {ROLES.map((r) => (
                <div key={r.key} className="flex flex-col gap-mx-1">
                  <label htmlFor={`ob-${r.key}`} className="text-sm text-mx-muted">
                    {r.label}
                    {r.required ? " *" : ""}
                  </label>
                  <select
                    id={`ob-${r.key}`}
                    className="mx-input"
                    value={roles[r.key]}
                    onChange={(e) => setRoles({ ...roles, [r.key]: e.target.value })}
                  >
                    <option value="">{r.required ? "선택…" : "(없음)"}</option>
                    {domains
                      .filter((d) => d.id === roles[r.key] || !Object.values(roles).includes(d.id))
                      .map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.label ? `${d.label} · ` : ""}
                          {d.name}
                        </option>
                      ))}
                  </select>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-mx-4 items-center">
              {ROLES.map((r) => {
                const d = domains.find((x) => x.id === roles[r.key]);
                return d ? <Orb key={r.key} label={d.label ?? d.id.slice(0, 3)} name={d.name} accent={d.accent} /> : null;
              })}
            </div>
          </div>
        )}

        {STEPS[step] === "권한" && (
          <div className="flex flex-col gap-mx-3">
            <fieldset className="flex flex-col gap-mx-2">
              <legend className="font-bold mb-mx-2">Claude 권한 Level (나중에 Settings에서 바꿀 수 있습니다)</legend>
              {Object.entries(data.levels).map(([k, desc]) => (
                <label key={k} className="flex gap-mx-3 items-start">
                  <input
                    type="radio"
                    name="ob-level"
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
            <label className="flex gap-mx-3 items-center mt-mx-3">
              <input
                type="checkbox"
                className="mx-check"
                checked={git && data.git_available}
                disabled={!data.git_available}
                onChange={(e) => setGit(e.target.checked)}
              />
              <span>
                로컬 git으로 기록 <span className="text-sm text-mx-muted">— 승격·반려를 되돌릴 수 있게 (원격 없음)</span>
              </span>
            </label>
          </div>
        )}

        {STEPS[step] === "확인" && (
          <div className="flex flex-col gap-mx-3" data-testid="onboarding-preview">
            {preview ? (
              <>
                <p>
                  <b>{owner}</b> 님의 Vault — Domain <b>{preview.domains.join(", ")}</b> · Level {preview.level} · 파일{" "}
                  {preview.files}개
                </p>
                <pre className="mx-pre max-h-[260px] overflow-auto">{preview.sample.join("\n")}</pre>
                <Muted>기존 파일은 덮어쓰지 않습니다. 노트는 하나도 만들지 않습니다 (MOC·템플릿·설정만).</Muted>
              </>
            ) : actionError ? null : (
              <Muted>계획을 계산하는 중…</Muted>
            )}
          </div>
        )}

        <ErrorBox error={actionError} />

        <div className="flex gap-mx-3 mt-mx-5">
          {step > 0 ? (
            <button className="mx-btn" onClick={() => setStep(step - 1)} disabled={busy}>
              이전
            </button>
          ) : null}
          <span className="flex-1" />
          {STEPS[step] === "확인" ? (
            <button
              className="mx-btn mx-btn--primary"
              disabled={!preview || busy || blocked}
              onClick={create}
              data-testid="create-vault"
            >
              Vault 만들기
            </button>
          ) : (
            <button
              className="mx-btn mx-btn--primary"
              disabled={!canNext || blocked}
              onClick={() => setStep(step + 1)}
              data-testid="next"
            >
              다음
            </button>
          )}
        </div>
      </Card>
    </div>
  );
}
