import { test, expect, type Page } from "@playwright/test";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Runs AFTER hub.spec.ts (same Vault, already onboarded with D1/D3/CLOUD-SEC, level 2, one promoted note).
 * Covers the menus not exercised there: Sub-MOC search, Pack editor (read-only → copy → save),
 * patch preview/apply, Commons candidates, Settings table layout, and special characters in note paths.
 * Every test also asserts the browser console stays free of errors.
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API = `http://127.0.0.1:${process.env.MYELIN_E2E_API_PORT ?? "8799"}`;
const state = () => JSON.parse(readFileSync(path.join(__dirname, ".e2e-state.json"), "utf-8")) as { vault: string };
const git = (args: string) => execSync(`git ${args}`, { cwd: state().vault, encoding: "utf-8" }).trim();

function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  return errors;
}

const FM = (id: string, domain: string, status: string, origin: string, extra = "") =>
  `---\nid: ${id}\ntype: evergreen\ndomain: [${domain}]\nstatus: ${status}\norigin: ${origin}\nconfidence: medium\n` +
  `classification: internal\nshare: false\nsource: []\ncreated: 2026-10-18\n${extra}tags: [e2e]\n---\n`;

test.describe.serial("Hub 메뉴 흐름 — Domains · Packs · Patches · Commons · Settings", () => {
  test("Sub-MOC 버튼은 주제 검색 패널을 열고 Obsidian 링크를 준다", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/domains");
    await page.getByTestId("orb-CLOUD-SEC").click();
    await expect(page.getByTestId("domain-detail")).toContainText("클라우드 보안");
    const chips = page.getByTestId("sub-moc");
    await expect(chips).toHaveCount(3);
    await chips.filter({ hasText: "IAM" }).click();
    const panel = page.getByTestId("sub-moc-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("MOC 노트 없음");
    const newLink = panel.getByRole("link", { name: /MOC 노트 만들기/ });
    await expect(newLink).toHaveAttribute("href", /^obsidian:\/\/new\?path=/);
    expect(decodeURIComponent((await newLink.getAttribute("href"))!)).toContain("10_Domains/CLOUD-SEC/CLOUD-SEC - IAM.md");
    await expect(panel).toContainText(/검색 결과 \d+/); // the _MOC itself lists "IAM", so ≥1 hit is correct
    // D1 has a verified note from hub.spec.ts → search hits render as a table with Obsidian links
    await page.getByTestId("orb-D1").click();
    await page.getByTestId("sub-moc").first().click();
    await expect(page.getByTestId("sub-moc-panel")).toContainText(/검색 결과 \d+/);
    expect(errors).toEqual([]);
  });

  test("Packs: Reference Pack 은 읽기 전용, 개인 Pack 으로 복사하면 저장(commit)된다", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/packs");
    await page.getByTestId("pack-open-brian.physical-ai").click();
    const editor = page.getByTestId("pack-editor");
    await expect(editor).toHaveAttribute("readonly", "");
    await expect(editor).toHaveValue(/pack: brian\.physical-ai/);
    await expect(page.getByTestId("pack-save")).toBeDisabled();
    await page.getByRole("button", { name: "개인 Pack 으로 복사" }).click();
    await expect(editor).not.toHaveAttribute("readonly", "");
    await expect(editor).toHaveValue(/pack: me\.physical-ai/);
    await page.getByRole("button", { name: "검증" }).click();
    await expect(page.getByText(/^ok · domains/)).toBeVisible();
    const before = git("rev-list --count HEAD");
    await page.getByTestId("pack-save").click();
    await expect(page.getByText(/^저장됨 · commit/)).toBeVisible();
    expect(Number(git("rev-list --count HEAD"))).toBe(Number(before) + 1);
    expect(git("log -1 --format=%s")).toMatch(/^\[myelin:/);
    expect(existsSync(path.join(state().vault, "packs", "me.physical-ai", "pack.yaml"))).toBeTruthy();
    await expect(page.getByTestId("pack-list")).toContainText("me.physical-ai");
    expect(git("status --porcelain")).toBe("");
    // the wizard's personal pack is editable
    await page.getByTestId("pack-open-me.my-domains").click();
    await expect(page.getByText(/me\.my-domains 을 불러왔다/)).toBeVisible();
    await expect(page.getByTestId("pack-save")).toBeEnabled();
    expect(errors).toEqual([]);
  });

  test("패치 제안: 미리보기 → diff → digest 검사 후 Apply → applied/ 로 이동", async ({ page }) => {
    const errors = watchConsole(page);
    const vault = state().vault;
    mkdirSync(path.join(vault, "_patches"), { recursive: true });
    writeFileSync(path.join(vault, "_patches", "e2e-link.patch.md"),
      "---\npatch: 1\ntarget: 10_Domains/D1/_MOC.md\nkind: append\nunder: \"## 최근 verified\"\norigin: claude\n" +
      "skill: link\ncreated: 2026-10-18\nrationale: e2e link patch\nstatus: proposed\n---\n## append\n- [[MYELIN 시작하기]]\n");
    await page.goto("/review");
    const row = page.getByTestId("patch-row").filter({ hasText: "e2e-link.patch.md" });
    await expect(row).toBeVisible();
    await expect(row.getByTestId("patch-apply")).toBeDisabled(); // preview first (digest)
    await row.getByTestId("patch-preview").click();
    await expect(row.getByTestId("patch-diff")).toContainText("+- [[MYELIN 시작하기]]");
    await row.getByTestId("patch-apply").click();
    await expect(page.getByTestId("review-toast")).toContainText(/Apply e2e-link\.patch\.md · commit [0-9a-f]{7}/);
    expect(existsSync(path.join(vault, "_patches", "applied", "e2e-link.patch.md"))).toBeTruthy();
    expect(existsSync(path.join(vault, "_patches", "e2e-link.patch.md"))).toBeFalsy();
    const moc = readFileSync(path.join(vault, "10_Domains", "D1", "_MOC.md"), "utf-8");
    // appended at the end of the "최근 verified" section (after its placeholder comment), before "열린 질문"
    expect(moc).toMatch(/## 최근 verified\n(?:<!--.*-->\n)?- \[\[MYELIN 시작하기\]\]\n+## 열린 질문/);
    expect(git("log -1 --format=%s")).toMatch(/^\[myelin:link\]/);
    expect(git("status --porcelain")).toBe("");
    await expect(page.getByTestId("patch-row").filter({ hasText: "e2e-link.patch.md" })).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test("제목에 # · ? · % 가 있는 초안도 Promote / Reject 된다", async ({ page }) => {
    const errors = watchConsole(page);
    const vault = state().vault;
    const dir = path.join(vault, "00_Inbox", "ai-drafts");
    writeFileSync(path.join(dir, "C# 메모 #1.md"), FM("20261018-1200-csharp", "D1", "draft", "claude") + "# C# 메모 #1\n\nbody\n");
    writeFileSync(path.join(dir, "왜? 100% 질문.md"), FM("20261018-1201-why", "D1", "draft", "claude") + "# 왜? 100% 질문\n\nbody\n");
    await page.goto("/review");
    const a = page.getByTestId("draft-row").filter({ hasText: "C# 메모 #1" });
    await expect(a).toBeVisible();
    await a.getByTestId("draft-read").click();
    await expect(a.getByTestId("draft-body")).toContainText("body");
    await a.getByTestId("promote").click();
    await expect(page.getByTestId("promoted-card")).toContainText("10_Domains/D1/C# 메모 #1.md");
    expect(existsSync(path.join(vault, "10_Domains", "D1", "C# 메모 #1.md"))).toBeTruthy();
    const b = page.getByTestId("draft-row").filter({ hasText: "왜? 100% 질문" });
    await expect(b).toBeVisible();
    await b.getByTestId("reject").click();
    await expect(page.getByTestId("review-toast")).toContainText(/Reject 왜\? 100% 질문 · commit/);
    expect(existsSync(path.join(dir, "왜? 100% 질문.md"))).toBeFalsy();
    expect(git("status --porcelain")).toBe("");
    expect(errors).toEqual([]);
  });

  test("Commons 후보: share:true 인 verified 노트만 나오고, 확인 체크 후에만 제안 가능", async ({ page }) => {
    const errors = watchConsole(page);
    const vault = state().vault;
    const note = path.join(vault, "10_Domains", "D1", "MYELIN 시작하기.md");
    writeFileSync(note, readFileSync(note, "utf-8").replace("share: false", "share: true"));
    execSync("git add -A && git commit -q -m 'e2e: mark share' ", { cwd: vault });
    // a confidential note must never become a candidate even with share: true
    writeFileSync(path.join(vault, "10_Domains", "D1", "비밀 노트.md"),
      FM("20261018-1300-secret", "D1", "verified", "human", "reviewed: 2026-10-18\n").replace("classification: internal", "classification: confidential").replace("share: false", "share: true") + "# 비밀 노트\n\n고객 A 계약\n");
    // Vault pre-commit device (ADR-0011 §5): a confidential note marked share:true cannot be committed
    // by any tool; only a human may bypass with --no-verify (we do, to test the Hub's own gate next).
    let rejected = "";
    try { execSync("git add -A && git commit -q -m 'e2e: secret'", { cwd: vault, stdio: "pipe" }); }
    catch (e) { rejected = String((e as { stdout?: Buffer; stderr?: Buffer }).stdout ?? "") + String((e as { stderr?: Buffer }).stderr ?? ""); }
    expect(rejected).toContain("confidential-share");
    execSync("git commit -q --no-verify -m 'e2e: secret (human bypass)'", { cwd: vault });
    await page.goto("/review");
    const rows = page.getByTestId("commons-row");
    await expect(rows.filter({ hasText: "MYELIN 시작하기" })).toBeVisible();
    // no Commons clone yet → the Hub says so up front and never offers a button that would fail
    await expect(page.getByTestId("commons-notice")).toContainText("Commons clone");
    await expect(rows.filter({ hasText: "MYELIN 시작하기" }).getByTestId("commons-publish")).toBeDisabled();
    const commons = path.join(path.dirname(vault), path.basename(vault) + "-commons");
    execSync(`uv run myelin commons init "${commons}"`, { cwd: path.resolve(__dirname, "../../../.."), stdio: "ignore" });
    await page.goto("/settings");
    await expect(page.getByTestId("commons-status")).toContainText("Commons clone");
    // enabling Commons without a remote is refused in the UI (no half-valid request reaches the API)
    await page.getByTestId("commons-enabled").check();
    await expect(page.getByTestId("commons-remote-required")).toBeVisible();
    await expect(page.getByTestId("settings-save")).toBeDisabled();
    await page.getByTestId("commons-enabled").uncheck();
    await expect(page.getByTestId("settings-save")).toBeEnabled();
    await page.getByTestId("commons-local").fill(commons);
    await page.getByTestId("settings-save").click();
    await expect(page.getByTestId("settings-msg")).toContainText("commit");
    await page.goto("/settings");
    await expect(page.getByTestId("commons-status")).toContainText("제안 가능");
    await page.goto("/review");
    await expect(page.getByTestId("commons-notice")).toHaveCount(0);
    const secret = rows.filter({ hasText: "비밀 노트" });
    if (await secret.count()) {
      await expect(secret).toContainText("blocked");
      await expect(secret.getByTestId("commons-publish")).toBeDisabled();
    }
    const row = rows.filter({ hasText: "MYELIN 시작하기" });
    await expect(row).toContainText("publishable");
    await expect(row.getByTestId("commons-publish")).toBeDisabled(); // confirmation checkbox first
    await row.getByRole("checkbox", { name: /기밀이 없음/ }).check();
    await expect(row.getByTestId("commons-pr")).not.toBeChecked(); // PR 은 opt-in; 로컬 브랜치까지만
    await expect(page.getByTestId("commons-identity")).toContainText("실명");
    await row.getByTestId("commons-publish").click();
    await expect(page.getByTestId("review-toast")).toContainText(/Commons 제안 MYELIN 시작하기 · commit/);
    expect(execSync("git branch --list 'publish/*'", { cwd: commons, encoding: "utf-8" })).toMatch(/publish\//);
    expect(git("status --porcelain")).toBe("");
    expect(errors).toEqual([]);
  });

  test("Settings: Skill 표가 카드 안에 들어가고 셀 글자가 넘치지 않는다", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/settings");
    const table = page.locator(".hub-card--table .mx-table");
    await expect(table).toBeVisible();
    const card = await page.locator(".hub-card--table").boundingBox();
    const tbl = await table.boundingBox();
    expect(tbl!.x + tbl!.width).toBeLessThanOrEqual(card!.x + card!.width + 0.5);
    const overflow = await table.evaluate((t) => Array.from(t.querySelectorAll("td")).filter((td) => td.scrollWidth > td.clientWidth + 1).length);
    expect(overflow).toBe(0);
    const rows = await table.locator("tbody tr").count();
    expect(rows).toBe(7); // ingest distill interview review link compose ip-scan
    await expect(page.getByTestId("level-2")).toHaveAttribute("aria-pressed", "true");
    expect(errors).toEqual([]);
  });

  test("Dashboard: 모든 쓰기가 git log 에 남고 작업 트리는 깨끗하다", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/");
    await expect(page.getByTestId("git-log")).toContainText("[myelin:link]");
    await expect(page.getByTestId("git-log")).toContainText("[myelin:review]");
    // 복리 장치: 강도 분포와 재사용 비율이 Dashboard 에, 강도 라벨이 노트 표에 텍스트로 보인다
    await expect(page.getByTestId("kpi-reused-pct")).toBeVisible();
    await expect(page.getByTestId("strength-table")).toContainText("1");
    await page.goto("/domains");
    await page.getByTestId("orb-D1").click();
    await expect(page.getByTestId("domain-detail")).toContainText(/myelin ×\d/);
    const status = (await (await fetch(`${API}/api/git/status`)).json()) as { clean: boolean };
    expect(status.clean).toBeTruthy();
    expect(errors).toEqual([]);
  });
});
