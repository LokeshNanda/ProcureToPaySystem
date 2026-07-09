import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { setRefreshToken } from "../lib/api";

function SignOutButton() {
  const { signOut } = useAuth();
  return <button onClick={() => void signOut()}>sign out</button>;
}

describe("AuthContext signOut", () => {
  beforeEach(() => {
    setRefreshToken("some-refresh-token");
  });

  afterEach(() => {
    setRefreshToken(null);
    vi.restoreAllMocks();
  });

  it("calls the backend logout endpoint with the refresh token", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 })
    );

    render(
      <AuthProvider>
        <SignOutButton />
      </AuthProvider>
    );
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/auth/logout"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ refresh_token: "some-refresh-token" }),
        })
      );
    });
  });

  it("clears local session even if the backend call fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    render(
      <AuthProvider>
        <SignOutButton />
      </AuthProvider>
    );

    expect(() => fireEvent.click(screen.getByRole("button", { name: /sign out/i }))).not.toThrow();

    await waitFor(() => {
      expect(localStorage.getItem("refresh_token")).toBeNull();
    });
  });
});
