"""Tests for quiz models, validation, and deterministic evaluation logic."""

import pytest
from pydantic import ValidationError as PydanticValidationError
from models.quiz_models import (
    QuizQuestion,
    QuizGenerationResponse,
)
from services.quiz_service import quiz_service


def test_quiz_question_validation_success():
    q = QuizQuestion(
        question="What is the time complexity of binary search on a sorted array?",
        options=["O(1)", "O(n)", "O(log n)", "O(n log n)"],
        correct_index=2,
        explanation="Binary search halves the search space each step, yielding logarithmic time.",
    )
    assert q.correct_index == 2
    assert len(q.options) == 4


def test_quiz_question_duplicate_options_rejected():
    with pytest.raises(PydanticValidationError):
        QuizQuestion(
            question="What is 2+2?",
            options=["4", "4", "5", "6"],  # Duplicate '4'
            correct_index=0,
            explanation="2+2=4",
        )


def test_quiz_question_invalid_option_count():
    with pytest.raises(PydanticValidationError):
        QuizQuestion(
            question="What is 2+2?",
            options=["1", "2", "3"],  # Only 3 options
            correct_index=1,
            explanation="2+2=4",
        )


def test_quiz_question_invalid_correct_index():
    with pytest.raises(PydanticValidationError):
        QuizQuestion(
            question="What is 2+2?",
            options=["1", "2", "3", "4"],
            correct_index=5,  # Out of range 0..3
            explanation="2+2=4",
        )


def test_deterministic_quiz_evaluation():
    # Construct a 3-question quiz
    quiz = QuizGenerationResponse(
        subject="Computer Science",
        topic="Data Structures",
        difficulty="Medium",
        questions=[
            QuizQuestion(
                question="Q1",
                options=["A", "B", "C", "D"],
                correct_index=1,  # Correct: B
                explanation="Exp 1",
            ),
            QuizQuestion(
                question="Q2",
                options=["A", "B", "C", "D"],
                correct_index=3,  # Correct: D
                explanation="Exp 2",
            ),
            QuizQuestion(
                question="Q3",
                options=["A", "B", "C", "D"],
                correct_index=0,  # Correct: A
                explanation="Exp 3",
            ),
        ],
    )

    # User answers: Q0 -> B (correct, index 1), Q1 -> A (incorrect, index 0), Q2 -> None (unanswered)
    user_responses = {
        0: 1,
        1: 0,
        2: None,
    }

    result = quiz_service.evaluate_quiz(quiz, user_responses, user_id=None, persist=False)

    assert result.total == 3
    assert result.score == 1
    assert result.correct_count == 1
    assert result.incorrect_count == 1
    assert result.unanswered_count == 1
    assert result.percentage == round((1 / 3) * 100.0, 2)
    assert result.questions_detail[0].is_correct is True
    assert result.questions_detail[1].is_correct is False
    assert result.questions_detail[2].is_unanswered is True
