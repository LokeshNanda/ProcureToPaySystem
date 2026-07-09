import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { apiFetch } from "../../lib/api";
import OrgFormModal from "./OrgFormModal";
import ImportResultView from "./ImportResultView";
import type { ActiveFilter, ImportResult, ListResponse, OrgFormValues, OrgItem } from "./types";

type Props = {
  resource: "cost-centers" | "gl-accounts";
  hasOwner: boolean;
  title: string;
  entityLabel: string;
};

const PAGE_SIZE = 25;

// Error carrying the HTTP status so onError handlers can special-case 409.
type ApiError = Error & { status?: number };

// Reads an RFC 7807 problem+json body (best-effort) and throws an Error that
// carries the HTTP status plus a human-readable detail/title.
async function throwProblem(res: Response): Promise<never> {
  let detail = "";
  let title = "";
  try {
    const body = await res.json();
    detail = body.detail ?? "";
    title = body.title ?? "";
  } catch {
    // non-JSON error body: fall through with empty detail/title
  }
  throw Object.assign(new Error(detail || title || "Request failed"), { status: res.status });
}

export default function OrgAdminPage({ resource, hasOwner, title, entityLabel }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<ActiveFilter>("true");
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OrgItem | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const listKey = ["org", resource, filter, page];

  // Maps a save error (create/update) to a translated message: 409 -> code
  // already exists, otherwise a generic save error with the server detail.
  const saveErrorMessage = (err: ApiError) =>
    err.status === 409 ? t("org.codeExists") : t("org.saveError", { detail: err.message });

  const { data, isLoading, isError } = useQuery({
    queryKey: listKey,
    queryFn: async (): Promise<ListResponse> => {
      const r = await apiFetch(`/${resource}?active=${filter}&page=${page}&page_size=${PAGE_SIZE}`);
      if (!r.ok) throw new Error("load_failed");
      return r.json();
    },
  });

  const invalidateList = () => queryClient.invalidateQueries({ queryKey: ["org", resource] });

  const createMutation = useMutation({
    mutationFn: async (values: OrgFormValues) => {
      const body: Record<string, unknown> = { code: values.code, name: values.name };
      if (hasOwner && values.owner_id) body.owner_id = values.owner_id;
      const r = await apiFetch(`/${resource}`, { method: "POST", body: JSON.stringify(body) });
      if (!r.ok) return throwProblem(r);
      return r.json();
    },
    onSuccess: () => {
      invalidateList();
      setFormError(null);
      setModalOpen(false);
    },
    onError: (err: ApiError) => setFormError(saveErrorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, values }: { id: string; values: OrgFormValues }) => {
      const body: Record<string, unknown> = { name: values.name };
      if (hasOwner) body.owner_id = values.owner_id || null;
      const r = await apiFetch(`/${resource}/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      if (!r.ok) return throwProblem(r);
      return r.json();
    },
    onSuccess: () => {
      invalidateList();
      setFormError(null);
      setModalOpen(false);
    },
    onError: (err: ApiError) => setFormError(saveErrorMessage(err)),
  });

  const deactivateMutation = useMutation({
    mutationFn: async (id: string) => {
      const r = await apiFetch(`/${resource}/${id}/deactivate`, { method: "POST" });
      if (!r.ok) return throwProblem(r);
      return r.json();
    },
    onSuccess: () => { setActionError(null); invalidateList(); },
    onError: (err: ApiError) => setActionError(t("org.saveError", { detail: err.message })),
  });

  const reactivateMutation = useMutation({
    mutationFn: async (id: string) => {
      const r = await apiFetch(`/${resource}/${id}/reactivate`, { method: "POST" });
      if (!r.ok) return throwProblem(r);
      return r.json();
    },
    onSuccess: () => { setActionError(null); invalidateList(); },
    onError: (err: ApiError) => setActionError(t("org.saveError", { detail: err.message })),
  });

  const importMutation = useMutation({
    mutationFn: async (file: File): Promise<ImportResult> => {
      const form = new FormData();
      form.append("file", file);
      const r = await apiFetch(`/${resource}/import`, { method: "POST", body: form });
      if (!r.ok) return throwProblem(r);
      return r.json();
    },
    onSuccess: (result) => {
      setActionError(null);
      setImportResult(result);
      invalidateList();
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err: ApiError) => {
      setImportResult(null);
      setActionError(t("org.importError", { detail: err.message }));
    },
  });

  const items = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function openCreate() {
    setFormError(null);
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(item: OrgItem) {
    setFormError(null);
    setEditing(item);
    setModalOpen(true);
  }

  function handleSubmit(values: OrgFormValues) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, values });
    } else {
      createMutation.mutate(values);
    }
  }

  function handleImportClick() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setImportResult(null);
      setActionError(t("org.selectFileFirst"));
      return;
    }
    importMutation.mutate(file);
  }

  return (
    <div>
      <h1 className="text-lg font-semibold">{title}</h1>

      <div className="mt-4 flex flex-wrap items-center gap-4">
        <div role="group" aria-label={t("org.status")} className="flex gap-1">
          <button
            type="button"
            className={`rounded border px-2 py-1 text-sm ${filter === "true" ? "bg-blue-600 text-white" : ""}`}
            onClick={() => { setFilter("true"); setPage(1); }}
          >
            {t("org.filterActive")}
          </button>
          <button
            type="button"
            className={`rounded border px-2 py-1 text-sm ${filter === "false" ? "bg-blue-600 text-white" : ""}`}
            onClick={() => { setFilter("false"); setPage(1); }}
          >
            {t("org.filterInactive")}
          </button>
          <button
            type="button"
            className={`rounded border px-2 py-1 text-sm ${filter === "all" ? "bg-blue-600 text-white" : ""}`}
            onClick={() => { setFilter("all"); setPage(1); }}
          >
            {t("org.filterAll")}
          </button>
        </div>

        <button
          type="button"
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
          onClick={openCreate}
        >
          {t("org.create")}
        </button>

        <div className="flex items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".csv" aria-label={t("org.chooseFile")} />
          <button type="button" className="rounded border px-3 py-1.5 text-sm" onClick={handleImportClick}>
            {t("org.import")}
          </button>
        </div>
      </div>

      {actionError && (
        <p role="alert" className="mt-3 text-sm text-red-700">{actionError}</p>
      )}

      {importResult && <ImportResultView result={importResult} />}

      <table className="mt-4 w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 pr-4">{t("org.code")}</th>
            <th className="py-2 pr-4">{t("org.name")}</th>
            {hasOwner && <th className="py-2 pr-4">{t("org.owner")}</th>}
            <th className="py-2 pr-4">{t("org.status")}</th>
            <th className="py-2 pr-4">{t("org.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr><td colSpan={5} className="py-3 text-gray-500">{t("org.loading")}</td></tr>
          )}
          {isError && (
            <tr><td colSpan={5} className="py-3 text-red-700">{t("org.loadError")}</td></tr>
          )}
          {!isLoading && !isError && items.length === 0 && (
            <tr><td colSpan={5} className="py-3 text-gray-500">{t("org.noResults")}</td></tr>
          )}
          {items.map((item) => (
            <tr key={item.id} className="border-b">
              <td className="py-2 pr-4">{item.code}</td>
              <td className="py-2 pr-4">{item.name}</td>
              {hasOwner && <td className="py-2 pr-4">{item.owner_id ?? ""}</td>}
              <td className="py-2 pr-4">
                <span className={`rounded px-2 py-0.5 text-xs ${item.is_active ? "bg-green-100 text-green-800" : "bg-gray-200 text-gray-700"}`}>
                  {item.is_active ? t("org.active") : t("org.inactive")}
                </span>
              </td>
              <td className="py-2 pr-4">
                <button type="button" className="mr-2 text-sm underline" onClick={() => openEdit(item)}>
                  {t("org.edit")}
                </button>
                {item.is_active ? (
                  <button
                    type="button"
                    className="text-sm underline"
                    onClick={() => deactivateMutation.mutate(item.id)}
                  >
                    {t("org.deactivate")}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="text-sm underline"
                    onClick={() => reactivateMutation.mutate(item.id)}
                  >
                    {t("org.reactivate")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-3 text-sm">
        <button
          type="button"
          className="rounded border px-2 py-1 disabled:opacity-50"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t("org.previous")}
        </button>
        <span>{t("org.pageOf", { page, totalPages })}</span>
        <button
          type="button"
          className="rounded border px-2 py-1 disabled:opacity-50"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
        >
          {t("org.next")}
        </button>
      </div>

      {modalOpen && (
        <OrgFormModal
          title={editing ? t("org.editTitle", { entity: entityLabel }) : t("org.createTitle", { entity: entityLabel })}
          hasOwner={hasOwner}
          initial={editing}
          submitting={createMutation.isPending || updateMutation.isPending}
          error={formError}
          onClose={() => { setFormError(null); setModalOpen(false); }}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
