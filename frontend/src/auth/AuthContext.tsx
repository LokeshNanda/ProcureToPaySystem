import { createContext, useContext, useState, type ReactNode } from "react";
import { apiFetch, login as apiLogin, setAccessToken, setRefreshToken } from "../lib/api";

type User = { id: string; email: string; full_name: string; roles: { name: string }[] };
type AuthState = { user: User | null; signIn: (e: string, p: string) => Promise<void>; signOut: () => void };

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  async function signIn(email: string, password: string) {
    const tokens = await apiLogin(email, password);
    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);
    const me = await apiFetch("/users/me/profile");
    if (!me.ok) throw new Error("profile_failed");
    setUser(await me.json());
  }

  function signOut() {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
  }

  return <Ctx.Provider value={{ user, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside provider");
  return v;
}
