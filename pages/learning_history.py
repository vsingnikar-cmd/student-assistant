"""Learning History page: Unified view of past quiz attempts, saved study schedules, and uploaded documents."""

import streamlit as st
from services.database_service import db_service
from utils.errors import sanitize_error_message


def render_learning_history(user_id: str, profile_data: dict):
    """Renders the student learning record history."""
    st.title("📜 Learning History")
    st.caption("Review your previous quizzes, saved study schedules, and uploaded study materials.")

    tab_quizzes, tab_plans, tab_docs = st.tabs(["🎯 Quiz Attempts", "📅 Saved Study Plans", "📄 Uploaded PDFs"])

    # -------------------------------------------------------------------------
    # TAB 1: QUIZ ATTEMPTS
    # -------------------------------------------------------------------------
    with tab_quizzes:
        st.subheader("Quiz Performance History")
        attempts = db_service.list_quiz_attempts(user_id, limit=30)

        if not attempts:
            st.info("You haven't completed any quizzes yet. Head to the **Quiz Generator** to test your knowledge!")
        else:
            for at in attempts:
                pct = float(at.get("percentage", 0))
                badge = "🟢 Passed" if pct >= 60 else "🔴 Needs Review"
                
                with st.expander(
                    f"{at.get('subject')} - {at.get('topic')} ({at.get('score')}/{at.get('total')} - {pct}%) • {badge}"
                ):
                    st.markdown(f"**Date:** {str(at.get('created_at'))[:19]}")
                    st.markdown(f"**Difficulty:** {at.get('difficulty')}")
                    st.markdown(f"**Score:** {at.get('score')} out of {at.get('total')} questions ({pct}%)")

                    # Answers review
                    answers = at.get("answers", [])
                    if answers:
                        st.write("---")
                        st.markdown("**Question Review:**")
                        for i, ans in enumerate(answers, 1):
                            is_corr = ans.get("is_correct", False)
                            is_unans = ans.get("is_unanswered", False)
                            status_icon = "⚪ Unanswered" if is_unans else ("✅ Correct" if is_corr else "❌ Incorrect")
                            st.markdown(f"**Q{i}: {ans.get('question')}** — *{status_icon}*")
                            if ans.get("explanation"):
                                st.caption(f"Explanation: {ans.get('explanation')}")

    # -------------------------------------------------------------------------
    # TAB 2: SAVED STUDY PLANS
    # -------------------------------------------------------------------------
    with tab_plans:
        st.subheader("Saved Study Plans")
        plans = db_service.list_study_plans(user_id, limit=20)

        if not plans:
            st.info("No saved study plans found. Generate and save a plan in the **Study Planner**!")
        else:
            for p in plans:
                with st.expander(f"{p.get('title')} (Exam: {p.get('exam_date')})"):
                    st.markdown(f"**Target Exam Date:** {p.get('exam_date')}")
                    st.markdown(f"**Daily Study Allocation:** {p.get('daily_hours')} hours/day")
                    st.markdown(f"**Subjects:** {', '.join(p.get('subjects', []))}")
                    st.write("---")
                    st.markdown(p.get("plan_text", ""))

                    del_col, exp_col = st.columns([1, 4])
                    with del_col:
                        if st.button("🗑️ Delete Plan", key=f"del_plan_{p['id']}"):
                            try:
                                db_service.delete_study_plan(user_id, p["id"])
                                st.success("Plan deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(sanitize_error_message(e))

    # -------------------------------------------------------------------------
    # TAB 3: UPLOADED PDFS
    # -------------------------------------------------------------------------
    with tab_docs:
        st.subheader("Processed Study Documents")
        docs = db_service.list_documents(user_id)

        if not docs:
            st.info("No documents uploaded yet.")
        else:
            for doc in docs:
                st.markdown(
                    f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem;">
                        <h4 style="margin: 0; color: #1e293b;">📄 {doc.get('filename')}</h4>
                        <div style="color: #64748b; font-size: 0.9rem; margin-top: 0.3rem;">
                            Pages: <strong>{doc.get('page_count')}</strong> • 
                            Extracted Characters: <strong>{doc.get('extracted_characters')}</strong> • 
                            Processed: <strong>{str(doc.get('created_at'))[:10]}</strong>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
