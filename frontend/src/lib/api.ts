const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const getRefreshToken = () => localStorage.getItem("refresh_token");
export const setRefreshToken = (t: string | null) =>
  t ? localStorage.setItem("refresh_token", t) : localStorage.removeItem("refresh_token");

async function refresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  });
  if (!resp.ok) return false;
  const data = await resp.json();
  setAccessToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return true;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  if (resp.status === 401 && retry && (await refresh())) return apiFetch(path, init, false);
  return resp;
}

export async function login(email: string, password: string) {
  const resp = await fetch(`${BASE}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) throw new Error("login_failed");
  return resp.json() as Promise<{ access_token: string; refresh_token: string }>;
}

export async function logout(refreshToken: string): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}
