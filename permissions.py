"""permissions.py — Role-Based Access Control (RBAC) for CapMatch (Plan part 5).

Three roles, each with DIFFERENT permissions (the brief's requirement):

    issuer   -> manage their OWN company profile; see who matched them
    investor -> browse issuers; run matching; publish new investors
    admin    -> full access: everything above + transactions + all data

Usage in main.py (FastAPI dependencies):

    @app.get("/admin/transactions")
    def tx(user=Depends(require_role("admin"))):
        ...

    # or allow several roles:
    @app.get("/match/{id}")
    def match(id, user=Depends(require_any("investor", "admin"))):
        ...
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from auth import get_current_user

# What each role is allowed to DO (named permissions).
ROLE_PERMISSIONS = {
    "issuer": {
        "view_own_issuer",       # see/manage their own company
        "view_own_matches",      # see investors matched to them
        "run_matching",
    },
    "investor": {
        "view_issuers",          # browse all issuers seeking capital
        "run_matching",          # score/rank investors for an issuer
        "publish_investor",      # add a new investor via the pipeline
        "view_own_matches",
    },
    "admin": {
        "view_own_issuer", "view_own_matches", "run_matching",
        "view_issuers", "publish_investor",
        "view_all",              # see every issuer, investor, match
        "view_transactions",     # see funding transactions
        "manage_transactions",   # create/update transactions
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_role(*allowed_roles: str):
    """Dependency: allow ONLY these roles; 403 for everyone else."""
    def checker(user=Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires role: {', '.join(allowed_roles)}. "
                       f"You are '{user.get('role')}'.",
            )
        return user
    return checker


# convenient alias so endpoints read naturally: Depends(require_any("investor","admin"))
require_any = require_role


def require_permission(permission: str):
    """Dependency: allow anyone whose role HAS this named permission."""
    def checker(user=Depends(get_current_user)):
        if not has_permission(user.get("role", ""), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permission: '{permission}'.",
            )
        return user
    return checker
