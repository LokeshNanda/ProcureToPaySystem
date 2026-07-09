import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(false);
    try {
      await signIn(email, password);
      navigate("/");
    } catch {
      setError(true);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto mt-24 flex max-w-sm flex-col gap-3">
      <h1 className="text-xl font-semibold">{t("login.title")}</h1>
      <input aria-label={t("login.email")} className="border p-2" value={email}
        onChange={(e) => setEmail(e.target.value)} placeholder={t("login.email")} />
      <input aria-label={t("login.password")} type="password" className="border p-2" value={password}
        onChange={(e) => setPassword(e.target.value)} placeholder={t("login.password")} />
      {error && <p role="alert" className="text-red-600">{t("login.error")}</p>}
      <button type="submit" className="bg-black p-2 text-white">{t("login.submit")}</button>
    </form>
  );
}
