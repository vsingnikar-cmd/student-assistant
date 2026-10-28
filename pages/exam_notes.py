"""Exam Notes Generator page: Creates structured 2-mark, 5-mark, and 10-mark academic notes."""

import streamlit as st
from services.gemini_service import gemini_service
from utils.validators import validate_exam_notes_input
from utils.errors import sanitize_error_message, ValidationError


def render_exam_notes(user_id: str, profile_data: dict):
    """Renders the Exam Notes generation interface."""
    st.title("📝 Exam Notes Generator")
    st.caption("Generate high-yield, structured exam answers designed specifically for university 2-mark, 5-mark, and 10-mark questions.")

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        subject = st.text_input(
            "Subject Name",
            placeholder="e.g. Operating Systems, Thermodynamics, Database Management",
            help="The course or subject title",
        )
    with col_in2:
        topic = st.text_input(
            "Topic / Question",
            placeholder="e.g. Paging vs Segmentation, Normalization, Carnot Cycle",
            help="Specific topic, question, or concept to generate notes for",
        )

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        marks = st.radio(
            "Target Question Marks",
            options=[2, 5, 10],
            format_func=lambda m: f"{m} Marks ({'Short Definition' if m == 2 else ('Medium Conceptual' if m == 5 else 'Comprehensive Long Answer')})",
            horizontal=True,
            index=1,
        )
    with col_opt2:
        difficulty = st.selectbox(
            "Academic Depth",
            options=["Beginner / Introductory", "Intermediate / Undergraduate", "Advanced / Technical"],
            index=1,
        )

    additional_context = st.text_area(
        "Optional Syllabus Constraints / Specific Focus",
        placeholder="e.g. Focus on 3NF and BCNF with anomalies table, or include standard circuit diagram description.",
        height=70,
    )

    if st.button("🚀 Generate Exam Notes", type="primary", use_container_width=True):
        try:
            clean_sub, clean_top, clean_marks = validate_exam_notes_input(subject, topic, marks)

            with st.spinner(f"Structuring {clean_marks}-mark examination answer for '{clean_top}'..."):
                notes = gemini_service.generate_exam_notes(
                    subject=clean_sub,
                    topic=clean_top,
                    marks=clean_marks,
                    difficulty=difficulty,
                    additional_context=additional_context.strip() if additional_context else None,
                )

                st.session_state["generated_notes"] = notes
                st.session_state["notes_subject"] = clean_sub
                st.session_state["notes_topic"] = clean_top
                st.session_state["notes_marks"] = clean_marks

        except ValidationError as ve:
            st.error(ve.message)
        except Exception as e:
            st.error(f"Error generating notes: {sanitize_error_message(e)}")

    # Display generated notes
    if "generated_notes" in st.session_state:
        st.write("---")
        st.subheader(f"📖 {st.session_state['notes_subject']} - {st.session_state['notes_topic']} ({st.session_state['notes_marks']} Marks)")

        notes_content = st.session_state["generated_notes"]
        st.markdown(notes_content)

        # Download / Export Button
        filename = f"{st.session_state['notes_subject']}_{st.session_state['notes_topic']}_{st.session_state['notes_marks']}marks.md".replace(" ", "_")
        st.download_button(
            label="💾 Download Notes as Markdown (.md)",
            data=notes_content,
            file_name=filename,
            mime="text/markdown",
            use_container_width=True,
        )
