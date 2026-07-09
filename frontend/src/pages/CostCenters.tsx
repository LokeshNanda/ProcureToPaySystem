import { useTranslation } from "react-i18next";
import OrgAdminPage from "../components/org/OrgAdminPage";

export default function CostCenters() {
  const { t } = useTranslation();
  return (
    <OrgAdminPage
      resource="cost-centers"
      hasOwner
      title={t("org.costCentersTitle")}
      entityLabel={t("org.costCentersTitle")}
    />
  );
}
