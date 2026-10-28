import streamlit as st
from services.database_service import db_service
from services.auth_service import auth_service
from models.schemas import resolve_student_name
from utils.config import config
from utils.errors import sanitize_error_message


def render_profile(user_id: str, profile_data: dict):
    """Renders the student academic profile view and editing interface."""
    st.title("👤 My Academic Profile")
    st.caption("View and keep your academic identity up to date to personalize your tutoring, exam notes, and study plans.")

    # Refresh from database if cached profile is missing, sparse, or lacks college
    if not profile_data or not profile_data.get("college") or not profile_data.get("full_name") or profile_data.get("full_name").strip().lower() in ("student", "user", ""):
        try:
            fresh = db_service.get_profile(user_id)
            if fresh:
                if fresh.college and not profile_data.get("college"):
                    profile_data["college"] = fresh.college
                if fresh.full_name and fresh.full_name.strip().lower() not in ("student", "user", ""):
                    profile_data["full_name"] = fresh.full_name
                st.session_state["user_profile"] = profile_data
        except Exception:
            pass

    user_email_session = st.session_state.get("user_email", "")
    username_val = profile_data.get("username") or (user_email_session.split("@")[0] if user_email_session else "student")
    email_val = profile_data.get("email") or user_email_session
    course_val = profile_data.get("course") or "B.Tech"
    branch_val = profile_data.get("branch") or "Computer Science"
    semester_val = str(profile_data.get("semester") or "1")
    college_val = profile_data.get("college") or profile_data.get("university") or profile_data.get("college_name") or ""

    # Check Supabase Auth user_metadata if college is still not found in profile
    if not college_val and config.is_supabase_configured():
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
                        college_val = meta_col
                        profile_data["college"] = college_val
                        st.session_state["user_profile"] = profile_data
                        try:
                            db_service.update_profile(user_id, {"college": college_val})
                        except Exception:
                            pass
        except Exception:
            pass

    # Intelligently resolve the student's full name
    resolved_name = resolve_student_name(profile_data, email=email_val, username=username_val)

    # -------------------------------------------------------------------------
    # 1. VISUAL STUDENT PROFILE CARD (Displays Full Name, College, and Academic Details)
    # -------------------------------------------------------------------------
    college_display = college_val if college_val else "College / University not specified yet (Add in the form below)"
    avatar_initial = resolved_name[0].upper() if resolved_name and resolved_name != "Student" else "🎓"

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); border-radius: 14px; padding: 1.8rem; color: white; margin-bottom: 2rem; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.2);">
            <div style="display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap;">
                <div style="width: 64px; height: 64px; border-radius: 50%; background: rgba(255, 255, 255, 0.2); backdrop-filter: blur(8px); border: 2px solid rgba(255, 255, 255, 0.4); display: flex; align-items: center; justify-content: center; font-size: 1.9rem; font-weight: 700; color: white;">
                    {avatar_initial}
                </div>
                <div style="flex: 1; min-width: 240px;">
                    <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
                        <h2 style="margin: 0; color: white; font-weight: 700; font-size: 1.6rem;">{resolved_name}</h2>
                        <span style="background: rgba(255, 255, 255, 0.2); font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Active Student</span>
                    </div>
                    <p style="margin: 0.35rem 0 0 0; opacity: 0.95; font-size: 1.05rem; font-weight: 500;">
                        🏛️ <strong>{college_display}</strong>
                    </p>
                    <p style="margin: 0.2rem 0 0 0; opacity: 0.85; font-size: 0.9rem;">
                        🎓 {course_val} • {branch_val} • Semester {semester_val}
                    </p>
                </div>
            </div>
            <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; margin-top: 1.2rem; padding-top: 1rem; border-top: 1px solid rgba(255, 255, 255, 0.2); font-size: 0.9rem; opacity: 0.9;">
                <div>👤 <strong>Username:</strong> @{username_val}</div>
                <div>📧 <strong>Email:</strong> {email_val}</div>
                <div>🗓️ <strong>Current Term:</strong> Semester {semester_val}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # 2. PROFILE EDIT FORM
    # -------------------------------------------------------------------------
    st.subheader("✏️ Edit Academic Profile Details")
    st.caption("Update your full name, college name, or course details anytime. All changes synchronize across your dashboard and assistant sessions.")

    with st.form("profile_edit_form"):
        st.markdown("##### 1. Identity & Contact (Read Only)")
        col_id1, col_id2 = st.columns(2)
        with col_id1:
            st.text_input(
                "Username",
                value=username_val,
                disabled=True,
                help="Your unique student handle cannot be altered.",
            )
        with col_id2:
            st.text_input(
                "Email Address",
                value=email_val,
                disabled=True,
                help="Primary authentication email linked to your account.",
            )

        st.markdown("##### 2. Academic Information")
        full_name_input = st.text_input(
            "Full Name",
            value=resolved_name,
            placeholder="e.g. Rachel Greene",
            help="Enter your real full name as you would like it to appear on your dashboard.",
        )

        col_ac1, col_ac2 = st.columns(2)
        with col_ac1:
            college_input = st.text_input(
                "College / University",
                value=college_val,
                placeholder="e.g. State University of Technology",
                help="Enter your enrolled college or university name.",
            )
        with col_ac2:
            course_input = st.text_input(
                "Course / Degree",
                value=course_val,
                placeholder="e.g. B.Tech, B.Sc, BCA",
            )

        col_ac3, col_ac4 = st.columns(2)
        with col_ac3:
            branch_input = st.text_input(
                "Branch / Major",
                value=branch_val,
                placeholder="e.g. Computer Science, Mechanical",
            )
        with col_ac4:
            semester_input = st.text_input(
                "Current Semester / Year",
                value=semester_val,
                placeholder="e.g. 1, 2, 3...",
            )

        subjects_list = profile_data.get("subjects", [])
        subjects_str = ", ".join(subjects_list) if isinstance(subjects_list, list) else str(subjects_list)
        subjects_input = st.text_area(
            "Current Enrolled Subjects (comma-separated)",
            value=subjects_str,
            placeholder="e.g. Operating Systems, Computer Networks, Database Management Systems, Discrete Mathematics",
            help="These subjects are used to customize exam notes and study plan suggestions.",
        )

        submitted = st.form_submit_button("💾 Save Profile Changes", type="primary", use_container_width=True)

        if submitted:
            if not full_name_input.strip():
                st.error("Full name cannot be blank.")
                return
            if not course_input.strip():
                st.error("Course cannot be blank.")
                return
            if not branch_input.strip():
                st.error("Branch cannot be blank.")
                return

            clean_subjects = [s.strip() for s in subjects_input.split(",") if s.strip()]

            updates = {
                "full_name": full_name_input.strip(),
                "college": college_input.strip(),
                "course": course_input.strip(),
                "branch": branch_input.strip(),
                "semester": semester_input.strip(),
                "subjects": clean_subjects,
                "profile_completed": True,
            }

            try:
                updated_profile = db_service.update_profile(user_id, updates)
                st.session_state["user_profile"] = updated_profile.model_dump()
                st.success("🎉 Academic profile updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update profile: {sanitize_error_message(e)}")

