from typing import List
from fastapi import Depends
from app.core.exceptions import ForbiddenException


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: "Profile"):
        if not user:
            raise ForbiddenException(message="User not authenticated", code="unauthorized")
        if user.role not in self.allowed_roles:
            raise ForbiddenException(
                message=f"Access denied for role '{user.role}'. Required one of: {self.allowed_roles}",
                code="forbidden",
            )
        return user


# Common role helpers
require_staff = RoleChecker(["reception", "doctor", "pharmacy", "lab", "accountant", "manager"])
require_patient = RoleChecker(["patient"])
require_doctor = RoleChecker(["doctor", "manager"])
require_reception = RoleChecker(["reception", "manager"])
require_pharmacy = RoleChecker(["pharmacy", "manager"])
require_lab = RoleChecker(["lab", "manager"])
require_accountant = RoleChecker(["accountant", "manager"])
require_manager = RoleChecker(["manager"])
