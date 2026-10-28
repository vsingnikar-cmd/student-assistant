"""Study Planner page: Personalized study timetable generation, workload validation, and plan saving."""

from datetime import date, timedelta
import streamlit as st
from services.study_plan_service import study_plan_service
from utils.errors import sanitize_error_message, ValidationError


def render_study_planner(user_id: str, profile_data: dict):
    """Renders the AI study planner generator and schedule viewer."""
    st.title("📅 Study Planner")
    st.caption("Generate a realistic day-by-day preparation schedule customized for your upcoming exams and available hours.")

    col1, col2 = st.columns(2)
    with col1:
        subjects_input = st.text_input(
            "Subjects (comma-separated)",
            placeholder="e.g. Operating Systems, Computer Networks, Software Engineering",
            help="List all subjects you need to prepare for",
        )
    with col2:
        default_exam_date = date.today() + timedelta(days=21)
        exam_date = st.date_input(
            "Target Examination Date",
            value=default_exam_date,
            min_value=date.today() + timedelta(days=1),
            help="When does your examination begin?",
        )

    col3, col4 = st.columns(2)
    with col3:
        daily_hours = st.slider(
            "Available Study Hours Per Day",
            min_value=1.0,
            max_value=12.0,
            value=4.0,
            step=0.5,
            help="Realistic hours you can consistently dedicate each day",
        )
    with col4:
        topics_priority = st.text_input(
            "High-Priority Topics / Difficult Areas (optional)",
            placeholder="e.g. Memory Management, Dynamic Programming, Subnetting",
            help="Topics you feel weakest in or have high exam weightage",
        )

    # Days remaining calculation
    days_left = (exam_date - date.today()).days
    total_capacity = days_left * daily_hours

    st.info(
        f"⏳ **Timeline Overview:** **{days_left} days** remaining until exam • "
        f"**{daily_hours} hrs/day** • Total estimated preparation capacity: **~{total_capacity:.1f} hours**."
    )

    if st.button("🗓️ Generate Personalized Study Plan", type="primary", use_container_width=True):
        raw_subjects = [s.strip() for s in subjects_input.split(",") if s.strip()]
        try:
            with st.spinner("Analyzing calendar, allocating subjects, and generating schedule..."):
                plan_result = study_plan_service.generate_plan(
                    subjects=raw_subjects,
                    exam_date=exam_date,
                    daily_hours=daily_hours,
                    topics=topics_priority.strip(),
                )

                st.session_state["active_study_plan"] = plan_result
                st.session_state["plan_saved_to_db"] = False

        except ValidationError as ve:
            st.error(ve.message)
        except Exception as e:
            st.error(f"Error creating study plan: {sanitize_error_message(e)}")

    # Display active plan
    if "active_study_plan" in st.session_state and st.session_state["active_study_plan"]:
        plan = st.session_state["active_study_plan"]
        st.write("---")
        st.subheader(f"📖 {plan['title']}")

        st.markdown(plan["plan_text"])

        # Save Plan Action
        save_col1, save_col2 = st.columns([1, 1])
        with save_col1:
            if not st.session_state.get("plan_saved_to_db", False):
                if st.button("💾 Save Plan to Learning History", type="primary", use_container_width=True):
                    try:
                        study_plan_service.save_plan(
                            user_id=user_id,
                            title=plan["title"],
                            exam_date=plan["exam_date"],
                            daily_hours=plan["daily_hours"],
                            subjects=plan["subjects"],
                            plan_text=plan["plan_text"],
                        )
                        st.session_state["plan_saved_to_db"] = True
                        st.success("Study plan successfully saved to your Learning History!")
                    except Exception as e:
                        st.error(f"Failed to save plan: {sanitize_error_message(e)}")
            else:
                st.success("✅ This plan is saved in your Learning History.")

        with save_col2:
            st.download_button(
                label="📥 Export Schedule as Markdown",
                data=plan["plan_text"],
                file_name=f"{plan['title'].replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
