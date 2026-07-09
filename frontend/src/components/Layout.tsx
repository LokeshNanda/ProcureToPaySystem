import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { signOut } = useAuth();
  const { t } = useTranslation();
  return (
    <div>
      <header className="flex justify-between border-b p-4">
        <span className="font-semibold">OpenP2P</span>
        <button onClick={signOut} className="text-sm underline">{t("home.logout")}</button>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
