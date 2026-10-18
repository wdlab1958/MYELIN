import { spawn, execSync, type ChildProcess } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Starts the Hub API on an EMPTY temp directory (not yet a Vault) → onboarding path is exercised. */
export default async function globalSetup() {
  const repo = path.resolve(__dirname, "../../../..");
  const vault = mkdtempSync(path.join(tmpdir(), "myelin-e2e-"));
  const port = process.env.MYELIN_E2E_API_PORT ?? "8799";
  // The Vault pre-commit device (ADR-0011 §5) runs `${MYELIN_BIN:-myelin} doctor --staged`; on CI
  // runners `myelin` is not on PATH, so point it at the workspace venv for the tests' own commits.
  process.env.MYELIN_BIN ??= path.join(repo, ".venv", "bin", "myelin");
  // 도움말 챗봇(ADR-0013)은 로컬 Ollama 가 있으면 LLM 모드가 되어 답이 비결정적이다 → 닫힌 포트로 kb 모드 고정.
  const env = { ...process.env, MYELIN_PACKS: path.join(repo, "packs"), MYELIN_ASSISTANT_URL: "http://127.0.0.1:9" };
  const api: ChildProcess = spawn("uv", ["run", "myelin-hub", "--vault", vault, "--port", port, "--no-web"], {
    cwd: repo, env, stdio: ["ignore", "pipe", "pipe"],
  });
  api.stderr?.on("data", (d) => process.stderr.write(`[api] ${d}`));
  await waitFor(`http://127.0.0.1:${port}/api/health`, 30_000);
  writeFileSync(path.join(__dirname, ".e2e-state.json"), JSON.stringify({ vault, pid: api.pid }));
  process.env.MYELIN_E2E_VAULT = vault;
  return async () => {
    try { api.kill("SIGTERM"); } catch { /* ignore */ }
    try { execSync(`rm -rf "${vault}"`); } catch { /* ignore */ }
  };
}

async function waitFor(url: string, ms: number) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* retry */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`API did not start: ${url}`);
}
