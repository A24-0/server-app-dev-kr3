from typing import FrozenSet

ROLE_PERMISSIONS: dict[str, FrozenSet[str]] = {
    "admin": frozenset(
        {
            "todo:create",
            "todo:read",
            "todo:update",
            "todo:delete",
            "rbac:admin",
            "rbac:user_rw",
            "rbac:guest_read",
        }
    ),
    "user": frozenset(
        {
            "todo:create",
            "todo:read",
            "todo:update",
            "rbac:user_rw",
            "rbac:guest_read",
        }
    ),
    "guest": frozenset({"todo:read", "rbac:guest_read"}),
}


def has_permission(role: str, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, frozenset())
    return permission in perms
