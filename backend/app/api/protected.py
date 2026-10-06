"""
Protected test endpoints demonstrating role-based access control.

These are Phase 1 placeholder routes that prove the RBAC system works.
They will be replaced/expanded in later phases with real business logic.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import require_faculty, require_student
from app.models.user import User

router = APIRouter(tags=["Protected (RBAC test)"])


@router.get(
    "/api/student/dashboard",
    summary="Student dashboard (student role required)",
)
def student_dashboard(current_user: User = Depends(require_student)) -> dict:
    """
    Student-only endpoint.
    Returns 403 if the authenticated user is not a STUDENT.
    """
    return {
        "message": f"Welcome, {current_user.full_name}! This is your student dashboard.",
        "user_id": current_user.id,
        "role": current_user.role,
        "phase": "Phase 2 will add assignments, submissions, and performance analytics here.",
    }


@router.get(
    "/api/faculty/dashboard",
    summary="Faculty dashboard (faculty role required)",
)
def faculty_dashboard(current_user: User = Depends(require_faculty)) -> dict:
    """
    Faculty-only endpoint.
    Returns 403 if the authenticated user is not FACULTY.
    """
    return {
        "message": f"Welcome, {current_user.full_name}! This is your faculty dashboard.",
        "user_id": current_user.id,
        "role": current_user.role,
        "phase": "Phase 2 will add class management, assignment creation, and analytics here.",
    }
