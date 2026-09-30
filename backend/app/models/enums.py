from enum import Enum


class UserRole(str, Enum):
    """System-level User Roles (RBAC)."""
    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class CaseStatus(str, Enum):
    """Controlled lifecycle statuses for forensic cases."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CaseAccessRole(str, Enum):
    """Case-level authorization membership roles."""
    LEAD = "LEAD"
    CONTRIBUTOR = "CONTRIBUTOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class AuditAction(str, Enum):
    """Categorized audit event action identifiers."""
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    USER_CREATE = "USER_CREATE"
    CASE_CREATE = "CASE_CREATE"
    CASE_UPDATE = "CASE_UPDATE"
    CASE_MEMBER_ADD = "CASE_MEMBER_ADD"
    CASE_MEMBER_UPDATE = "CASE_MEMBER_UPDATE"
    CASE_MEMBER_REMOVE = "CASE_MEMBER_REMOVE"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
