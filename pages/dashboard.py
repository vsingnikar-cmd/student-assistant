"""Dashboard view: Displays student welcome, stats, recent activities, and quick actions."""

import streamlit as st
from services.database_service import db_service
from models.schemas import resolve_student_name
from utils.config import config


def render_dashboard(user_id: str, profile_data: dict):
    """Renders the student dashboard with dynamic personalized welcome header."""
    user_email_session = st.session_state.get("user_email", "")
    full_name = resolve_student_name(
        profile=profile_data,
        email=user_email_session,
        username=profile_data.get("username", "") if profile_data else "",
    )
    course = profile_data.get("course") or "Engineering"
    branch = profile_data.get("branch") or "Computer Science"
    semester = str(profile_data.get("semester") or "1")
    college = profile_data.get("college") or ""

    college_text = f" • 🏛️ {college}" if college else ""

    # Header Card
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 1.8rem; border-radius: 12px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.2);">
            <h2 style="margin: 0; color: white; font-weight: 700; font-size: 1.6rem;">Welcome back, {full_name}! 👋</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.95; font-size: 1.05rem;">
                {course} • {branch} • Semester {semester}{college_text}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch real persisted metrics
    metrics = db_service.get_dashboard_metrics(user_id)

    # Metric Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="💬 Chat Interactions",
            value=metrics["total_messages"],
            help="Total academic questions and discussions saved.",
        )
    with col2:
        st.metric(
            label="🎯 Quizzes Attempted",
            value=metrics["total_quizzes"],
            help="Total multiple-choice quizzes completed.",
        )
    with col3:
        st.metric(
            label="📈 Average Quiz Score",
            value=f"{metrics['avg_quiz_score']}%",
            help="Overall performance across all attempted quizzes.",
        )
    with col4:
        st.metric(
            label="📅 Study Plans",
            value=metrics["total_plans"],
            help="Personalized study plans created and saved.",
        )

    st.write("---")

    # Quick Actions
    st.subheader("⚡ Quick Study Actions")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    with qcol1:
        if st.button("💬 Ask Tutor", use_container_width=True, help="Ask questions about any academic concept"):
            st.session_state["current_page"] = "Academic Chat"
            st.rerun()
    with qcol2:
        if st.button("📄 Query PDF", use_container_width=True, help="Upload and study from textbooks and notes"):
            st.session_state["current_page"] = "PDF Assistant"
            st.rerun()
    with qcol3:
        if st.button("📝 Exam Notes", use_container_width=True, help="Generate structured 2, 5, or 10-mark answers"):
            st.session_state["current_page"] = "Exam Notes"
            st.rerun()
    with qcol4:
        if st.button("🎯 Practice Quiz", use_container_width=True, help="Test your knowledge with MCQs"):
            st.session_state["current_page"] = "Quiz Generator"
            st.rerun()

    st.write("---")

    # Recent Activity Row
    rec_col1, rec_col2 = st.columns(2)

    with rec_col1:
        st.subheader("📊 Recent Quiz Attempts")
        recent_quizzes = db_service.list_quiz_attempts(user_id, limit=5)
        if not recent_quizzes:
            st.info("No quizzes taken yet. Test your understanding with the **Quiz Generator**!")
        else:
            for q in recent_quizzes:
                score_badge = "🟢" if float(q.get("percentage", 0)) >= 70 else ("🟡" if float(q.get("percentage", 0)) >= 50 else "🔴")
                st.markdown(
                    f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.9rem; margin-bottom: 0.6rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong>{q.get('subject')} - {q.get('topic')}</strong>
                            <span>{score_badge} <strong>{q.get('score')}/{q.get('total')} ({q.get('percentage')}%)</strong></span>
                        </div>
                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.3rem;">
                            Difficulty: {q.get('difficulty')} • {str(q.get('created_at', ''))[:10]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with rec_col2:
        st.subheader("📅 Recent Study Plans")
        recent_plans = db_service.list_study_plans(user_id, limit=5)
        if not recent_plans:
            st.info("No study plans created yet. Plan your semester exams with the **Study Planner**!")
        else:
            for p in recent_plans:
                st.markdown(
                    f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.9rem; margin-bottom: 0.6rem;">
                        <div style="font-weight: 600; color: #1e293b;">{p.get('title')}</div>
                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.3rem;">
                            Target Exam: {p.get('exam_date')} • Daily: {p.get('daily_hours')} hrs
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
