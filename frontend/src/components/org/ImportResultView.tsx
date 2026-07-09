import { useTranslation } from "react-i18next";
import type { ImportResult } from "./types";

export default function ImportResultView({ result }: { result: ImportResult }) {
  const { t } = useTranslation();
  return (
    <div className="mt-3 rounded border p-3 text-sm">
      <p>{t("org.importResult", { created: result.created, updated: result.updated, errors: result.errors.length })}</p>
      {result.errors.length > 0 && (
        <div className="mt-2">
          <p className="font-medium">{t("org.importErrorsTitle")}</p>
          <ul className="list-disc pl-6">
            {result.errors.map((e, idx) => (
              <li key={`${e.row}-${idx}`} className="text-red-700">
                {t("org.rowError", { row: e.row, code: e.code, reason: e.reason })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
