"""Study plan generation and schedule management service."""

import logging
from datetime import date
from typing import List, Dict, Any, Optional
from utils.validators import validate_study_planner_input
from utils.errors import ValidationError
from services.gemini_service import gemini_service
from services.database_service import db_service

logger = logging.getLogger(__name__)


class StudyPlanService:
    """Manages creation, validation, and storage of student study plans."""

    def generate_plan(
        self,
        subjects: List[str],
        exam_date: date,
        daily_hours: float,
        topics: str = "",
    ) -> Dict[str, Any]:
        """Validates parameters and generates an academic study plan."""
        clean_subjects, clean_exam_date, clean_hours = validate_study_planner_input(
            subjects=subjects,
            exam_date_val=exam_date,
            daily_hours=daily_hours,
        )

        today = date.today()
        days_remaining = (clean_exam_date - today).days

        if days_remaining <= 0:
            raise ValidationError("Target exam date must be at least 1 day in the future.")

        exam_date_str = clean_exam_date.strftime("%B %d, %Y")
        
        plan_text = gemini_service.generate_study_plan(
            subjects=clean_subjects,
            exam_date_str=exam_date_str,
            days_remaining=days_remaining,
            daily_hours=clean_hours,
            topics=topics,
        )

        title = f"{', '.join(clean_subjects[:2])} Exam Prep ({clean_exam_date.strftime('%b %Y')})"

        return {
            "title": title,
            "exam_date": str(clean_exam_date),
            "days_remaining": days_remaining,
            "daily_hours": clean_hours,
            "subjects": clean_subjects,
            "plan_text": plan_text,
        }

    def save_plan(
        self,
        user_id: str,
        title: str,
        exam_date: str,
        daily_hours: float,
        subjects: List[str],
        plan_text: str,
    ) -> Dict[str, Any]:
        """Persists the generated plan to the database."""
        return db_service.save_study_plan(
            user_id=user_id,
            title=title,
            exam_date=exam_date,
            daily_hours=daily_hours,
            subjects=subjects,
            plan_text=plan_text,
        )


study_plan_service = StudyPlanService()
