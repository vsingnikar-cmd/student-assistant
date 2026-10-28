"""Academic Chatbot page: Multi-turn academic tutor with conversation persistence."""

import streamlit as st
from services.gemini_service import gemini_service
from services.database_service import db_service
from utils.errors import sanitize_error_message


def render_academic_chat(user_id: str, profile_data: dict):
    """Renders the conversational academic tutor."""
    st.title("💬 Academic Chatbot")
    st.caption("Ask questions, explore complex engineering & academic theories, and get step-by-step guidance.")

    # Initialize active conversation ID in session state if not present
    if "active_conv_id" not in st.session_state:
        try:
            st.session_state["active_conv_id"] = db_service.get_or_create_conversation(user_id)
        except Exception:
            st.session_state["active_conv_id"] = "temp-local-session"

    conv_id = st.session_state["active_conv_id"]

    # Action bar for new discussion / clear
    top_col1, top_col2 = st.columns([3, 1])
    with top_col2:
        if st.button("➕ New Topic", use_container_width=True, help="Start a clean conversation thread"):
            try:
                new_id = db_service.create_new_conversation(user_id, title="New Academic Discussion")
                st.session_state["active_conv_id"] = new_id
                st.session_state["chat_messages_cache"] = []
                st.rerun()
            except Exception as e:
                st.error(sanitize_error_message(e))

    # Load messages from cache or database
    if "chat_messages_cache" not in st.session_state:
        try:
            st.session_state["chat_messages_cache"] = db_service.get_recent_messages(user_id, conv_id)
        except Exception:
            st.session_state["chat_messages_cache"] = []

    messages = st.session_state["chat_messages_cache"]

    # Display empty state with quick starter chips if conversation is empty
    if not messages:
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 2rem; text-align: center; margin: 1.5rem 0;">
                <h3 style="color: #334155; margin-bottom: 0.5rem;">How can I help with your studies today?</h3>
                <p style="color: #64748b; font-size: 0.95rem;">You can ask for derivations, conceptual breakdowns, code explanations, or intuitive analogies.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("**Try asking:**")
        chip_col1, chip_col2, chip_col3 = st.columns(3)
        with chip_col1:
            if st.button("Explain Dijkstra's Algorithm step-by-step", use_container_width=True):
                st.session_state["pending_chat_prompt"] = "Explain Dijkstra's Shortest Path Algorithm step-by-step with an example."
                st.rerun()
        with chip_col2:
            if st.button("Derive Fourier Transform properties", use_container_width=True):
                st.session_state["pending_chat_prompt"] = "Explain the key mathematical properties of the Continuous Fourier Transform with equations."
                st.rerun()
        with chip_col3:
            if st.button("Explain ACID properties in Databases", use_container_width=True):
                st.session_state["pending_chat_prompt"] = "Explain ACID properties in database transactions with concrete banking examples."
                st.rerun()

    # Render message history
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.markdown(content)

    # Check for pending prompt from starter chips
    auto_prompt = st.session_state.pop("pending_chat_prompt", None)
    user_input = st.chat_input("Ask an academic or technical question...") or auto_prompt

    if user_input:
        cleaned_input = user_input.strip()
        if not cleaned_input:
            st.warning("Please type a question before sending.")
            return

        # Display user question
        with st.chat_message("user"):
            st.markdown(cleaned_input)

        # Append to local cache
        messages.append({"role": "user", "content": cleaned_input})
        st.session_state["chat_messages_cache"] = messages

        # Persist user question to Supabase
        try:
            db_service.save_chat_message(user_id, conv_id, "user", cleaned_input)
        except Exception as e:
            st.warning(f"Note: Could not save message to database: {sanitize_error_message(e)}")

        # Generate Gemini AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing concept and structuring response..."):
                try:
                    response_text = gemini_service.generate_chat_response(
                        question=cleaned_input,
                        history=messages[:-1],  # Context history
                        student_profile=profile_data,
                    )
                    st.markdown(response_text)
                    messages.append({"role": "assistant", "content": response_text})
                    st.session_state["chat_messages_cache"] = messages

                    # Persist assistant response
                    db_service.save_chat_message(user_id, conv_id, "assistant", response_text)
                except Exception as e:
                    err_msg = sanitize_error_message(e)
                    st.error(f"Error: {err_msg}")
