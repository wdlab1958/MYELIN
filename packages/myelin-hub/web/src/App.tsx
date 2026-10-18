import { useCallback, useEffect, useState } from "react";
import { get } from "./api";
import { ErrorBox } from "./components/ui";
import Commons from "./screens/Commons";
import Dashboard from "./screens/Dashboard";
import Domains from "./screens/Domains";
import Onboarding from "./screens/Onboarding";
import Packs from "./screens/Packs";
import Review from "./screens/Review";
import Settings from "./screens/Settings";
import type { State } from "./types";

const SCREENS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "domains", label: "My Domains" },
  { key: "review", label: "Review Gate" },
  { key: "packs", label: "Domain Packs" },
  { key: "commons", label: "Team Commons" },
  { key: "settings", label: "Settings" },
] as const;
type ScreenKey = (typeof SCREENS)[number]["key"];

function currentScreen(): ScreenKey {
  const key = window.location.hash.replace(/^#\//, "");
  return SCREENS.find((s) => s.key === key)?.key ?? "dashboard";
}

export default function App() {
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [screen, setScreen] = useState<ScreenKey>(currentScreen);

  const refresh = useCallback(() => {
    get<State>("/api/state").then(setState).catch(setError);
  }, []);
  useEffect(refresh, [refresh]);
  useEffect(() => {
    const onHash = () => setScreen(currentScreen());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (error) return <main className="p-mx-6"><ErrorBox error={error} /></main>;
  if (!state) return <main className="p-mx-6 text-mx-muted">불러오는 중…</main>;
  if (!state.initialized) {
    return (
      <Shell state={state}>
        <Onboarding vault={state.vault} onDone={refresh} />
      </Shell>
    );
  }
  return (
    <Shell state={state}>
      <div className="grid grid-cols-[220px_1fr] gap-mx-6 items-start">
        <nav className="mx-card mx-nav" aria-label="화면">
          {SCREENS.map((s) => (
            <a
              key={s.key}
              href={`#/${s.key}`}
              className={`mx-nav__item ${screen === s.key ? "is-active" : ""}`}
              aria-current={screen === s.key ? "page" : undefined}
              data-testid={`nav-${s.key}`}
            >
              {s.label}
            </a>
          ))}
        </nav>
        <main data-testid={`screen-${screen}`}>
          {screen === "dashboard" && <Dashboard />}
          {screen === "domains" && <Domains />}
          {screen === "review" && <Review />}
          {screen === "packs" && <Packs />}
          {screen === "commons" && <Commons />}
          {screen === "settings" && <Settings onChange={refresh} />}
        </main>
      </div>
    </Shell>
  );
}

function Shell(props: { state: State; children: React.ReactNode }) {
  const { state } = props;
  return (
    <div className="max-w-[1360px] mx-auto p-mx-5 flex flex-col gap-mx-6">
      <header className="mx-card flex items-center gap-mx-4 py-mx-4">
        <span className="text-3xl font-extrabold tracking-tight">MYELIN</span>
        <span className="mx-chip mx-chip--verified" title="localhost">Hub</span>
        <span className="text-mx-muted text-sm truncate flex-1" title={state.vault} data-testid="vault-path">
          {state.vault}
        </span>
        {state.initialized ? (
          <span className="text-sm">
            {state.owner} · <span className="mx-chip mx-chip--draft">Level {state.level}</span>
          </span>
        ) : null}
        {state.git ? null : <span className="mx-chip mx-chip--blocked">git 없음</span>}
      </header>
      {props.children}
    </div>
  );
}
