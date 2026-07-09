import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import GLAccounts from "../pages/GLAccounts";
import { queryClient } from "../lib/queryClient";
import "../i18n";

vi.mock("../lib/api", () => ({
  apiFetch: vi.fn(async () => ({ ok: true, json: async () => ({ data: [], meta: { page: 1, page_size: 25, total: 0 } }) })),
}));

describe("GLAccounts", () => {
  it("renders the title and create control", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter><GLAccounts /></BrowserRouter>
      </QueryClientProvider>
    );
    expect(screen.getByText(/gl accounts/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create/i })).toBeInTheDocument();
  });
});
