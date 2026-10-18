import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SHOTS = process.env.MYELIN_E2E_SCREENSHOTS === "1";
const OUT = path.resolve(__dirname, "../../../../docs/reports/P6");
const API = `http://127.0.0.1:${process.env.MYELIN_E2E_API_PORT ?? "8799"}`;

async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}

async function gitStatus() {
  const r = await fetch(`${API}/api/git/status`);
  return (await r.json()) as { repo: boolean; clean: boolean; changes: string[] };
}

test.describe.serial("신규 사용자 온보딩 → 첫 노트 승격", () => {
  test("온보딩 마법사로 Vault 를 만든다", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("onboarding")).toBeVisible();
    await page.getByTestId("input-name").fill("E2E Tester");
    await page.getByTestId("select-primary").selectOption("D1");
    await page.getByTestId("select-research").selectOption("D3");
    // 직접 정의한 Domain 을 Growth 로 — 개인 Pack(me.my-domains) 경로를 함께 검증한다
    await page.getByTestId("custom-id").fill("cloud sec");
    await page.getByTestId("custom-name").fill("클라우드 보안");
    await page.getByTestId("custom-submocs").fill("IAM, 네트워크, 로깅");
    await page.getByTestId("custom-add").click();
    await expect(page.getByTestId("onboarding-error")).toHaveCount(0);
    await page.getByTestId("select-growth").selectOption("CLOUD-SEC");
    await shot(page, "00-onboarding");
    await page.getByTestId("onboarding-submit").click();
    await expect(page.getByTestId("kpi-grid")).toBeVisible({ timeout: 30_000 });
    const state = JSON.parse(readFileSync(path.join(__dirname, ".e2e-state.json"), "utf-8"));
    expect(existsSync(path.join(state.vault, "myelin.yaml"))).toBeTruthy();
    expect(existsSync(path.join(state.vault, ".git"))).toBeTruthy();
    expect(existsSync(path.join(state.vault, "packs", "me.my-domains", "pack.yaml"))).toBeTruthy();
    expect(existsSync(path.join(state.vault, "10_Domains", "CLOUD-SEC", "_MOC.md"))).toBeTruthy();
    const domains = (await (await fetch(`${API}/api/domains`)).json()) as { id: string; role: string; pack?: string }[];
    expect(domains.find((d) => d.id === "CLOUD-SEC")).toMatchObject({ role: "growth", pack: "me.my-domains" });
    await shot(page, "01-dashboard");
  });

  test("읽기 전용 화면을 모두 돌아도 Vault 는 변하지 않는다", async ({ page }) => {
    const before = await gitStatus();
    expect(before.clean).toBeTruthy();
    await page.goto("/domains");
    await expect(page.getByTestId("domain-map")).toBeVisible();
    await expect(page.getByTestId("orb-D1")).toBeVisible();
    await page.getByTestId("orb-D3").click();
    await expect(page.getByTestId("domain-detail")).toContainText("D3");
    await shot(page, "02-my-domains");
    await page.goto("/packs");
    await expect(page.getByTestId("pack-list")).toContainText("brian.physical-ai");
    await shot(page, "03-domain-packs");
    await page.goto("/settings");
    await expect(page.getByTestId("settings-save")).toBeVisible();
    await shot(page, "04-settings");
    await page.goto("/review");
    await expect(page.getByTestId("draft-list")).toContainText("MYELIN 시작하기");
    await shot(page, "05-review-gate");
    const after = await gitStatus();
    expect(after.clean).toBeTruthy(); // 사용자 클릭 없는 쓰기 0
    const log = await (await fetch(`${API}/api/git/log`)).json();
    expect(log.length).toBe(1); // only the init commit so far
  });

  test("Review Gate 에서 Promote 를 누르면 verified + git commit", async ({ page }) => {
    await page.goto("/review");
    const row = page.getByTestId("draft-row").first();
    await expect(row).toContainText("MYELIN 시작하기");
    await expect(row.getByTestId("promote")).toBeDisabled(); // 읽음 확인 장치: 본문을 열기 전에는 승격 불가
    await row.getByTestId("draft-read").click();
    await expect(row.getByTestId("draft-body")).toContainText("MYELIN");
    await row.getByTestId("promote").click();
    await expect(page.getByTestId("promoted-card")).toContainText("myelinated");
    await expect(page.getByTestId("review-toast")).toContainText("commit");
    await shot(page, "06-promoted");
    const log = (await (await fetch(`${API}/api/git/log`)).json()) as { subject: string }[];
    expect(log[0].subject).toMatch(/^\[myelin:review\] promote MYELIN 시작하기 → D1/);
    const notes = (await (await fetch(`${API}/api/notes?status=verified&domain=D1`)).json()) as { path: string; origin: string }[];
    const promoted = notes.find((n) => n.path.endsWith("MYELIN 시작하기.md"));
    expect(promoted?.path).toBe("10_Domains/D1/MYELIN 시작하기.md");
    expect(promoted?.origin).toBe("mixed");
    expect((await gitStatus()).clean).toBeTruthy();
    await page.goto("/");
    await expect(page.getByTestId("kpi-verified")).toHaveText(/[1-9]/);
    await expect(page.getByTestId("git-log")).toContainText("[myelin:review] promote");
    await shot(page, "07-dashboard-after-promote");
  });

  test("Settings 저장은 클릭으로 commit 을 만든다", async ({ page }) => {
    await page.goto("/settings");
    await page.getByTestId("level-2").click();
    await page.getByTestId("settings-save").click();
    await expect(page.getByTestId("settings-msg")).toContainText("commit");
    const log = (await (await fetch(`${API}/api/git/log`)).json()) as { subject: string }[];
    expect(log[0].subject).toBe("[myelin:settings] update myelin.yaml");
  });
});
