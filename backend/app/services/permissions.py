from app.models.enums import UserRole

PERMISSIONS = {
    UserRole.partner: {"*"},
    UserRole.admin: {"admin", "team", "settings"},
    UserRole.lawyer: {"cases", "clients", "documents", "tasks", "calendar"},
    UserRole.paralegal: {"cases", "documents", "tasks", "calendar"},
    UserRole.client: {"portal"},
}


def has_permission(role: UserRole, permission: str) -> bool:
    role_permissions = PERMISSIONS.get(role, set())
    return "*" in role_permissions or permission in role_permissions
