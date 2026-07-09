from fastapi import Depends

from app.core.deps import get_current_active_user
from app.core.errors import ProblemException
from app.modules.users.models import User


class Roles:
    ADMIN = "Admin"
    PROCUREMENT_MANAGER = "ProcurementManager"
    REQUESTER = "Requester"
    APPROVER = "Approver"
    AP_CLERK = "APClerk"
    RECEIVER = "Receiver"
    AUDITOR = "Auditor"
    VENDOR = "Vendor"


ALL_ROLES = [
    Roles.ADMIN, Roles.PROCUREMENT_MANAGER, Roles.REQUESTER, Roles.APPROVER,
    Roles.AP_CLERK, Roles.RECEIVER, Roles.AUDITOR, Roles.VENDOR,
]


def require_roles(*required: str):
    async def _dep(user: User = Depends(get_current_active_user)) -> User:
        held = {r.name for r in user.roles}
        if not held.intersection(required):
            raise ProblemException(403, "Forbidden", "You lack the required role.")
        return user

    return Depends(_dep)
