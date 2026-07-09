import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import CostCenters from "../pages/CostCenters";
import { apiFetch } from "../lib/api";
import "../i18n";

vi.mock("../lib/api", () => ({ apiFetch: vi.fn() }));

const emptyList = { ok: true, json: async () => ({ data: [], meta: { page: 1, page_size: 25, total: 0 } }) };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BrowserRouter><CostCenters /></BrowserRouter>
    </QueryClientProvider>
  );
}

afterEach(() => vi.clearAllMocks());

describe("OrgAdminPage error handling", () => {
  it("shows a translated code-exists message on a 409 create and keeps the modal open", async () => {
    vi.mocked(apiFetch).mockImplementation(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return {
          ok: false,
          status: 409,
          json: async () => ({ title: "Conflict", detail: "code already exists", status: 409 }),
        } as unknown as Response;
      }
      return emptyList as unknown as Response;
    });

    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /^create$/i }));
    await user.type(screen.getByLabelText(/code/i), "CC1");
    await user.type(screen.getByLabelText(/^name$/i), "Marketing");
    await user.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText(/that code already exists/i)).toBeInTheDocument();
    // Modal stays open so the user can correct the input.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("prompts to select a file when import is clicked with no file chosen", async () => {
    vi.mocked(apiFetch).mockResolvedValue(emptyList as unknown as Response);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /import csv/i }));
    await waitFor(() => expect(screen.getByText(/select a csv file first/i)).toBeInTheDocument());
  });
});
