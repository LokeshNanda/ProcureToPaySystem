import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { OrgFormValues, OrgItem } from "./types";

type Props = {
  title: string;
  hasOwner: boolean;
  initial: OrgItem | null;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (values: OrgFormValues) => void;
};

// Mounted only while the modal is open (see OrgAdminPage), so component-local
// state can be seeded straight from `initial` without an effect: closing and
// reopening naturally remounts this component with fresh state.
export default function OrgFormModal({ title, hasOwner, initial, submitting, onClose, onSubmit }: Props) {
  const { t } = useTranslation();
  const [code, setCode] = useState(initial?.code ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [ownerId, setOwnerId] = useState(initial?.owner_id ?? "");

  const isEdit = initial !== null;

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/40" role="dialog" aria-modal="true">
      <form
        className="w-full max-w-md rounded bg-white p-6 shadow"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ code, name, owner_id: ownerId });
        }}
      >
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>

        <label className="mb-1 block text-sm font-medium" htmlFor="org-code">{t("org.code")}</label>
        <input
          id="org-code"
          className="mb-1 w-full rounded border p-2 disabled:bg-gray-100"
          value={code}
          disabled={isEdit}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        {isEdit && <p className="mb-3 text-xs text-gray-500">{t("org.codeImmutable")}</p>}
        {!isEdit && <div className="mb-3" />}

        <label className="mb-1 block text-sm font-medium" htmlFor="org-name">{t("org.name")}</label>
        <input
          id="org-name"
          className="mb-3 w-full rounded border p-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />

        {hasOwner && (
          <>
            <label className="mb-1 block text-sm font-medium" htmlFor="org-owner">{t("org.ownerIdOptional")}</label>
            <input
              id="org-owner"
              className="mb-3 w-full rounded border p-2"
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
            />
          </>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="rounded border px-3 py-1.5 text-sm" onClick={onClose}>
            {t("org.cancel")}
          </button>
          <button
            type="submit"
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={submitting}
          >
            {t("org.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
