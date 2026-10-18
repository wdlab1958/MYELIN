import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { get, type VaultSummary } from "./lib/api";
import Dashboard from "./pages/Dashboard";
import Domains from "./pages/Domains";
import Review from "./pages/Review";
import Packs from "./pages/Packs";
import Settings from "./pages/Settings";
import Onboarding from "./pages/Onboarding";

const NAV = [
  ["/", "Dashboard"],
  ["/domains", "My Domains"],
  ["/review", "Inbox / Review Gate"],
  ["/packs", "Domain Packs"],
  ["/settings", "Settings"],
] as const;

export default function App() {
  const [vault, setVault] = useState<VaultSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const refresh = () => get<VaultSummary>("/api/vault").then(setVault).catch((e) => setErr(String(e)));
  useEffect(() => { void refresh(); }, []);

  if (err) return <main className="hub-main"><div className="mx-badge--blocked">API 오류 · {err}</div></main>;
  if (!vault) return <main className="hub-main mx-muted">loading…</main>;
  if (!vault.ready) return <Onboarding root={vault.root} onDone={refresh} />;

  return (
    <div className="hub-shell">
      <aside className="hub-side">
        <div className="hub-brand">MYELIN <span className="mx-muted" style={{ fontWeight: 400, fontSize: "var(--mx-font-size-sm)" }}>Hub</span></div>
        <nav className="mx-nav" aria-label="주 메뉴">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => "mx-nav-item" + (isActive ? " is-active" : "")} data-testid={`nav-${label.split(" ")[0].toLowerCase()}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mx-muted" style={{ padding: "var(--mx-space-5) var(--mx-space-4) 0", fontSize: "var(--mx-font-size-xs)" }}>
          {vault.owner?.name} · Level {vault.level} {vault.level_name}<br />
          <span className="mx-mono">{vault.root}</span>
        </div>
      </aside>
      <main className="hub-main">
        <Routes>
          <Route path="/" element={<Dashboard vault={vault} />} />
          <Route path="/domains" element={<Domains />} />
          <Route path="/review" element={<Review onChanged={refresh} />} />
          <Route path="/packs" element={<Packs onChanged={refresh} />} />
          <Route path="/settings" element={<Settings vault={vault} onChanged={refresh} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
