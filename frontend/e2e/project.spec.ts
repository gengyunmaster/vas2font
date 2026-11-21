import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const notebook = new URL("../../samples/representative-100-v1/notebook.json", import.meta.url)
  .pathname;

test("complete project, inspection, generation, and migration workflow", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByLabel("Font name").fill("Automated Regression Font");
  await page.getByLabel("Version", { exact: true }).fill("1.4");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await page.getByRole("button", { name: "Enter project" }).click();
  await expect(page.getByRole("heading", { name: "Automated Regression Font" })).toBeVisible();

  await page.locator(".nav-item").filter({ hasText: "Uploads" }).click();
  await page.locator('input[type="file"]').setInputFiles(notebook);
  await page
    .getByLabel("Character set template")
    .selectOption({ label: "representative-100 v1 (100 characters)" });
  await page.getByRole("button", { name: "Upload notebook" }).click();
  await expect(page.getByText("100 glyphs", { exact: true })).toBeVisible();

  await page.locator(".nav-item").filter({ hasText: "Glyphs" }).click();
  await expect(page.locator(".glyph-card")).toHaveCount(48);
  await page.getByLabel("Search glyphs").fill("U+6C38");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".glyph-card")).toHaveCount(1);
  await page.locator(".glyph-card input[type=checkbox]").check();
  await page.getByRole("button", { name: "Create correction template (1)" }).click();
  await expect(page.locator(".template-form textarea")).toHaveValue("永");
  await page.getByRole("button", { name: "Create template", exact: true }).click();
  await expect(page.locator(".template-card").filter({ hasText: "Corrections" })).toBeVisible();

  await page.locator(".nav-item").filter({ hasText: "Generate" }).click();
  await page.locator(".generate-actions").getByRole("button", { name: "Generate font" }).click();
  await expect(page.getByRole("link", { name: "Download OTF" })).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".generation-progress strong")).toHaveText("100%");
  const fontDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download OTF" }).click();
  const fontPath = testInfo.outputPath("font.otf");
  await (await fontDownload).saveAs(fontPath);
  expect(readFileSync(fontPath).subarray(0, 4).toString()).toBe("OTTO");

  await page.locator(".nav-item").filter({ hasText: "Overview" }).click();
  const backupDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download backup" }).click();
  const backupPath = testInfo.outputPath("backup.json");
  await (await backupDownload).saveAs(backupPath);
  const backup = JSON.parse(readFileSync(backupPath, "utf8"));
  expect(backup.format).toBe("vas2font-project-backup");
  expect(backup.uploads).toHaveLength(1);
  expect(backup.templates).toHaveLength(1);
  expect(readFileSync(backupPath, "utf8")).not.toContain("access_code");

  await page.getByRole("button", { name: "Delete project", exact: true }).click();
  await page.locator(".modal").getByRole("button", { name: "Delete project", exact: true }).click();
  await expect(page.getByText("Project deleted", { exact: true })).toBeVisible();

  await page.locator(".backup-file-button input").setInputFiles(backupPath);
  await expect(page.getByText("Your private access code")).toBeVisible();
  await page.getByRole("button", { name: "Enter project" }).click();
  await page.locator(".nav-item").filter({ hasText: "Uploads" }).click();
  await expect(page.locator(".upload-row")).toHaveCount(1);
  await page.locator(".nav-item").filter({ hasText: "Glyphs" }).click();
  await expect(page.getByText("100", { exact: true }).first()).toBeVisible();
  expect(errors).toEqual([]);
});
