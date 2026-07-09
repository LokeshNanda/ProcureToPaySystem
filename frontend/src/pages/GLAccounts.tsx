import { useTranslation } from "react-i18next";
import OrgAdminPage from "../components/org/OrgAdminPage";

export default function GLAccounts() {
  const { t } = useTranslation();
  return (
    <OrgAdminPage
      resource="gl-accounts"
      hasOwner={false}
      title={t("org.glAccountsTitle")}
      entityLabel={t("org.glAccountsTitle")}
    />
  );
}
