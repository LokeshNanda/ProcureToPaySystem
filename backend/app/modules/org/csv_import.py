import csv
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.org import service
from app.modules.users.service import get_by_email


def _rows(csv_text: str, required: set[str]) -> tuple[list[dict], set[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = {(f or "").strip() for f in (reader.fieldnames or [])}
    if reader.fieldnames is None or not required.issubset(fieldnames):
        return (
            [],
            fieldnames,
            [{"row": 1, "code": None, "reason": f"CSV must have a header row with columns: {sorted(required)}"}],
        )
    return list(reader), fieldnames, []


def _truthy(val: str | None, default: bool = True) -> bool:
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "active"}


async def import_cost_centers(db: AsyncSession, csv_text: str) -> dict:
    rows, fieldnames, structural = _rows(csv_text, {"code", "name"})
    if structural:
        return {"created": 0, "updated": 0, "errors": structural}
    has_owner_col = "owner_email" in fieldnames
    has_active_col = "active" in fieldnames
    created = updated = 0
    errors: list[dict] = []
    for i, raw in enumerate(rows, start=2):  # row 1 is the header
        code = (raw.get("code") or "").strip()
        name = (raw.get("name") or "").strip()
        if not code or not name:
            errors.append({"row": i, "code": code or None, "reason": "code and name are required"})
            continue

        # owner_id semantics: None -> clear/unset; service._UNSET -> leave unchanged.
        # Only touch owner when the owner_email column is present in the header.
        owner_id: object = service._UNSET
        if has_owner_col:
            owner_email = (raw.get("owner_email") or "").strip()
            if owner_email:
                owner = await get_by_email(db, owner_email)
                if owner is None:
                    errors.append({"row": i, "code": code, "reason": f"unknown owner email '{owner_email}'"})
                    continue
                owner_id = owner.id
            else:
                owner_id = None  # column present, blank cell -> clear owner

        existing = await service.get_cost_center_by_code(db, code)
        if existing is None:
            # On create there is no prior owner; _UNSET means "no owner".
            create_owner = None if owner_id is service._UNSET else owner_id
            cc = await service.create_cost_center(db, code=code, name=name, owner_id=create_owner)
            if has_active_col:
                await service.set_cost_center_active(db, cc, _truthy(raw.get("active")))
            created += 1
        else:
            await service.update_cost_center(db, existing, name=name, owner_id=owner_id)
            if has_active_col:
                await service.set_cost_center_active(db, existing, _truthy(raw.get("active")))
            updated += 1
    return {"created": created, "updated": updated, "errors": errors}


async def import_gl_accounts(db: AsyncSession, csv_text: str) -> dict:
    rows, fieldnames, structural = _rows(csv_text, {"code", "name"})
    if structural:
        return {"created": 0, "updated": 0, "errors": structural}
    has_active_col = "active" in fieldnames
    created = updated = 0
    errors: list[dict] = []
    for i, raw in enumerate(rows, start=2):
        code = (raw.get("code") or "").strip()
        name = (raw.get("name") or "").strip()
        if not code or not name:
            errors.append({"row": i, "code": code or None, "reason": "code and name are required"})
            continue
        existing = await service.get_gl_account_by_code(db, code)
        if existing is None:
            gl = await service.create_gl_account(db, code=code, name=name)
            if has_active_col:
                await service.set_gl_account_active(db, gl, _truthy(raw.get("active")))
            created += 1
        else:
            await service.update_gl_account(db, existing, name=name)
            if has_active_col:
                await service.set_gl_account_active(db, existing, _truthy(raw.get("active")))
            updated += 1
    return {"created": created, "updated": updated, "errors": errors}
