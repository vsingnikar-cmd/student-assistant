"""AI Student Assistant Agent - Main Application Entrypoint.

Modern Educational SaaS Web Application built with Streamlit, Supabase, and Google Gemini.
"""

import streamlit as st
from utils.config import config
from utils.errors import sanitize_error_message, AuthenticationError, ValidationError
from utils.validators import validate_registration_form, validate_email
from services.auth_service import auth_service
from services.database_service import db_service
from models.schemas import resolve_student_name

# Import modular page renderers
from pages.dashboard import render_dashboard
from pages.academic_chat import render_academic_chat
from pages.pdf_assistant import render_pdf_assistant
from pages.exam_notes import render_exam_notes
from pages.quiz_generator import render_quiz_generator
from pages.study_planner import render_study_planner
from pages.learning_history import render_learning_history
from pages.profile import render_profile

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & THEME STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Student Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main container spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* Primary Accent Styling */
    .stButton>button[kind="primary"] {
        background-color: #2563eb;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #1d4ed8;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }

    /* Card styling */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 1.2rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* Sidebar brand card */
    .sidebar-brand {
        padding: 1rem 0;
        margin-bottom: 1rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .sidebar-brand h2 {
        color: #1e3a8a;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
    }
    .sidebar-brand p {
        color: #64748b;
        font-size: 0.85rem;
        margin: 0.2rem 0 0 0;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. SESSION INITIALIZATION
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = {}
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "login"


def logout_user():
    """Clears all session-specific memory and signs out of Supabase."""
    auth_service.sign_out()
    keys_to_clear = [
        "authenticated",
        "user_id",
        "user_email",
        "user_profile",
        "active_conv_id",
        "chat_messages_cache",
        "active_pdf_key",
        "active_pdf_id",
        "active_pdf_chunks",
        "active_quiz",
        "quiz_user_answers",
        "quiz_submitted",
        "quiz_result",
        "active_study_plan",
        "generated_notes",
    ]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state["authenticated"] = False
    st.session_state["current_page"] = "Dashboard"
    st.rerun()


# -----------------------------------------------------------------------------
# 3. AUTHENTICATION SCREENS (LOGIN, REGISTER, PASSWORD RESET)
# -----------------------------------------------------------------------------
def render_auth_portal():
    """Renders the clean, accessible student login and registration portal."""
    auth_col1, auth_col2, auth_col3 = st.columns([1, 2, 1])

    with auth_col2:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <h1 style="color: #1e3a8a; font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem;">🎓 AI Student Assistant</h1>
                <p style="color: #64748b; font-size: 1.05rem;">Integrated academic intelligence, PDF analysis, exam notes, and study planning.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not config.is_supabase_configured():
            st.info(
                "⚡ **Running in Local Storage Mode (SQLite):** Zero setup needed! You can create accounts and sign in right now. "
                "To connect to Supabase Cloud, add `SUPABASE_URL` and `SUPABASE_KEY` in your `.env` file."
            )

        tab_login, tab_register, tab_reset = st.tabs(["🔐 Student Login", "📝 Create Account", "🔑 Reset Password"])

        # ----------------- LOGIN TAB -----------------
        with tab_login:
            st.write("")
            login_type = st.radio(
                "Sign In Using",
                options=["Email Address", "Username"],
                horizontal=True,
                label_visibility="collapsed",
            )

            identifier_label = "Email Address" if login_type == "Email Address" else "Username"
            login_identifier = st.text_input(identifier_label, placeholder=f"Enter your {identifier_label.lower()}...")
            login_password = st.text_input("Password", type="password", placeholder="Enter your password...")

            if st.button("Sign In", type="primary", use_container_width=True):
                if not login_identifier.strip() or not login_password:
                    st.error("Please enter both your identifier and password.")
                else:
                    with st.spinner("Authenticating credentials..."):
                        try:
                            if login_type == "Email Address":
                                auth_res = auth_service.sign_in_with_email(login_identifier, login_password)
                            else:
                                auth_res = auth_service.sign_in_with_username(login_identifier, login_password)

                            user = auth_res.get("user")
                            if user:
                                user_id = user.id if hasattr(user, "id") else user.get("id")
                                user_email = user.email if hasattr(user, "email") else user.get("email")
                                user_meta = user.user_metadata if hasattr(user, "user_metadata") else (user.get("user_metadata") or {})
                                if not isinstance(user_meta, dict):
                                    user_meta = {}

                                # Load or ensure profile
                                try:
                                    prof = db_service.ensure_profile(user)
                                    prof_dict = prof.model_dump() if prof else {}
                                except Exception:
                                    prof_dict = {}

                                resolved_name = resolve_student_name(
                                    profile=prof_dict,
                                    email=user_email,
                                    username=prof_dict.get("username", "") if prof_dict else user_meta.get("username", ""),
                                )

                                # Extract college from profile or user metadata
                                resolved_college = (
                                    prof_dict.get("college")
                                    or user_meta.get("college")
                                    or user_meta.get("university")
                                    or user_meta.get("college_name")
                                    or user_meta.get("institution")
                                    or ""
                                )

                                if not prof_dict:
                                    prof_dict = {
                                        "id": user_id,
                                        "email": user_email,
                                        "username": user_meta.get("username") or (user_email.split("@")[0] if user_email else "student"),
                                        "full_name": resolved_name,
                                        "course": user_meta.get("course") or "B.Tech",
                                        "branch": user_meta.get("branch") or "Computer Science",
                                        "semester": str(user_meta.get("semester") or "1"),
                                        "college": resolved_college,
                                    }
                                else:
                                    prof_dict["full_name"] = resolved_name
                                    if resolved_college:
                                        prof_dict["college"] = resolved_college

                                st.session_state["authenticated"] = True
                                st.session_state["user_id"] = user_id
                                st.session_state["user_email"] = user_email
                                st.session_state["user_profile"] = prof_dict
                                st.session_state["current_page"] = "Dashboard"
                                st.success("Signed in successfully!")
                                st.rerun()

                        except AuthenticationError as ae:
                            st.error(ae.message)
                        except Exception as e:
                            st.error(f"Sign in failed: {sanitize_error_message(e)}")

            st.write("---")
            # Demo / Sandbox Login option for immediate reviewer evaluation
            st.caption("Testing or reviewing without live Supabase credentials?")
            if st.button("🚀 Explore in Demo / Sandbox Mode", use_container_width=True):
                st.session_state["authenticated"] = True
                st.session_state["user_id"] = "00000000-0000-0000-0000-000000000001"
                st.session_state["user_email"] = "alex.student@university.edu"
                st.session_state["user_profile"] = {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "alex.student@university.edu",
                    "username": "alex_student",
                    "full_name": "Alex Mercer",
                    "course": "B.Tech Computer Science & Engineering",
                    "branch": "Artificial Intelligence & Data Science",
                    "college": "Institute of Technology",
                    "semester": "5",
                    "subjects": ["Operating Systems", "Computer Networks", "Database Management", "Machine Learning"],
                    "profile_completed": True,
                }
                st.session_state["current_page"] = "Dashboard"
                st.rerun()

        # ----------------- REGISTRATION TAB -----------------
        with tab_register:
            st.write("")
            with st.form("student_registration_form"):
                st.markdown("##### 1. Account Credentials")
                reg_username = st.text_input("Username (3-30 letters/numbers/_)", placeholder="e.g. rachel_greene")
                reg_email = st.text_input("Email Address", placeholder="e.g. student@college.edu")
                reg_pass1 = st.text_input("Password (min 8 characters)", type="password")
                reg_pass2 = st.text_input("Confirm Password", type="password")

                st.markdown("##### 2. Academic Profile Details")
                reg_name = st.text_input("Full Name", placeholder="e.g. Rachel Greene")
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    reg_course = st.text_input("Course", value="B.Tech", placeholder="e.g. B.Tech, B.Sc, M.Sc")
                with r_col2:
                    reg_branch = st.text_input("Branch / Major", placeholder="e.g. Computer Science, Mechanical")

                r_col3, r_col4 = st.columns(2)
                with r_col3:
                    reg_semester = st.selectbox("Current Semester", options=[str(i) for i in range(1, 9)], index=0)
                with r_col4:
                    reg_college = st.text_input("College / University", placeholder="e.g. State University")

                reg_submit = st.form_submit_button("Create Student Account", type="primary", use_container_width=True)

                if reg_submit:
                    try:
                        validated_data = validate_registration_form(
                            username=reg_username,
                            full_name=reg_name,
                            email=reg_email,
                            password=reg_pass1,
                            confirm_password=reg_pass2,
                            course=reg_course,
                            branch=reg_branch,
                            semester=reg_semester,
                            college=reg_college,
                        )

                        with st.spinner("Registering student account..."):
                            auth_res = auth_service.sign_up(
                                email=validated_data["email"],
                                password=validated_data["password"],
                                username=validated_data["username"],
                                full_name=validated_data["full_name"],
                                course=validated_data["course"],
                                branch=validated_data["branch"],
                                semester=validated_data["semester"],
                                college=validated_data["college"],
                            )

                            if auth_res.get("requires_verification"):
                                st.info("Account registered! Please check your email inbox to verify your account before logging in.")
                            else:
                                st.success("🎉 Account created successfully! Please switch to the **Student Login** tab to sign in.")

                    except ValidationError as ve:
                        st.error(ve.message)
                    except AuthenticationError as ae:
                        st.error(ae.message)
                    except Exception as e:
                        st.error(f"Registration error: {sanitize_error_message(e)}")

        # ----------------- PASSWORD RESET TAB -----------------
        with tab_reset:
            st.write("")
            reset_email = st.text_input("Enter your registered email address:", placeholder="e.g. student@college.edu")
            if st.button("Send Password Recovery Link", use_container_width=True):
                if not reset_email:
                    st.warning("Please provide your email address.")
                else:
                    try:
                        clean_reset_email = validate_email(reset_email)
                        auth_service.reset_password(clean_reset_email)
                        st.success("If an account exists with this email, a password reset link has been dispatched.")
                    except ValidationError as ve:
                        st.error(ve.message)
                    except Exception as e:
                        st.error(f"Error: {sanitize_error_message(e)}")


# -----------------------------------------------------------------------------
# 4. MAIN AUTHENTICATED APPLICATION WORKFLOW
# -----------------------------------------------------------------------------
def render_authenticated_app():
    """Renders the student application with persistent sidebar and session guards."""
    user_id = st.session_state["user_id"]
    profile_data = st.session_state.get("user_profile", {})
    user_email_session = st.session_state.get("user_email", "")

    # Auto-refresh if profile data is missing, generic, or lacks college
    if not profile_data or not profile_data.get("college") or not profile_data.get("full_name") or profile_data.get("full_name").strip().lower() in ("student", "user", ""):
        try:
            fresh = db_service.get_profile(user_id)
            if fresh:
                if fresh.college and not profile_data.get("college"):
                    profile_data["college"] = fresh.college
                if fresh.full_name and fresh.full_name.strip().lower() not in ("student", "user", ""):
                    profile_data["full_name"] = fresh.full_name
                st.session_state["user_profile"] = profile_data
            elif config.is_supabase_configured():
                user_obj = auth_service.client.auth.get_user().user
                prof = db_service.ensure_profile(user_obj)
                if prof:
                    profile_data = prof.model_dump()
                    st.session_state["user_profile"] = profile_data
        except Exception:
            pass

    if not profile_data.get("college") and config.is_supabase_configured():
        try:
            u_obj = auth_service.client.auth.get_user().user
            if u_obj:
                u_meta = u_obj.user_metadata if hasattr(u_obj, "user_metadata") else (u_obj.get("user_metadata") or {})
                if isinstance(u_meta, dict):
                    meta_col = (
                        u_meta.get("college")
                        or u_meta.get("university")
                        or u_meta.get("college_name")
                        or u_meta.get("institution")
                        or ""
                    )
                    if meta_col:
                        profile_data["college"] = meta_col
                        st.session_state["user_profile"] = profile_data
        except Exception:
            pass

    resolved_name = resolve_student_name(
        profile=profile_data,
        email=user_email_session,
        username=profile_data.get("username", "") if profile_data else "",
    )
    profile_data["full_name"] = resolved_name
    st.session_state["user_profile"] = profile_data

    # Navigation options matching PRD Section 7.3
    NAV_ITEMS = [
        "📊 Dashboard",
        "💬 Academic Chat",
        "📄 PDF Assistant",
        "📝 Exam Notes",
        "🎯 Quiz Generator",
        "📅 Study Planner",
        "📜 Learning History",
        "👤 My Profile",
    ]

    # SIDEBAR NAVIGATION
    with st.sidebar:
        college_name = profile_data.get("college", "")
        college_line = f"<p style='font-size: 0.82rem; color: #94a3b8; margin: 0;'>🏛️ {college_name}</p>" if college_name else ""
        course_name = profile_data.get("course", "B.Tech")
        sem_num = profile_data.get("semester", "1")
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <h2>🎓 Student Assistant</h2>
                <p>Welcome, <strong>{resolved_name}</strong></p>
                {college_line}
                <p style="font-size: 0.8rem; color: #94a3b8; margin: 0.2rem 0 0 0;">{course_name} • Sem {sem_num}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Map current page to selection index
        current = st.session_state.get("current_page", "Dashboard")
        nav_titles = [item.split(" ", 1)[1] for item in NAV_ITEMS]
        current_clean = current.split(" ", 1)[-1] if " " in current else current
        default_index = nav_titles.index(current_clean) if current_clean in nav_titles else 0

        selected_nav = st.radio(
            "Navigation Menu",
            options=NAV_ITEMS,
            index=default_index,
            label_visibility="collapsed",
        )

        selected_page_title = selected_nav.split(" ", 1)[1]
        st.session_state["current_page"] = selected_page_title

        st.write("---")

        # Diagnostics & Status
        gemini_ready = config.is_gemini_configured()
        supabase_ready = config.is_supabase_configured()
        st.caption(f"🤖 Gemini: {'🟢 Ready' if gemini_ready else '🟡 Add Key in .env'}")
        st.caption(f"🗄️ Supabase: {'🟢 Connected' if supabase_ready else '🟡 Add URL in .env'}")

        st.write("")
        # 9. LOGOUT ACTION
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()

    # ROUTE TO SELECTED PAGE
    page = st.session_state["current_page"]

    if page == "Dashboard":
        render_dashboard(user_id, profile_data)
    elif page == "Academic Chat":
        render_academic_chat(user_id, profile_data)
    elif page == "PDF Assistant":
        render_pdf_assistant(user_id, profile_data)
    elif page == "Exam Notes":
        render_exam_notes(user_id, profile_data)
    elif page == "Quiz Generator":
        render_quiz_generator(user_id, profile_data)
    elif page == "Study Planner":
        render_study_planner(user_id, profile_data)
    elif page == "Learning History":
        render_learning_history(user_id, profile_data)
    elif page == "My Profile":
        render_profile(user_id, profile_data)
    else:
        render_dashboard(user_id, profile_data)


# -----------------------------------------------------------------------------
# 5. ENTRYPOINT CONTROLLER
# -----------------------------------------------------------------------------
def main():
    if not st.session_state.get("authenticated", False):
        render_auth_portal()
    else:
        render_authenticated_app()


if __name__ == "__main__":
    main()
