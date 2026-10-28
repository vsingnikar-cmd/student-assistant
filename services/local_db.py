"""Local SQLite database fallback.

Provides seamless local persistence for profiles, chat, quizzes, study plans,
and documents when remote Supabase credentials are not yet configured in .env.
"""

import sqlite3
import json
import uuid
import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from utils.errors import AuthenticationError, DatabaseError

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "local_storage.db")


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_local_db():
    """Initializes local tables matching the Supabase schema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Local Auth Users Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS local_users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Profiles Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                username TEXT NOT NULL,
                full_name TEXT NOT NULL,
                course TEXT NOT NULL,
                branch TEXT NOT NULL,
                college TEXT,
                semester TEXT NOT NULL,
                subjects TEXT DEFAULT '[]',
                profile_completed INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Conversations Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Chat Messages Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Documents Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                extracted_characters INTEGER NOT NULL,
                storage_path TEXT,
                processing_status TEXT DEFAULT 'completed',
                created_at TEXT NOT NULL
            )
            """
        )

        # Document Chunks Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                page_start INTEGER NOT NULL,
                page_end INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Quiz Attempts Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                answers TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Study Plans Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS study_plans (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                exam_date TEXT NOT NULL,
                daily_hours REAL NOT NULL,
                subjects TEXT NOT NULL,
                plan_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        conn.commit()


# Initialize schema on import
init_local_db()


def hash_password(password: str, salt: Optional[str] = None) -> (str, str):
    """Secure password hashing using PBKDF2 with SHA-256."""
    if not salt:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return pwd_hash, salt


class LocalAuthStore:
    """Local SQLite implementation of authentication."""

    @staticmethod
    def sign_up(email: str, password: str, username: str, full_name: str, course: str, branch: str, semester: str, college: str = ""):
        user_id = str(uuid.uuid4())
        clean_email = email.strip().lower()
        clean_user = username.strip().lower()

        with get_connection() as conn:
            cursor = conn.cursor()
            # Check unique username
            cursor.execute("SELECT id FROM local_users WHERE LOWER(username) = ?", (clean_user,))
            if cursor.fetchone():
                raise AuthenticationError(f"Username '{username}' is already taken.")

            # Check unique email
            cursor.execute("SELECT id FROM local_users WHERE LOWER(email) = ?", (clean_email,))
            if cursor.fetchone():
                raise AuthenticationError("An account with this email address already exists.")

            pwd_hash, salt = hash_password(password)
            now_iso = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO local_users (id, email, username, password_hash, salt, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, clean_email, username.strip(), pwd_hash, salt, now_iso),
            )

            cursor.execute(
                """
                INSERT INTO profiles (id, email, username, full_name, course, branch, college, semester, subjects, profile_completed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, clean_email, username.strip(), full_name, course, branch, college, semester, "[]", now_iso, now_iso),
            )
            conn.commit()

        return {
            "user": {"id": user_id, "email": clean_email},
            "session": {"access_token": "local-token"},
            "requires_verification": False,
        }

    @staticmethod
    def sign_in_with_email(email: str, password: str):
        clean_email = email.strip().lower()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM local_users WHERE LOWER(email) = ?", (clean_email,))
            row = cursor.fetchone()
            if not row:
                raise AuthenticationError("Invalid email or password.")

            expected_hash, _ = hash_password(password, salt=row["salt"])
            if expected_hash != row["password_hash"]:
                raise AuthenticationError("Invalid email or password.")

            return {"user": {"id": row["id"], "email": row["email"]}, "session": {"token": "local"}}

    @staticmethod
    def sign_in_with_username(username: str, password: str):
        clean_user = username.strip().lower()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM local_users WHERE LOWER(username) = ?", (clean_user,))
            row = cursor.fetchone()
            if not row:
                raise AuthenticationError("Invalid username or password.")

            expected_hash, _ = hash_password(password, salt=row["salt"])
            if expected_hash != row["password_hash"]:
                raise AuthenticationError("Invalid username or password.")

            return {"user": {"id": row["id"], "email": row["email"]}, "session": {"token": "local"}}


class LocalDataStore:
    """Local SQLite implementation of data persistence."""

    @staticmethod
    def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["subjects"] = json.loads(data.get("subjects") or "[]")
            except Exception:
                data["subjects"] = []
            data["profile_completed"] = bool(data.get("profile_completed", 1))
            return data

    @staticmethod
    def update_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        with get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE profiles
                SET full_name = ?, course = ?, branch = ?, college = ?, semester = ?, subjects = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updates.get("full_name", ""),
                    updates.get("course", ""),
                    updates.get("branch", ""),
                    updates.get("college", ""),
                    updates.get("semester", ""),
                    json.dumps(updates.get("subjects", [])),
                    now_iso,
                    user_id,
                ),
            )
            conn.commit()
        return LocalDataStore.get_profile(user_id)

    @staticmethod
    def get_or_create_conversation(user_id: str, title: str = "Academic Discussion") -> str:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            
            conv_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, user_id, title, now_iso, now_iso),
            )
            conn.commit()
            return conv_id

    @staticmethod
    def save_chat_message(user_id: str, conversation_id: str, role: str, content: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            msg_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO chat_messages (id, conversation_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, user_id, role, content, now_iso),
            )
            cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso, conversation_id))
            conn.commit()

    @staticmethod
    def get_recent_messages(user_id: str, conversation_id: str, limit: int = 50):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chat_messages WHERE user_id = ? AND conversation_id = ? ORDER BY created_at ASC LIMIT ?",
                (user_id, conversation_id, limit),
            )
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def save_document(user_id: str, filename: str, page_count: int, extracted_characters: int, chunks: List[Dict[str, Any]]):
        with get_connection() as conn:
            cursor = conn.cursor()
            doc_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO documents (id, user_id, filename, page_count, extracted_characters, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, user_id, filename, page_count, extracted_characters, now_iso),
            )
            for c in chunks:
                chunk_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO document_chunks (id, document_id, user_id, chunk_index, page_start, page_end, chunk_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chunk_id, doc_id, user_id, c["chunk_index"], c["page_start"], c["page_end"], c["chunk_text"], now_iso),
                )
            conn.commit()
            return doc_id

    @staticmethod
    def list_documents(user_id: str, limit: int = 20):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_document_chunks(user_id: str, document_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_chunks WHERE user_id = ? AND document_id = ? ORDER BY chunk_index ASC", (user_id, document_id))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def delete_document(user_id: str, document_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_chunks WHERE user_id = ? AND document_id = ?", (user_id, document_id))
            cursor.execute("DELETE FROM documents WHERE user_id = ? AND id = ?", (user_id, document_id))
            conn.commit()

    @staticmethod
    def save_quiz_attempt(user_id: str, subject: str, topic: str, difficulty: str, score: int, total: int, percentage: float, answers: List[Dict[str, Any]]):
        with get_connection() as conn:
            cursor = conn.cursor()
            attempt_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO quiz_attempts (id, user_id, subject, topic, difficulty, score, total, percentage, answers, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (attempt_id, user_id, subject, topic, difficulty, score, total, percentage, json.dumps(answers), now_iso),
            )
            conn.commit()

    @staticmethod
    def list_quiz_attempts(user_id: str, limit: int = 50):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            results = []
            for r in cursor.fetchall():
                item = dict(r)
                try:
                    item["answers"] = json.loads(item["answers"])
                except Exception:
                    item["answers"] = []
                results.append(item)
            return results

    @staticmethod
    def save_study_plan(user_id: str, title: str, exam_date: str, daily_hours: float, subjects: List[str], plan_text: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            plan_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO study_plans (id, user_id, title, exam_date, daily_hours, subjects, plan_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (plan_id, user_id, title, exam_date, daily_hours, json.dumps(subjects), plan_text, now_iso, now_iso),
            )
            conn.commit()

    @staticmethod
    def list_study_plans(user_id: str, limit: int = 50):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM study_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            results = []
            for r in cursor.fetchall():
                item = dict(r)
                try:
                    item["subjects"] = json.loads(item["subjects"])
                except Exception:
                    item["subjects"] = []
                results.append(item)
            return results

    @staticmethod
    def delete_study_plan(user_id: str, plan_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM study_plans WHERE user_id = ? AND id = ?", (user_id, plan_id))
            conn.commit()

    @staticmethod
    def get_dashboard_metrics(user_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,))
            total_messages = cursor.fetchone()[0]

            cursor.execute("SELECT percentage FROM quiz_attempts WHERE user_id = ?", (user_id,))
            quizzes = cursor.fetchall()
            total_quizzes = len(quizzes)
            avg_score = round(sum(q[0] for q in quizzes) / total_quizzes, 1) if total_quizzes > 0 else 0.0

            cursor.execute("SELECT COUNT(*) FROM study_plans WHERE user_id = ?", (user_id,))
            total_plans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_id,))
            total_docs = cursor.fetchone()[0]

            return {
                "total_messages": total_messages,
                "total_quizzes": total_quizzes,
                "avg_quiz_score": avg_score,
                "total_plans": total_plans,
                "total_documents": total_docs,
            }
