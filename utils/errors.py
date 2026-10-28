"""Custom exception classes and user-facing error formatting utilities.

Ensures sensitive details (API keys, DB secrets, internal stack traces) are
never exposed to end users, while producing actionable and clear feedback.
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ai_student_assistant")


class AppError(Exception):
    """Base application exception with an actionable message."""
    def __init__(self, message: str, technical_details: str = ""):
        super().__init__(message)
        self.message = message
        self.technical_details = technical_details
        if technical_details:
            logger.error(f"{message} | Tech: {technical_details}")


class AuthenticationError(AppError):
    """Authentication or authorization failures."""
    pass


class ValidationError(AppError):
    """Input validation errors."""
    pass


class AIProviderError(AppError):
    """Gemini API or LLM processing errors."""
    pass


class PDFProcessingError(AppError):
    """PDF parsing, extraction, or size errors."""
    pass


class DatabaseError(AppError):
    """Supabase or database operation errors."""
    pass


class NotFoundError(AppError):
    """Resource not found errors."""
    pass


def sanitize_error_message(err: Exception) -> str:
    """Translates arbitrary exceptions into safe, user-friendly messages.
    
    Prevents leaking credentials, raw JSON payloads, or stack traces.
    """
    if isinstance(err, AppError):
        return err.message
    
    err_str = str(err).lower()
    
    # Common network / API errors
    if "api_key" in err_str or "apikey" in err_str or "credential" in err_str:
        return "Authentication error with AI provider. Please verify API configuration."
    if "rate limit" in err_str or "429" in err_str or "quota" in err_str:
        return "The AI service is currently busy or rate limit reached. Please wait a moment and retry."
    if "timeout" in err_str or "timed out" in err_str:
        return "The request timed out. Please check your network connection and try again."
    if "connection" in err_str or "network" in err_str:
        return "Network connection issue. Please check your internet connection."
    if "duplicate key" in err_str or "already exists" in err_str:
        return "A record with this information already exists."
    
    # Generic safe fallback
    return "An unexpected error occurred. Please try again or contact support if the issue persists."
