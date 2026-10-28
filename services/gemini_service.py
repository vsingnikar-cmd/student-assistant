"""Google Gemini AI service utilizing the official google-genai SDK with automatic model resilience."""

import json
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from utils.config import config
from utils.errors import AIProviderError
from models.quiz_models import QuizGenerationResponse, QuizQuestion

logger = logging.getLogger(__name__)


class GeminiService:
    """Manages all interactions with Google Gemini models."""

    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._model = config.GEMINI_MODEL

    def _get_client(self) -> genai.Client:
        """Returns initialized Gemini client or raises an informative error."""
        if not config.is_gemini_configured():
            raise AIProviderError(
                "Gemini API key is not configured. Please add GEMINI_API_KEY to your .env file."
            )
        if self._client is None:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client

    def _call_model(self, contents: Any, config_obj: types.GenerateContentConfig):
        """Calls Gemini with automatic fallback across resilient model endpoints if temporary 503/404 occurs."""
        client = self._get_client()
        candidate_models = [self._model, "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]
        seen = set()
        models_to_try = []
        for m in candidate_models:
            if m and m not in seen:
                seen.add(m)
                models_to_try.append(m)

        last_exc = None
        for model_name in models_to_try:
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config_obj,
                )
            except Exception as e:
                err_str = str(e).lower()
                if "503" in err_str or "404" in err_str or "unavailable" in err_str or "not found" in err_str:
                    logger.warning(f"Model {model_name} unavailable ({e}), trying fallback...")
                    last_exc = e
                    continue
                raise e
        raise last_exc

    # =========================================================================
    # 1. ACADEMIC CHATBOT
    # =========================================================================

    def generate_chat_response(
        self,
        question: str,
        history: List[Dict[str, str]],
        student_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generates an academic, educational response using bounded context."""
        student_context = ""
        if student_profile:
            course = student_profile.get("course", "")
            branch = student_profile.get("branch", "")
            semester = student_profile.get("semester", "")
            if course or branch:
                student_context = f"\nThe student is enrolled in {course} ({branch}), Semester {semester}."

        system_instruction = (
            "You are an expert AI Student Assistant and Academic Tutor."
            f"{student_context}\n"
            "Your role is to help students deeply understand academic, scientific, and engineering concepts.\n"
            "Guidelines:\n"
            "- Provide clear definitions, intuitive explanations, real-world examples, and step-by-step derivations where applicable.\n"
            "- Use LaTeX formatting for mathematical expressions ($...$ for inline, $$...$$ for block formulas).\n"
            "- Break complex topics into structured sections with markdown headings and bullet points.\n"
            "- If a question is ambiguous, clarify key nuances.\n"
            "- Do not fabricate citations or claim to know proprietary exam questions.\n"
            "- Maintain an encouraging, scholarly, and supportive tone."
        )

        contents = []
        for msg in history[-config.MAX_CHAT_CONTEXT_MESSAGES :]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.get("content", ""))],
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=question)],
            )
        )

        try:
            response = self._call_model(
                contents=contents,
                config_obj=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
                    max_output_tokens=2048,
                ),
            )
            return response.text or "I apologize, but I could not generate a response at this time."
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            raise AIProviderError("Failed to communicate with AI model.", technical_details=str(e))

    # =========================================================================
    # 2. EXAM NOTES GENERATOR
    # =========================================================================

    def generate_exam_notes(
        self,
        subject: str,
        topic: str,
        marks: int,
        difficulty: str = "Intermediate",
        additional_context: Optional[str] = None,
    ) -> str:
        """Generates exam-oriented notes tailored to 2-mark, 5-mark, or 10-mark formats."""
        if marks == 2:
            format_rules = (
                "FORMAT: 2-MARK EXAM ANSWER\n"
                "- Crisp 1-2 sentence formal definition or core statement.\n"
                "- Exactly 2 essential bullet points (key properties, formula, or significance).\n"
                "- Keep concise, precise, and high-yield (target: 40-70 words)."
            )
        elif marks == 5:
            format_rules = (
                "FORMAT: 5-MARK EXAM ANSWER\n"
                "- **Introduction / Definition**: Clear, formal conceptual overview.\n"
                "- **Key Principles / Important Points**: 4-5 numbered or bulleted core points.\n"
                "- **Working / Brief Explanation**: Concise conceptual breakdown or formula.\n"
                "- **Illustrative Example**: One relevant real-world or technical example.\n"
                "- Target: 150-250 words."
            )
        else:  # 10 marks
            format_rules = (
                "FORMAT: 10-MARK COMPREHENSIVE EXAM ANSWER\n"
                "- **Title & Abstract / Definition**: Comprehensive academic definition.\n"
                "- **Core Architecture / Working Principles**: Detailed explanation with subheadings and numbered steps.\n"
                "- **Key Components / Theoretical Formulations**: Equations or structural breakdown.\n"
                "- **Practical Example / Case Study**: Concrete real-world or computational example.\n"
                "- **Advantages & Limitations**: Balanced comparison.\n"
                "- **Applications in Industry / Academia**: 3-4 notable applications.\n"
                "- **Conclusion**: Summary summarizing key takeaways.\n"
                "- Target: 400-600 words."
            )

        prompt = (
            f"Generate high-scoring, structured exam notes for the following topic:\n"
            f"**Subject**: {subject}\n"
            f"**Topic**: {topic}\n"
            f"**Exam Question Weight**: {marks} Marks\n"
            f"**Academic Level**: {difficulty}\n"
        )
        if additional_context:
            prompt += f"**Specific Focus / Reference Context**: {additional_context}\n"

        prompt += (
            f"\nStrictly follow this structure:\n{format_rules}\n\n"
            "Note: Format using clean markdown with bold labels and LaTeX for any formulas. "
            "Do not fabricate proprietary university marking schemes."
        )

        try:
            response = self._call_model(
                contents=prompt,
                config_obj=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=3000,
                ),
            )
            disclaimer = (
                "\n\n---\n*Disclaimer: These notes are structured according to academic and examination conventions. "
                "Always cross-check specific grading schemes and syllabus guidelines of your institution.*"
            )
            return (response.text or "") + disclaimer
        except Exception as e:
            logger.error(f"Gemini exam notes error: {e}")
            raise AIProviderError("Failed to generate exam notes.", technical_details=str(e))

    # =========================================================================
    # 3. QUIZ GENERATOR
    # =========================================================================

    def generate_quiz(
        self, subject: str, topic: str, num_questions: int, difficulty: str = "Medium"
    ) -> QuizGenerationResponse:
        """Generates structured multiple choice questions with deterministic validation."""
        prompt = (
            f"Create a multiple-choice quiz on the topic '{topic}' in the subject '{subject}'.\n"
            f"Difficulty: {difficulty}\n"
            f"Number of questions: {num_questions}\n\n"
            "Requirements:\n"
            "1. Each question must have exactly 4 distinct, unambiguous answer options.\n"
            "2. 'correct_index' must be an integer between 0 and 3 indicating the 0-based index of the correct option.\n"
            "3. Provide a clear, thorough explanation for why the correct option is right.\n"
            "4. Return ONLY a valid JSON object matching the requested schema.\n"
            "5. Distribute correct answers across options 0, 1, 2, 3 (do NOT place all answers at option 0)."
        )

        last_error = None
        for attempt in range(2):
            try:
                response = self._call_model(
                    contents=prompt,
                    config_obj=types.GenerateContentConfig(
                        temperature=0.4,
                        response_mime_type="application/json",
                        response_schema=QuizGenerationResponse,
                    ),
                )
                
                raw_text = response.text.strip()
                parsed_json = json.loads(raw_text)
                
                quiz_data = QuizGenerationResponse(**parsed_json)
                return quiz_data
            except Exception as e:
                logger.warning(f"Quiz generation attempt {attempt + 1} failed: {e}")
                last_error = e

        raise AIProviderError(
            f"Failed to generate a valid quiz after retries. Technical details: {last_error}"
        )

    # =========================================================================
    # 4. GROUNDED PDF QUESTION ANSWERING
    # =========================================================================

    def answer_from_pdf_context(
        self, question: str, retrieved_chunks: List[Dict[str, Any]], filename: str
    ) -> str:
        """Generates a strictly document-grounded answer with verifiable page citations."""
        if not retrieved_chunks:
            return (
                f"I could not find any relevant information regarding '{question}' in the document **{filename}**.\n\n"
                "Please verify that the document contains text related to this topic or try rephrasing your question."
            )

        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            p_start = chunk.get("page_start", 1)
            p_end = chunk.get("page_end", p_start)
            page_label = f"Page {p_start}" if p_start == p_end else f"Pages {p_start}-{p_end}"
            context_blocks.append(
                f"--- EXCERPT {i} [{page_label}] ---\n{chunk.get('chunk_text', '').strip()}"
            )

        combined_context = "\n\n".join(context_blocks)

        prompt = (
            f"You are a document assistant analyzing the academic document: '{filename}'.\n\n"
            f"Document Excerpts:\n{combined_context}\n\n"
            f"Student Question: {question}\n\n"
            "Strict Instructions:\n"
            "1. Answer the question using ONLY the provided excerpts above.\n"
            "2. Whenever citing information, include the specific page reference (e.g., '[Page 3]' or '[Pages 4-5]') from the excerpt header.\n"
            "3. If the provided excerpts do not contain enough evidence or facts to answer the question, state: "
            "'The uploaded document does not contain sufficient information to answer this question.' Do not fabricate external facts.\n"
            "4. Do not invent page numbers that are not present in the excerpt headers."
        )

        try:
            response = self._call_model(
                contents=prompt,
                config_obj=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1500,
                ),
            )
            return response.text or "No answer could be formulated from the document."
        except Exception as e:
            logger.error(f"Gemini PDF QA error: {e}")
            raise AIProviderError("Failed to query document content.", technical_details=str(e))

    # =========================================================================
    # 5. STUDY PLANNER
    # =========================================================================

    def generate_study_plan(
        self,
        subjects: List[str],
        exam_date_str: str,
        days_remaining: int,
        daily_hours: float,
        topics: str = "",
    ) -> str:
        """Generates a day-by-day structured study schedule."""
        total_study_capacity = days_remaining * daily_hours

        prompt = (
            f"Create a realistic, disciplined study plan for a college student.\n"
            f"- Subjects: {', '.join(subjects)}\n"
            f"- Examination Target Date: {exam_date_str} ({days_remaining} days remaining)\n"
            f"- Available Study Time: {daily_hours} hours/day (Total Capacity: ~{total_study_capacity:.1f} hours)\n"
        )
        if topics:
            prompt += f"- Key Topics / Priority Focus Areas: {topics}\n"

        prompt += (
            "\nRequirements for the plan:\n"
            "1. Allocate time proportionally across the subjects.\n"
            "2. Structure into distinct phases: Core Learning & Concepts, Problem Solving & Application, and Final Revision & Mock Tests.\n"
            "3. Provide a clear Day-by-Day schedule (or grouped milestones if period > 14 days) detailing exact hourly allocations.\n"
            "4. Include active recall techniques, formula revision, and dedicated rest/buffer slots.\n"
            "5. If available time is tight compared to the syllabus, clearly warn the student and prioritize high-yield topics.\n"
            "6. Conclude with exam strategy and time-management tips on test day."
        )

        try:
            response = self._call_model(
                contents=prompt,
                config_obj=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=3000,
                ),
            )
            disclaimer = (
                "\n\n---\n*Note: This study schedule is an AI-generated guidance tool designed to assist your planning. "
                "Consistency, practice, and personal pace are key to academic success.*"
            )
            return (response.text or "") + disclaimer
        except Exception as e:
            logger.error(f"Gemini study plan error: {e}")
            raise AIProviderError("Failed to generate study plan.", technical_details=str(e))


gemini_service = GeminiService()
