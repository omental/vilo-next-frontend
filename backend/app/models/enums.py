import enum


class RecordStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class UserRole(str, enum.Enum):
    partner = "partner"
    lawyer = "lawyer"
    paralegal = "paralegal"
    admin = "admin"
    client = "client"
