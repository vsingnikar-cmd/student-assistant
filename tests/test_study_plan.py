"""Tests for study planning logic, date bounds, and hourly capacity."""

from datetime import date, timedelta
import pytest
from utils.errors import ValidationError
from utils.validators import validate_study_planner_input


def test_study_plan_date_bounds():
    today = date.today()
    future_date = today + timedelta(days=14)

    subjects, d, hours = validate_study_planner_input(
        subjects=["Operating Systems", "Computer Networks"],
        exam_date_val=future_date,
        daily_hours=3.5,
    )
    assert d == future_date
    assert hours == 3.5
    assert len(subjects) == 2


def test_study_plan_past_date_fails():
    past = date.today() - timedelta(days=2)
    with pytest.raises(ValidationError) as excinfo:
        validate_study_planner_input(
            subjects=["Database Systems"],
            exam_date_val=past,
            daily_hours=2.0,
        )
    assert "cannot be in the past" in str(excinfo.value)
