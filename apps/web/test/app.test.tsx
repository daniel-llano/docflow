import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import HomePage from "@/app/page";
import { request, saveSession } from "@/lib/api";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const done = {
  id: "j1",
  title: "Acme invoice",
  filename: "invoice.pdf",
  status: "completed",
  attempts: 1,
  error: null,
  createdAt: "2026-10-28T10:00:00Z",
  finishedAt: "2026-10-28T10:00:01Z",
  result: {
    word_count: 120,
    reading_minutes: 1,
    language: "en",
    keywords: ["invoice", "acme"],
    amounts: ["$1,250.00"],
    dates: ["2026-11-15"],
    pii: { email: 1, phone: 0, card: 0, iban: 0 },
    pii_masked: true,
    summary: "Invoice 4471 from Acme.",
    masked_preview: "Contact [EMAIL].",
  },
};

describe("request", () => {
  it("turns FastAPI validation errors into a readable message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ detail: [{ msg: "Value error, Use at least one letter and one digit." }] }, 422));
    await expect(request("/api/auth/register", { method: "POST", body: "{}" })).rejects.toThrow("Use at least one letter and one digit.");
  });
});

describe("HomePage", () => {
  it("signs in and shows documents", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/auth/login")) return json({ token: "t", expiresAt: new Date(Date.now() + 60_000).toISOString(), email: "ann@example.com" });
      return json({ items: [done], total: 1 });
    });
    render(<HomePage />);

    await userEvent.type(await screen.findByLabelText("Email"), "ann@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Secret123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Acme invoice")).toBeInTheDocument();
    expect(screen.getByText("ann@example.com")).toBeInTheDocument();
  });

  it("shows extract details for a completed job", async () => {
    saveSession({ token: "t", expiresAt: new Date(Date.now() + 60_000).toISOString(), email: "ann@example.com" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ items: [done], total: 1 }));
    render(<HomePage />);

    await userEvent.click(await screen.findByRole("button", { name: /Acme invoice/ }));

    expect(screen.getByText("$1,250.00")).toBeInTheDocument();
    expect(screen.getByText("1 email")).toBeInTheDocument();
    expect(screen.getByText("Contact [EMAIL].")).toBeInTheDocument();
  });

  it("signs out when the session is rejected", async () => {
    saveSession({ token: "old", expiresAt: new Date(Date.now() + 60_000).toISOString(), email: "ann@example.com" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ detail: "Your session has expired. Sign in again." }, 401));
    render(<HomePage />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument());
  });
});
