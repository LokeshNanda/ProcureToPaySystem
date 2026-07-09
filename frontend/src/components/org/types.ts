export type OrgItem = {
  id: string;
  code: string;
  name: string;
  owner_id?: string | null;
  is_active: boolean;
};

export type ListMeta = { page: number; page_size: number; total: number };

export type ListResponse = { data: OrgItem[]; meta: ListMeta };

export type ImportRowError = { row: number; code: string; reason: string };

export type ImportResult = { created: number; updated: number; errors: ImportRowError[] };

export type ActiveFilter = "true" | "false" | "all";

export type OrgFormValues = { code: string; name: string; owner_id: string };
