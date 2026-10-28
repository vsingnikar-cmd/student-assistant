"""Database service for Supabase PostgreSQL data persistence with strict user isolation and local SQLite fallback."""

import logging
from typing import Dict, Any, List, Optional
from utils.config import config
from utils.errors import DatabaseError
from services.auth_service import auth_service
from services.local_db import LocalDataStore
from models.schemas import StudentProfile, resolve_student_name

logger = logging.getLogger(__name__)


class DatabaseService:
    """Provides methods for reading and persisting student data via Supabase or local SQLite."""

    def _get_client(self):
        """Returns the authenticated Supabase client."""
        return auth_service.client

    # =========================================================================
    # 1. PROFILE MANAGEMENT
    # =========================================================================

    def get_profile(self, user_id: str) -> Optional[StudentProfile]:
        """Retrieves a student profile by user UUID."""
        if not config.is_supabase_configured():
            data = LocalDataStore.get_profile(user_id)
            return StudentProfile(**data) if data else None

        try:
            client = self._get_client()
            res = client.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
            if res and res.data:
                return StudentProfile(**res.data)
            return None
        except Exception as e:
            logger.error(f"Error fetching profile for {user_id}: {e}")
            raise DatabaseError("Unable to retrieve student profile.", technical_details=str(e))

    def ensure_profile(self, user: Any) -> StudentProfile:
        """Retrieves profile, or auto-populates it from user metadata and creates row in profiles table."""
        user_id = user.id if hasattr(user, "id") else user.get("id")
        user_email = user.email if hasattr(user, "email") else user.get("email", "")
        meta = user.user_metadata if hasattr(user, "user_metadata") else (user.get("user_metadata") or {})
        if not isinstance(meta, dict):
            meta = {}

        existing = None
        try:
            existing = self.get_profile(user_id)
        except Exception:
            pass

        existing_has_real_name = (
            existing
            and existing.full_name
            and existing.full_name.strip()
            and existing.full_name.strip().lower() not in ("student", "user", "none", "null", "")
        )

        # Resolve student full_name with priority: real existing name -> user_metadata -> username -> email
        full_name = resolve_student_name(
            profile={
                "full_name": existing.full_name if existing_has_real_name else (meta.get("full_name") or meta.get("name")),
                "username": meta.get("username") or (existing.username if existing else None),
            },
            email=user_email,
            username=meta.get("username") or (existing.username if existing else ""),
        )

        username = meta.get("username") or (existing.username if existing and existing.username else user_email.split("@")[0])
        course = meta.get("course") or (existing.course if existing and existing.course else "B.Tech")
        branch = meta.get("branch") or (existing.branch if existing and existing.branch else "Computer Science")
        semester = str(meta.get("semester") or (existing.semester if existing and existing.semester else "1"))
        college = (
            meta.get("college")
            or meta.get("university")
            or meta.get("college_name")
            or meta.get("institution")
            or (existing.college if existing and existing.college else "")
        )
        subjects = meta.get("subjects") or (existing.subjects if existing and existing.subjects else [])

        # If existing record already has both a real name and college, return it immediately
        if existing and existing_has_real_name and existing.college:
            return existing

        profile_payload = {
            "id": user_id,
            "email": user_email,
            "username": username,
            "full_name": full_name,
            "course": course,
            "branch": branch,
            "college": college,
            "semester": semester,
            "subjects": subjects,
            "profile_completed": True,
        }

        if not config.is_supabase_configured():
            LocalDataStore.update_profile(user_id, profile_payload)
            data = LocalDataStore.get_profile(user_id)
            return StudentProfile(**data)

        try:
            client = self._get_client()
            if existing:
                update_fields = {
                    "full_name": full_name,
                    "course": course,
                    "branch": branch,
                    "college": college,
                    "semester": semester,
                    "subjects": subjects,
                    "profile_completed": True,
                }
                client.table("profiles").update(update_fields).eq("id", user_id).execute()
            else:
                try:
                    client.table("profiles").insert(profile_payload).execute()
                except Exception as insert_err:
                    # If insert fails (e.g. row already exists or unique username), try update
                    update_fields = {
                        "full_name": full_name,
                        "course": course,
                        "branch": branch,
                        "college": college,
                        "semester": semester,
                        "subjects": subjects,
                        "profile_completed": True,
                    }
                    try:
                        client.table("profiles").update(update_fields).eq("id", user_id).execute()
                    except Exception:
                        pass

            refetched = self.get_profile(user_id)
            if refetched:
                return refetched
        except Exception as e:
            logger.warning(f"Failed to persist profile record: {e}")

        return StudentProfile(**profile_payload)

    def update_profile(self, user_id: str, updates: Dict[str, Any]) -> StudentProfile:
        """Updates student academic profile fields in database and session."""
        if not config.is_supabase_configured():
            data = LocalDataStore.update_profile(user_id, updates)
            return StudentProfile(**data)

        try:
            client = self._get_client()
            allowed_fields = {
                "full_name",
                "course",
                "branch",
                "college",
                "semester",
                "subjects",
                "profile_completed",
            }
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

            # 1. Update public.profiles row directly via PATCH
            try:
                client.table("profiles").update(filtered_updates).eq("id", user_id).execute()
            except Exception as update_err:
                logger.warning(f"Profiles table update error for {user_id}: {update_err}")

            # 2. Also update Supabase Auth user metadata so it persists across logins
            try:
                client.auth.update_user({"data": filtered_updates})
            except Exception as auth_err:
                logger.warning(f"Auth metadata update error: {auth_err}")

            # 3. Re-fetch updated profile
            refetched = None
            try:
                refetched = self.get_profile(user_id)
            except Exception:
                pass

            if refetched:
                return refetched

            base = {
                "id": user_id,
                "email": "",
                "username": "student",
                "full_name": filtered_updates.get("full_name", "Student"),
                "course": filtered_updates.get("course", "B.Tech"),
                "branch": filtered_updates.get("branch", "Computer Science"),
                "college": filtered_updates.get("college", ""),
                "semester": filtered_updates.get("semester", "1"),
                "subjects": filtered_updates.get("subjects", []),
                "profile_completed": True,
            }
            base.update(filtered_updates)
            return StudentProfile(**base)

        except Exception as e:
            logger.error(f"Error updating profile for {user_id}: {e}")
            raise DatabaseError("Failed to update student profile.", technical_details=str(e))
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error updating profile for {user_id}: {e}")
            raise DatabaseError("Failed to update student profile.", technical_details=str(e))
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error updating profile for {user_id}: {e}")
            raise DatabaseError("Failed to update student profile.", technical_details=str(e))

    # =========================================================================
    # 2. CONVERSATIONS & CHAT MESSAGES
    # =========================================================================

    def get_or_create_conversation(self, user_id: str, title: str = "Academic Discussion") -> str:
        """Gets the most recent conversation or creates a new one for the user."""
        if not config.is_supabase_configured():
            return LocalDataStore.get_or_create_conversation(user_id, title)

        try:
            client = self._get_client()
            res = (
                client.table("conversations")
                .select("id")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]["id"]

            new_conv = (
                client.table("conversations")
                .insert({"user_id": user_id, "title": title})
                .execute()
            )
            return new_conv.data[0]["id"]
        except Exception as e:
            logger.error(f"Error getting/creating conversation: {e}")
            raise DatabaseError("Unable to initialize chat conversation.", technical_details=str(e))

    def create_new_conversation(self, user_id: str, title: str = "New Discussion") -> str:
        """Explicitly starts a fresh conversation thread."""
        if not config.is_supabase_configured():
            return LocalDataStore.get_or_create_conversation(user_id, title)

        try:
            client = self._get_client()
            new_conv = (
                client.table("conversations")
                .insert({"user_id": user_id, "title": title})
                .execute()
            )
            return new_conv.data[0]["id"]
        except Exception as e:
            logger.error(f"Error creating new conversation: {e}")
            raise DatabaseError("Unable to create conversation.", technical_details=str(e))

    def save_chat_message(
        self, user_id: str, conversation_id: str, role: str, content: str
    ) -> Dict[str, Any]:
        """Saves a user or assistant chat message."""
        if not config.is_supabase_configured():
            LocalDataStore.save_chat_message(user_id, conversation_id, role, content)
            return {"role": role, "content": content}

        try:
            client = self._get_client()
            res = (
                client.table("chat_messages")
                .insert(
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "role": role,
                        "content": content,
                    }
                )
                .execute()
            )
            try:
                client.table("conversations").update({"updated_at": "now()"}).eq("id", conversation_id).execute()
            except Exception:
                pass
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")
            raise DatabaseError("Failed to save chat message.", technical_details=str(e))

    def get_recent_messages(
        self, user_id: str, conversation_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieves recent messages for a conversation in chronological order."""
        if not config.is_supabase_configured():
            return LocalDataStore.get_recent_messages(user_id, conversation_id, limit)

        try:
            client = self._get_client()
            res = (
                client.table("chat_messages")
                .select("*")
                .eq("user_id", user_id)
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Error loading chat messages: {e}")
            raise DatabaseError("Failed to load chat history.", technical_details=str(e))

    def clear_conversation_messages(self, user_id: str, conversation_id: str) -> None:
        """Deletes messages belonging to a conversation."""
        if not config.is_supabase_configured():
            return

        try:
            client = self._get_client()
            client.table("chat_messages").delete().eq("user_id", user_id).eq("conversation_id", conversation_id).execute()
        except Exception as e:
            logger.error(f"Error clearing chat messages: {e}")
            raise DatabaseError("Failed to clear chat history.", technical_details=str(e))

    # =========================================================================
    # 3. DOCUMENTS & CHUNKS
    # =========================================================================

    def save_document(
        self,
        user_id: str,
        filename: str,
        page_count: int,
        extracted_characters: int,
        chunks: List[Dict[str, Any]],
        storage_path: Optional[str] = None,
    ) -> str:
        """Saves document metadata and extracted text chunks."""
        if not config.is_supabase_configured():
            return LocalDataStore.save_document(user_id, filename, page_count, extracted_characters, chunks)

        try:
            client = self._get_client()
            doc_res = (
                client.table("documents")
                .insert(
                    {
                        "user_id": user_id,
                        "filename": filename,
                        "page_count": page_count,
                        "extracted_characters": extracted_characters,
                        "storage_path": storage_path,
                        "processing_status": "completed",
                    }
                )
                .execute()
            )
            doc_id = doc_res.data[0]["id"]

            if chunks:
                chunk_payloads = [
                    {
                        "document_id": doc_id,
                        "user_id": user_id,
                        "chunk_index": c["chunk_index"],
                        "page_start": c["page_start"],
                        "page_end": c["page_end"],
                        "chunk_text": c["chunk_text"],
                    }
                    for c in chunks
                ]
                batch_size = 50
                for i in range(0, len(chunk_payloads), batch_size):
                    batch = chunk_payloads[i : i + batch_size]
                    client.table("document_chunks").insert(batch).execute()

            return doc_id
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            raise DatabaseError("Failed to save document records.", technical_details=str(e))

    def list_documents(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists uploaded documents for the user."""
        if not config.is_supabase_configured():
            return LocalDataStore.list_documents(user_id, limit)

        try:
            client = self._get_client()
            res = (
                client.table("documents")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def get_document_chunks(self, user_id: str, document_id: str) -> List[Dict[str, Any]]:
        """Retrieves chunks for a specific document."""
        if not config.is_supabase_configured():
            return LocalDataStore.get_document_chunks(user_id, document_id)

        try:
            client = self._get_client()
            res = (
                client.table("document_chunks")
                .select("*")
                .eq("user_id", user_id)
                .eq("document_id", document_id)
                .order("chunk_index", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Error fetching chunks: {e}")
            return []

    def delete_document(self, user_id: str, document_id: str) -> None:
        """Deletes a document and its cascading chunks."""
        if not config.is_supabase_configured():
            LocalDataStore.delete_document(user_id, document_id)
            return

        try:
            client = self._get_client()
            client.table("documents").delete().eq("user_id", user_id).eq("id", document_id).execute()
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise DatabaseError("Failed to delete document.", technical_details=str(e))

    # =========================================================================
    # 4. QUIZ ATTEMPTS
    # =========================================================================

    def save_quiz_attempt(
        self,
        user_id: str,
        subject: str,
        topic: str,
        difficulty: str,
        score: int,
        total: int,
        percentage: float,
        answers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Saves a completed quiz attempt."""
        if not config.is_supabase_configured():
            LocalDataStore.save_quiz_attempt(user_id, subject, topic, difficulty, score, total, percentage, answers)
            return {"score": score, "total": total}

        try:
            client = self._get_client()
            res = (
                client.table("quiz_attempts")
                .insert(
                    {
                        "user_id": user_id,
                        "subject": subject,
                        "topic": topic,
                        "difficulty": difficulty,
                        "score": score,
                        "total": total,
                        "percentage": percentage,
                        "answers": answers,
                    }
                )
                .execute()
            )
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Error saving quiz attempt: {e}")
            raise DatabaseError("Failed to persist quiz attempt.", technical_details=str(e))

    def list_quiz_attempts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves past quiz attempts for the student."""
        if not config.is_supabase_configured():
            return LocalDataStore.list_quiz_attempts(user_id, limit)

        try:
            client = self._get_client()
            res = (
                client.table("quiz_attempts")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Error loading quiz attempts: {e}")
            return []

    # =========================================================================
    # 5. STUDY PLANS
    # =========================================================================

    def save_study_plan(
        self,
        user_id: str,
        title: str,
        exam_date: str,
        daily_hours: float,
        subjects: List[str],
        plan_text: str,
    ) -> Dict[str, Any]:
        """Saves a generated study plan."""
        if not config.is_supabase_configured():
            LocalDataStore.save_study_plan(user_id, title, exam_date, daily_hours, subjects, plan_text)
            return {"title": title}

        try:
            client = self._get_client()
            res = (
                client.table("study_plans")
                .insert(
                    {
                        "user_id": user_id,
                        "title": title,
                        "exam_date": str(exam_date),
                        "daily_hours": daily_hours,
                        "subjects": subjects,
                        "plan_text": plan_text,
                    }
                )
                .execute()
            )
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Error saving study plan: {e}")
            raise DatabaseError("Failed to save study plan.", technical_details=str(e))

    def list_study_plans(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves saved study plans for the student."""
        if not config.is_supabase_configured():
            return LocalDataStore.list_study_plans(user_id, limit)

        try:
            client = self._get_client()
            res = (
                client.table("study_plans")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Error loading study plans: {e}")
            return []

    def delete_study_plan(self, user_id: str, plan_id: str) -> None:
        """Deletes a saved study plan."""
        if not config.is_supabase_configured():
            LocalDataStore.delete_study_plan(user_id, plan_id)
            return

        try:
            client = self._get_client()
            client.table("study_plans").delete().eq("user_id", user_id).eq("id", plan_id).execute()
        except Exception as e:
            logger.error(f"Error deleting study plan: {e}")
            raise DatabaseError("Failed to delete study plan.", technical_details=str(e))

    # =========================================================================
    # 6. DASHBOARD STATISTICS
    # =========================================================================

    def get_dashboard_metrics(self, user_id: str) -> Dict[str, Any]:
        """Calculates personalized statistics for the student dashboard."""
        if not config.is_supabase_configured():
            return LocalDataStore.get_dashboard_metrics(user_id)

        try:
            client = self._get_client()
            msg_res = (
                client.table("chat_messages")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            total_messages = msg_res.count if msg_res.count is not None else 0

            quiz_res = (
                client.table("quiz_attempts")
                .select("score, total, percentage")
                .eq("user_id", user_id)
                .execute()
            )
            quizzes = quiz_res.data or []
            total_quizzes = len(quizzes)
            avg_score = (
                round(sum(float(q.get("percentage", 0)) for q in quizzes) / total_quizzes, 1)
                if total_quizzes > 0
                else 0.0
            )

            plan_res = (
                client.table("study_plans")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            total_plans = plan_res.count if plan_res.count is not None else 0

            doc_res = (
                client.table("documents")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            total_docs = doc_res.count if doc_res.count is not None else 0

            return {
                "total_messages": total_messages,
                "total_quizzes": total_quizzes,
                "avg_quiz_score": avg_score,
                "total_plans": total_plans,
                "total_documents": total_docs,
            }
        except Exception as e:
            logger.warning(f"Error fetching dashboard metrics: {e}")
            return {
                "total_messages": 0,
                "total_quizzes": 0,
                "avg_quiz_score": 0.0,
                "total_plans": 0,
                "total_documents": 0,
            }


db_service = DatabaseService()
