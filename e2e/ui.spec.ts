import { test, expect } from "playwright/test";

test.describe("DocFlow", () => {
  test("register, upload a document, read the extract, and delete it", async ({ page, request }) => {
    const email = `e2e${Date.now()}@example.com`;
    await page.goto("/");
    await page.getByRole("tab", { name: "Create account" }).click();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("Pipeline123");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("No documents yet. Upload one above.")).toBeVisible();

    await page.getByLabel(/^File/).setInputFiles({
      name: "acme-invoice.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "Invoice 4471 from Acme Corp. The total of $1,250.00 is due on 2026-11-15. " +
          "Send questions to billing@acme.test or call +1 (415) 555-0199.",
      ),
    });
    await page.getByRole("button", { name: "Process document" }).click();

    const row = page.getByRole("button", { name: /acme-invoice\.txt/ });
    await expect(row.getByText("completed")).toBeVisible({ timeout: 20_000 });
    const detail = page.getByRole("region", { name: "Details for acme-invoice.txt" });
    await expect(detail.getByText("$1,250.00", { exact: true })).toBeVisible();
    await expect(detail.getByText("2026-11-15", { exact: true })).toBeVisible();
    await expect(detail.getByText("1 email, 1 phone")).toBeVisible();
    await expect(detail.locator("pre")).toContainText("[EMAIL]");

    const events = await (await request.get("http://localhost:8090/events")).json();
    expect(events.some((e: { body: { title: string; status: string } }) => e.body.title === "acme-invoice.txt" && e.body.status === "completed")).toBe(true);

    page.once("dialog", (d) => d.accept());
    await detail.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("No documents yet. Upload one above.")).toBeVisible();
  });

  test("pasted text and validation messages", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Create account" }).click();
    await page.getByLabel("Email").fill(`weak${Date.now()}@example.com`);
    await page.getByLabel("Password").fill("allletters");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.locator("p.error")).toHaveText("Use at least one letter and one digit.");

    await page.getByLabel("Password").fill("Letters123");
    await page.getByRole("button", { name: "Create account" }).click();
    await page.getByRole("tab", { name: "Paste text" }).click();
    await page.getByLabel("Title").fill("Meeting notes");
    await page.getByLabel("Text").fill("La reunión es el lunes para revisar el presupuesto de la empresa con los clientes.");
    await page.getByRole("button", { name: "Process document" }).click();
    const detail = page.getByRole("region", { name: "Details for Meeting notes" });
    await expect(detail.getByText("es", { exact: true })).toBeVisible({ timeout: 20_000 });
  });
});
