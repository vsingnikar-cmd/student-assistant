"""Pydantic data models for profile, chat, exam notes, documents, and study plans."""

from datetime import date, datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    """Student profile data model."""
    id: str
    email: str
    username: str
    full_name: str
    course: str
    branch: str
    college: Optional[str] = ""
    semester: str
    subjects: List[str] = Field(default_factory=list)
    profile_completed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProfileUpdateRequest(BaseModel):
    """Payload for updating student profile."""
    full_name: str
    course: str
    branch: str
    college: Optional[str] = ""
    semester: str
    subjects: List[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """Single chat message data model."""
    id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    role: Literal["user", "assistant"]
    content: str
    created_at: Optional[datetime] = None


class ExamNotesRequest(BaseModel):
    """Parameters for generating exam notes."""
    subject: str
    topic: str
    marks: Literal[2, 5, 10]
    difficulty: Optional[str] = "Intermediate"
    additional_context: Optional[str] = None


class DocumentMetadata(BaseModel):
    """Document record data model."""
    id: Optional[str] = None
    user_id: Optional[str] = None
    filename: str
    page_count: int
    extracted_characters: int
    storage_path: Optional[str] = None
    processing_status: str = "completed"
    created_at: Optional[datetime] = None


class DocumentChunk(BaseModel):
    """Extracted text chunk with page range."""
    id: Optional[str] = None
    document_id: Optional[str] = None
    user_id: Optional[str] = None
    chunk_index: int
    page_start: int
    page_end: int
    chunk_text: str


class StudyPlanRecord(BaseModel):
    """Saved study plan data model."""
    id: Optional[str] = None
    user_id: Optional[str] = None
    title: str
    exam_date: date
    daily_hours: float
    subjects: List[str]
    plan_text: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def resolve_student_name(
    profile: Optional[dict] = None,
    email: str = "",
    username: str = "",
) -> str:
    """Intelligently resolves the student's actual display name from available profile data, username, or email.

    Guarantees that a student's real name or formatted username/email is shown,
    never falling back to a generic 'Student' placeholder when real details exist.
    """
    if profile and isinstance(profile, dict):
        fn = profile.get("full_name")
        if fn and isinstance(fn, str) and fn.strip() and fn.strip().lower() not in ("student", "user", "none", "null", "anonymous"):
            return fn.strip()

        meta = profile.get("user_metadata") or {}
        if isinstance(meta, dict):
            meta_fn = meta.get("full_name") or meta.get("name") or meta.get("display_name")
            if meta_fn and isinstance(meta_fn, str) and meta_fn.strip() and meta_fn.strip().lower() not in ("student", "user", "none", "null", "anonymous"):
                return meta_fn.strip()

        u = profile.get("username") or (meta.get("username") if isinstance(meta, dict) else None)
        if u and isinstance(u, str) and u.strip() and u.strip().lower() not in ("student", "user"):
            cleaned = u.replace(".", " ").replace("_", " ").replace("-", " ")
            words = [w.capitalize() for w in cleaned.split() if w and not w.isdigit()]
            if words:
                return " ".join(words)
            return u.strip().capitalize()

    if username and username.strip() and username.strip().lower() not in ("student", "user"):
        cleaned = username.replace(".", " ").replace("_", " ").replace("-", " ")
        words = [w.capitalize() for w in cleaned.split() if w and not w.isdigit()]
        if words:
            return " ".join(words)
        return username.strip().capitalize()

    if email and "@" in email:
        prefix = email.split("@")[0].strip()
        cleaned = prefix.replace(".", " ").replace("_", " ").replace("-", " ")
        words = [w.capitalize() for w in cleaned.split() if w and not w.isdigit()]
        if words:
            return " ".join(words)
        return prefix.capitalize()

    return "Student"

