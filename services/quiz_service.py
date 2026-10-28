"""Quiz generation, deterministic scoring, and attempt tracking service."""

import logging
from typing import Dict, Any, List, Optional
from utils.errors import ValidationError
from models.quiz_models import (
    QuizGenerationResponse,
    QuizSubmission,
    QuizEvaluationResult,
    QuizQuestionResult,
)
from services.gemini_service import gemini_service
from services.database_service import db_service

logger = logging.getLogger(__name__)


class QuizService:
    """Handles multiple-choice quiz creation, deterministic score calculation, and results."""

    def create_quiz(
        self, subject: str, topic: str, num_questions: int, difficulty: str = "Medium"
    ) -> QuizGenerationResponse:
        """Requests AI quiz generation and validates output against strict Pydantic schemas."""
        return gemini_service.generate_quiz(
            subject=subject,
            topic=topic,
            num_questions=num_questions,
            difficulty=difficulty,
        )

    def evaluate_quiz(
        self,
        quiz: QuizGenerationResponse,
        user_responses: Dict[int, Optional[int]],
        user_id: Optional[str] = None,
        persist: bool = True,
    ) -> QuizEvaluationResult:
        """Deterministically calculates quiz score in application logic and saves to Supabase.
        
        Args:
            quiz: The verified QuizGenerationResponse.
            user_responses: Dict mapping question index (0-based) to selected option index (0..3 or None).
            user_id: Authenticated user ID.
            persist: Whether to save to the database.
        """
        questions = quiz.questions
        total_questions = len(questions)
        if total_questions == 0:
            raise ValidationError("Cannot evaluate an empty quiz.")

        score = 0
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        question_details: List[QuizQuestionResult] = []

        for idx, q in enumerate(questions):
            selected = user_responses.get(idx)
            is_unanswered = selected is None
            is_correct = False

            if is_unanswered:
                unanswered_count += 1
            elif selected == q.correct_index:
                is_correct = True
                correct_count += 1
                score += 1
            else:
                incorrect_count += 1

            question_details.append(
                QuizQuestionResult(
                    question=q.question,
                    options=q.options,
                    user_answer_index=selected,
                    correct_answer_index=q.correct_index,
                    is_correct=is_correct,
                    is_unanswered=is_unanswered,
                    explanation=q.explanation,
                )
            )

        percentage = round((score / total_questions) * 100.0, 2)

        result = QuizEvaluationResult(
            subject=quiz.subject,
            topic=quiz.topic,
            difficulty=quiz.difficulty,
            score=score,
            total=total_questions,
            percentage=percentage,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unanswered_count=unanswered_count,
            questions_detail=question_details,
        )

        # Persist to database if authenticated and requested
        if persist and user_id:
            try:
                db_service.save_quiz_attempt(
                    user_id=user_id,
                    subject=quiz.subject,
                    topic=quiz.topic,
                    difficulty=quiz.difficulty,
                    score=score,
                    total=total_questions,
                    percentage=percentage,
                    answers=[q.model_dump() for q in question_details],
                )
            except Exception as e:
                logger.error(f"Failed to record quiz attempt in database: {e}")

        return result


quiz_service = QuizService()
