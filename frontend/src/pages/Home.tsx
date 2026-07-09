import { useTranslation } from "react-i18next";
import Layout from "../components/Layout";
import { useAuth } from "../auth/AuthContext";

export default function Home() {
  const { t } = useTranslation();
  const { user } = useAuth();
  return (
    <Layout>
      <h1 className="text-lg">{t("home.welcome", { name: user?.full_name })}</h1>
      <p className="mt-2 text-sm text-gray-600">{user?.email}</p>
      <h2 className="mt-4 font-medium">{t("home.roles")}</h2>
      <ul className="list-disc pl-6">{user?.roles.map((r) => <li key={r.name}>{r.name}</li>)}</ul>
    </Layout>
  );
}
