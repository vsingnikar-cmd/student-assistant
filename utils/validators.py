"""Input validation utilities for user forms, dates, file uploads, and academic parameters."""

import re
from datetime import date, datetime
from typing import List, Optional, Tuple
from utils.errors import ValidationError

# Regex patterns
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


def validate_email(email: str) -> str:
    """Validates email format and returns stripped lowercase email."""
    if not email or not isinstance(email, str):
        raise ValidationError("Email address is required.")
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValidationError("Please provide a valid email address.")
    return cleaned


def validate_username(username: str) -> str:
    """Validates username length and permitted characters (3-30 letters, numbers, underscores)."""
    if not username or not isinstance(username, str):
        raise ValidationError("Username is required.")
    cleaned = username.strip()
    if not USERNAME_REGEX.match(cleaned):
        raise ValidationError(
            "Username must be 3 to 30 characters long and contain only letters, numbers, and underscores."
        )
    return cleaned


def validate_password(password: str) -> str:
    """Validates password length and basic strength."""
    if not password or not isinstance(password, str):
        raise ValidationError("Password is required.")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    return password


def validate_registration_form(
    username: str,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    course: str,
    branch: str,
    semester: str,
    college: Optional[str] = None,
) -> dict:
    """Validates the entire new student registration payload."""
    clean_username = validate_username(username)
    clean_email = validate_email(email)
    validate_password(password)

    if password != confirm_password:
        raise ValidationError("Password and confirmation password do not match.")

    if not full_name or not full_name.strip():
        raise ValidationError("Full name is required.")
    if not course or not course.strip():
        raise ValidationError("Course (e.g. B.Tech, B.Sc) is required.")
    if not branch or not branch.strip():
        raise ValidationError("Branch / Department is required.")
    if not semester or not str(semester).strip():
        raise ValidationError("Current semester is required.")

    return {
        "username": clean_username,
        "full_name": full_name.strip(),
        "email": clean_email,
        "password": password,
        "course": course.strip(),
        "branch": branch.strip(),
        "semester": str(semester).strip(),
        "college": college.strip() if college else "",
    }


def validate_exam_notes_input(subject: str, topic: str, marks: int) -> Tuple[str, str, int]:
    """Validates parameters for exam notes generation."""
    if not subject or not subject.strip():
        raise ValidationError("Subject cannot be empty.")
    if not topic or not topic.strip():
        raise ValidationError("Topic cannot be empty.")
    try:
        int_marks = int(marks)
    except (ValueError, TypeError):
        raise ValidationError("Marks must be an integer (2, 5, or 10).")

    if int_marks not in (2, 5, 10):
        raise ValidationError("Supported mark categories are 2, 5, or 10 marks.")

    return subject.strip(), topic.strip(), int_marks


def validate_quiz_input(
    subject: str, topic: str, num_questions: int, difficulty: str
) -> Tuple[str, str, int, str]:
    """Validates quiz generator parameters."""
    if not subject or not subject.strip():
        raise ValidationError("Subject cannot be empty.")
    if not topic or not topic.strip():
        raise ValidationError("Topic cannot be empty.")

    try:
        count = int(num_questions)
    except (ValueError, TypeError):
        raise ValidationError("Question count must be an integer.")

    if count < 3 or count > 15:
        raise ValidationError("Question count must be between 3 and 15.")

    diff = difficulty.strip().title()
    if diff not in ("Easy", "Medium", "Hard"):
        raise ValidationError("Difficulty must be Easy, Medium, or Hard.")

    return subject.strip(), topic.strip(), count, diff


def validate_study_planner_input(
    subjects: List[str], exam_date_val: date, daily_hours: float
) -> Tuple[List[str], date, float]:
    """Validates study planner constraints: date in future, reasonable hours."""
    cleaned_subjects = [s.strip() for s in subjects if s and s.strip()]
    if not cleaned_subjects:
        raise ValidationError("Please provide at least one subject.")

    today = date.today()
    if isinstance(exam_date_val, datetime):
        exam_date_val = exam_date_val.date()

    if exam_date_val < today:
        raise ValidationError("Examination date cannot be in the past.")

    try:
        hours = float(daily_hours)
    except (ValueError, TypeError):
        raise ValidationError("Daily hours must be a valid number.")

    if hours <= 0.0 or hours > 18.0:
        raise ValidationError("Daily study hours must be between 0.5 and 18 hours.")

    return cleaned_subjects, exam_date_val, hours


def validate_pdf_upload(file_bytes: bytes, filename: str, max_size_mb: int = 15) -> None:
    """Validates file extension and size for PDF documents."""
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are supported.")
    
    if not file_bytes or len(file_bytes) == 0:
        raise ValidationError("The uploaded PDF file is empty.")

    max_bytes = max_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValidationError(
            f"File size exceeds the maximum limit of {max_size_mb} MB (Current: {len(file_bytes)/(1024*1024):.2f} MB)."
        )
