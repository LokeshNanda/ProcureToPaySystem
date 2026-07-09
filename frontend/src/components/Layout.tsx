import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const { t } = useTranslation();
  const isAdmin = user?.roles.some((r) => r.name === "Admin") ?? false;
  return (
    <div>
      <header className="flex justify-between border-b p-4">
        <div className="flex items-center gap-6">
          <span className="font-semibold">OpenP2P</span>
          {isAdmin && (
            <nav className="flex gap-4 text-sm">
              <Link to="/cost-centers" className="underline">{t("nav.costCenters")}</Link>
              <Link to="/gl-accounts" className="underline">{t("nav.glAccounts")}</Link>
            </nav>
          )}
        </div>
        <button onClick={signOut} className="text-sm underline">{t("home.logout")}</button>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
