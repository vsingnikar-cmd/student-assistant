"""Quiz Generator page: AI multiple-choice question generation, interactive test taking, and deterministic scoring."""

import streamlit as st
from services.quiz_service import quiz_service
from utils.validators import validate_quiz_input
from utils.errors import sanitize_error_message, ValidationError


def render_quiz_generator(user_id: str, profile_data: dict):
    """Renders the quiz creation and interactive assessment view."""
    st.title("🎯 MCQ Quiz Generator")
    st.caption("Generate subject-specific multiple-choice tests, test your comprehension, and receive instant explanations.")

    # 1. QUIZ CREATION FORM
    with st.expander("⚙️ Configure New Quiz", expanded=("active_quiz" not in st.session_state)):
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            subject = st.text_input("Subject", placeholder="e.g. Data Structures, Digital Electronics")
        with col_q2:
            topic = st.text_input("Topic", placeholder="e.g. AVL Trees, Karnaugh Maps, SQL Joins")

        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            num_questions = st.slider("Number of Questions", min_value=3, max_value=15, value=5)
        with col_cfg2:
            difficulty = st.selectbox("Difficulty Level", options=["Easy", "Medium", "Hard"], index=1)

        if st.button("✨ Generate Quiz", type="primary", use_container_width=True):
            try:
                clean_sub, clean_top, clean_cnt, clean_diff = validate_quiz_input(
                    subject, topic, num_questions, difficulty
                )

                with st.spinner(f"Generating {clean_cnt} {clean_diff}-level MCQs on '{clean_top}'..."):
                    quiz_obj = quiz_service.create_quiz(
                        subject=clean_sub,
                        topic=clean_top,
                        num_questions=clean_cnt,
                        difficulty=clean_diff,
                    )

                    # Store in session state
                    st.session_state["active_quiz"] = quiz_obj
                    st.session_state["quiz_user_answers"] = {}
                    st.session_state["quiz_submitted"] = False
                    st.session_state["quiz_result"] = None
                    st.rerun()

            except ValidationError as ve:
                st.error(ve.message)
            except Exception as e:
                st.error(f"Error creating quiz: {sanitize_error_message(e)}")

    # 2. ACTIVE QUIZ INTERACTION
    if "active_quiz" in st.session_state and st.session_state["active_quiz"]:
        quiz = st.session_state["active_quiz"]
        st.write("---")
        st.subheader(f"📝 Quiz: {quiz.subject} - {quiz.topic} ({quiz.difficulty} Level)")

        # Render questions
        user_answers = st.session_state.get("quiz_user_answers", {})
        is_submitted = st.session_state.get("quiz_submitted", False)

        for idx, q in enumerate(quiz.questions):
            st.markdown(f"**Question {idx + 1} of {len(quiz.questions)}:**")
            st.markdown(f"##### {q.question}")

            # Format options with letter prefixes
            option_labels = [f"**{chr(65 + i)}.** {opt}" for i, opt in enumerate(q.options)]

            if not is_submitted:
                # Unanswered by default: index=None
                current_val = user_answers.get(idx)
                selected_label = st.radio(
                    f"Choose answer for Question {idx + 1}:",
                    options=option_labels,
                    index=current_val if current_val is not None else None,
                    key=f"quiz_opt_{idx}",
                    label_visibility="collapsed",
                )
                if selected_label is not None:
                    # Find index
                    selected_idx = option_labels.index(selected_label)
                    user_answers[idx] = selected_idx
                else:
                    user_answers[idx] = None
            else:
                # Display static after submission with color highlights
                result_detail = st.session_state["quiz_result"].questions_detail[idx]
                for i, opt in enumerate(q.options):
                    is_correct_opt = (i == q.correct_index)
                    is_user_choice = (i == result_detail.user_answer_index)

                    if is_correct_opt:
                        st.success(f"✅ **{chr(65 + i)}.** {opt} *(Correct Answer)*")
                    elif is_user_choice and not is_correct_opt:
                        st.error(f"❌ **{chr(65 + i)}.** {opt} *(Your Answer)*")
                    else:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**{chr(65 + i)}.** {opt}")

                # Show explanation
                with st.expander("💡 View Detailed Explanation"):
                    st.info(q.explanation)

            st.write("")

        st.session_state["quiz_user_answers"] = user_answers

        # Submit button
        if not is_submitted:
            if st.button("🏁 Submit Quiz for Evaluation", type="primary", use_container_width=True):
                with st.spinner("Calculating score and saving result..."):
                    result = quiz_service.evaluate_quiz(
                        quiz=quiz,
                        user_responses=user_answers,
                        user_id=user_id,
                        persist=True,
                    )
                    st.session_state["quiz_submitted"] = True
                    st.session_state["quiz_result"] = result
                    st.rerun()

        # 3. RESULT CARD
        if is_submitted and st.session_state.get("quiz_result"):
            res = st.session_state["quiz_result"]
            st.write("---")
            st.markdown(
                f"""
                <div style="background: #f8fafc; border: 2px solid {'#22c55e' if res.percentage >= 60 else '#ef4444'}; border-radius: 12px; padding: 1.5rem; margin-top: 1rem; text-align: center;">
                    <h2 style="margin: 0; color: #1e293b;">Quiz Results</h2>
                    <h1 style="font-size: 3rem; margin: 0.5rem 0; color: {'#16a34a' if res.percentage >= 60 else '#dc2626'};">
                        {res.score} / {res.total}
                    </h1>
                    <p style="font-size: 1.2rem; font-weight: 600; color: #475569; margin: 0;">
                        Score: {res.percentage}%
                    </p>
                    <p style="color: #64748b; font-size: 0.95rem; margin-top: 0.4rem;">
                        ✅ Correct: <strong>{res.correct_count}</strong> • 
                        ❌ Incorrect: <strong>{res.incorrect_count}</strong> • 
                        ⚪ Unanswered: <strong>{res.unanswered_count}</strong>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("🔄 Retake or Start Another Quiz", use_container_width=True):
                del st.session_state["active_quiz"]
                del st.session_state["quiz_user_answers"]
                del st.session_state["quiz_submitted"]
                del st.session_state["quiz_result"]
                st.rerun()
