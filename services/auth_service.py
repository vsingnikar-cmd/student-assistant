"""Authentication service for Supabase Auth, session management, and secure login."""

import logging
from typing import Optional, Dict, Any
import requests
from supabase import create_client, Client
from utils.config import config
from utils.errors import AuthenticationError
from utils.validators import validate_email, validate_password, validate_username
from services.local_db import LocalAuthStore

logger = logging.getLogger(__name__)


class AuthService:
    """Handles student authentication, session restoration, and user identity."""

    def __init__(self):
        self._client: Optional[Client] = None
        self._admin_client: Optional[Client] = None
        self._init_clients()

    def _init_clients(self):
        """Initializes Supabase anon client and optional service role admin client."""
        if config.is_supabase_configured():
            try:
                self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                if config.SUPABASE_SERVICE_ROLE_KEY:
                    self._admin_client = create_client(
                        config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY
                    )
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")

    @property
    def client(self) -> Client:
        if not self._client:
            self._init_clients()
        if not self._client and config.is_supabase_configured():
            try:
                self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            except Exception as e:
                logger.error(f"Supabase client creation error: {e}")
        if not self._client:
            raise AuthenticationError(
                "Supabase is not configured. Please check your SUPABASE_URL and SUPABASE_KEY in .env."
            )
        return self._client

    def sign_up(
        self,
        email: str,
        password: str,
        username: str,
        full_name: str,
        course: str,
        branch: str,
        semester: str,
        college: str = "",
    ) -> Dict[str, Any]:
        """Registers a new student account in Supabase Auth or local storage and creates profile."""
        clean_email = validate_email(email)
        clean_username = validate_username(username)
        validate_password(password)

        if not config.is_supabase_configured():
            return LocalAuthStore.sign_up(
                email=clean_email,
                password=password,
                username=clean_username,
                full_name=full_name,
                course=course,
                branch=branch,
                semester=semester,
                college=college,
            )

        try:
            active_client = self.client
        except AuthenticationError:
            return LocalAuthStore.sign_up(
                email=clean_email,
                password=password,
                username=clean_username,
                full_name=full_name,
                course=course,
                branch=branch,
                semester=semester,
                college=college,
            )

        # 1. Check if username is already taken (case-insensitive)
        if self._admin_client:
            existing = (
                self._admin_client.table("profiles")
                .select("id")
                .ilike("username", clean_username)
                .execute()
            )
            if existing.data and len(existing.data) > 0:
                raise AuthenticationError(f"Username '{clean_username}' is already taken.")

        # 2. Register user with Supabase Auth
        try:
            auth_response = self.client.auth.sign_up(
                {
                    "email": clean_email,
                    "password": password,
                    "options": {
                        "data": {
                            "username": clean_username,
                            "full_name": full_name,
                            "course": course,
                            "branch": branch,
                            "semester": semester,
                            "college": college,
                        }
                    },
                }
            )
        except Exception as e:
            err_msg = str(e)
            if "already registered" in err_msg.lower():
                raise AuthenticationError("An account with this email address already exists.")
            raise AuthenticationError(f"Registration failed: {err_msg}")

        user = auth_response.user
        if not user:
            raise AuthenticationError("Registration failed. No user was returned by authentication service.")

        # 3. Create student profile in profiles table
        profile_data = {
            "id": user.id,
            "email": clean_email,
            "username": clean_username,
            "full_name": full_name,
            "course": course,
            "branch": branch,
            "semester": semester,
            "college": college,
            "profile_completed": True,
            "subjects": [],
        }

        # Write profile using service client if available to ensure reliable initial profile creation
        target_client = self._admin_client if self._admin_client else self.client
        try:
            target_client.table("profiles").upsert(profile_data).execute()
        except Exception as e:
            logger.warning(f"Profile creation warning: {e}. Profile can be completed on first login.")

        return {
            "user": user,
            "session": auth_response.session,
            "requires_verification": auth_response.session is None,
        }

    def sign_in_with_email(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticates a student using email and password."""
        clean_email = validate_email(email)
        if not config.is_supabase_configured():
            return LocalAuthStore.sign_in_with_email(clean_email, password)
        try:
            response = self.client.auth.sign_in_with_password(
                {"email": clean_email, "password": password}
            )
            return {"user": response.user, "session": response.session}
        except AuthenticationError as ae:
            if "not configured" in ae.message.lower():
                return LocalAuthStore.sign_in_with_email(clean_email, password)
            raise
        except Exception as e:
            logger.warning(f"Login failed for email {clean_email}: {e}")
            raise AuthenticationError("Invalid email or password.")

    def sign_in_with_username(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticates a student using username and password via secure server-side lookup."""
        clean_username = validate_username(username).lower()
        if not config.is_supabase_configured():
            return LocalAuthStore.sign_in_with_username(clean_username, password)

        # Method 1: Edge Function if available
        edge_function_url = f"{config.SUPABASE_URL}/functions/v1/username-login"
        try:
            resp = requests.post(
                edge_function_url,
                json={"username": clean_username, "password": password},
                headers={
                    "Authorization": f"Bearer {config.SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data
            elif resp.status_code == 401:
                raise AuthenticationError("Invalid username or password.")
        except AuthenticationError:
            raise
        except Exception:
            pass

        # Method 2: Trusted server-side admin client lookup
        if self._admin_client:
            try:
                res = (
                    self._admin_client.table("profiles")
                    .select("email")
                    .ilike("username", clean_username)
                    .maybe_single()
                    .execute()
                )
                if not res or not res.data or not res.data.get("email"):
                    raise AuthenticationError("Invalid username or password.")
                
                target_email = res.data["email"]
                return self.sign_in_with_email(target_email, password)
            except AuthenticationError:
                raise
            except Exception as e:
                logger.error(f"Error during admin username resolution: {e}")
                raise AuthenticationError("Invalid username or password.")

        # Method 3: Fallback to local auth store
        return LocalAuthStore.sign_in_with_username(clean_username, password)

    def reset_password(self, email: str) -> None:
        """Sends a password recovery email to the student."""
        clean_email = validate_email(email)
        try:
            self.client.auth.reset_password_email(clean_email)
        except Exception as e:
            logger.error(f"Password reset failed: {e}")
            # For security, do not disclose whether the email exists
            pass

    def sign_out(self) -> None:
        """Signs the student out and invalidates the session."""
        try:
            self.client.auth.sign_out()
        except Exception as e:
            logger.warning(f"Sign out issue: {e}")


# Singleton instance
auth_service = AuthService()
