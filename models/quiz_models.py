"""Pydantic data models for MCQ quiz generation, submission, and deterministic evaluation."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class QuizQuestion(BaseModel):
    """Schema for an individual multiple-choice question."""
    question: str = Field(..., description="The clear question text")
    options: List[str] = Field(..., min_length=4, max_length=4, description="Exactly 4 distinct choices")
    correct_index: int = Field(..., ge=0, le=3, description="0-based index of correct option (0, 1, 2, or 3)")
    explanation: str = Field(..., description="Detailed explanation of why the correct option is right")
    topic: Optional[str] = None
    difficulty: Optional[str] = None

    @field_validator("options")
    @classmethod
    def validate_options(cls, options: List[str]) -> List[str]:
        cleaned = [opt.strip() for opt in options if opt and opt.strip()]
        if len(cleaned) != 4:
            raise ValueError("A quiz question must have exactly 4 non-empty options.")
        # Check for duplicate options
        lower_opts = [opt.lower() for opt in cleaned]
        if len(set(lower_opts)) != 4:
            raise ValueError("All 4 options must be distinct from one another.")
        return cleaned

    @field_validator("question")
    @classmethod
    def validate_question(cls, q: str) -> str:
        if not q or not q.strip():
            raise ValueError("Question text cannot be blank.")
        return q.strip()

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, exp: str) -> str:
        if not exp or not exp.strip():
            raise ValueError("Explanation cannot be blank.")
        return exp.strip()


class QuizGenerationResponse(BaseModel):
    """Container schema for the entire generated quiz."""
    subject: str
    topic: str
    difficulty: str
    questions: List[QuizQuestion] = Field(..., min_length=1)


class UserAnswer(BaseModel):
    """User response for a single question."""
    question_index: int
    selected_option_index: Optional[int] = None  # None indicates unanswered


class QuizSubmission(BaseModel):
    """Collection of user responses submitted for scoring."""
    answers: List[UserAnswer]


class QuizQuestionResult(BaseModel):
    """Evaluation result for an individual question."""
    question: str
    options: List[str]
    user_answer_index: Optional[int]
    correct_answer_index: int
    is_correct: bool
    is_unanswered: bool
    explanation: str


class QuizEvaluationResult(BaseModel):
    """Final calculated quiz result."""
    subject: str
    topic: str
    difficulty: str
    score: int
    total: int
    percentage: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    questions_detail: List[QuizQuestionResult]
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
