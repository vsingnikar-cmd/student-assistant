"""Tests for input validation routines."""

import pytest
from datetime import date, timedelta
from utils.errors import ValidationError
from utils.validators import (
    validate_email,
    validate_username,
    validate_password,
    validate_registration_form,
    validate_exam_notes_input,
    validate_quiz_input,
    validate_study_planner_input,
    validate_pdf_upload,
)


def test_validate_email_valid():
    assert validate_email("student@university.edu") == "student@university.edu"
    assert validate_email("  STUDENT@DOMAIN.COM  ") == "student@domain.com"


def test_validate_email_invalid():
    with pytest.raises(ValidationError):
        validate_email("invalid-email")
    with pytest.raises(ValidationError):
        validate_email("")
    with pytest.raises(ValidationError):
        validate_email("user@")


def test_validate_username_valid():
    assert validate_username("alex_2026") == "alex_2026"
    assert validate_username("john_doe") == "john_doe"


def test_validate_username_invalid():
    # Too short (< 3 chars)
    with pytest.raises(ValidationError):
        validate_username("ab")
    # Invalid characters (spaces, special symbols)
    with pytest.raises(ValidationError):
        validate_username("alex doe")
    with pytest.raises(ValidationError):
        validate_username("user@123")


def test_validate_password():
    assert validate_password("StrongPass123!") == "StrongPass123!"
    with pytest.raises(ValidationError):
        validate_password("short")


def test_validate_registration_form():
    data = validate_registration_form(
        username="john_doe",
        full_name="John Doe",
        email="john@college.edu",
        password="securePassword123",
        confirm_password="securePassword123",
        course="B.Tech",
        branch="Computer Science",
        semester="5",
        college="MIT",
    )
    assert data["username"] == "john_doe"
    assert data["email"] == "john@college.edu"

    # Password mismatch
    with pytest.raises(ValidationError):
        validate_registration_form(
            username="john_doe",
            full_name="John Doe",
            email="john@college.edu",
            password="pass1",
            confirm_password="pass2",
            course="B.Tech",
            branch="CS",
            semester="5",
        )


def test_validate_exam_notes_input():
    sub, top, marks = validate_exam_notes_input("Operating Systems", "Deadlock Prevention", 5)
    assert sub == "Operating Systems"
    assert marks == 5

    # Invalid marks (only 2, 5, 10 supported)
    with pytest.raises(ValidationError):
        validate_exam_notes_input("Math", "Calculus", 7)


def test_validate_quiz_input():
    sub, top, count, diff = validate_quiz_input("Physics", "Thermodynamics", 5, "Medium")
    assert count == 5
    assert diff == "Medium"

    # Out of bounds questions count (< 3 or > 15)
    with pytest.raises(ValidationError):
        validate_quiz_input("Physics", "Thermodynamics", 2, "Medium")
    with pytest.raises(ValidationError):
        validate_quiz_input("Physics", "Thermodynamics", 20, "Medium")


def test_validate_study_planner_input():
    future_date = date.today() + timedelta(days=30)
    subs, d, hours = validate_study_planner_input(["Calculus", "Algorithms"], future_date, 4.5)
    assert len(subs) == 2
    assert hours == 4.5

    # Past date
    past_date = date.today() - timedelta(days=1)
    with pytest.raises(ValidationError):
        validate_study_planner_input(["Calculus"], past_date, 3)

    # Invalid hours
    with pytest.raises(ValidationError):
        validate_study_planner_input(["Calculus"], future_date, 0)
    with pytest.raises(ValidationError):
        validate_study_planner_input(["Calculus"], future_date, 24)


def test_validate_pdf_upload():
    # Valid
    validate_pdf_upload(b"%PDF-1.4 mock content", "lecture.pdf", max_size_mb=10)

    # Non-pdf
    with pytest.raises(ValidationError):
        validate_pdf_upload(b"some content", "notes.docx", max_size_mb=10)

    # Empty
    with pytest.raises(ValidationError):
        validate_pdf_upload(b"", "empty.pdf", max_size_mb=10)


def test_resolve_student_name():
    from models.schemas import resolve_student_name

    # 1. Real full_name provided in profile
    assert resolve_student_name({"full_name": "Vaibhav Sharma"}) == "Vaibhav Sharma"

    # 2. Generic "Student" placeholder in profile, fallback to user_metadata
    assert resolve_student_name({"full_name": "Student", "user_metadata": {"full_name": "Rachel Greene"}}) == "Rachel Greene"

    # 3. Generic "Student" placeholder, fallback to username
    assert resolve_student_name({"full_name": "Student", "username": "vaibhav_sharma"}) == "Vaibhav Sharma"
    assert resolve_student_name({"full_name": "Student", "username": "john.doe"}) == "John Doe"

    # 4. Fallback to email prefix
    assert resolve_student_name({"full_name": "Student"}, email="alex.mercer@university.edu") == "Alex Mercer"
    assert resolve_student_name(None, email="vaibhav@gmail.com") == "Vaibhav"

    # 5. Complete empty fallback
    assert resolve_student_name(None, email="", username="") == "Student"

