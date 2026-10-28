"""PDF Assistant page: Document upload, page-aware chunking, lexical retrieval, and grounded Q&A."""

import streamlit as st
from services.pdf_service import pdf_service
from services.gemini_service import gemini_service
from services.database_service import db_service
from utils.validators import validate_pdf_upload
from utils.errors import sanitize_error_message, PDFProcessingError
from utils.config import config


def render_pdf_assistant(user_id: str, profile_data: dict):
    """Renders the PDF document Q&A assistant."""
    st.title("📄 PDF Assistant")
    st.caption("Upload academic textbooks, lecture slides, or syllabus notes to ask grounded questions with exact page citations.")

    tab1, tab2 = st.tabs(["📤 Upload & Query New PDF", "📚 My Processed Documents"])

    # -------------------------------------------------------------------------
    # TAB 1: UPLOAD & QUERY
    # -------------------------------------------------------------------------
    with tab1:
        uploaded_file = st.file_uploader(
            "Select an academic PDF file",
            type=["pdf"],
            help=f"Max size: {config.MAX_UPLOAD_SIZE_MB} MB. Text-based PDFs only.",
        )

        if uploaded_file is not None:
            # Check if this file was already processed in this session
            current_file_key = f"pdf_processed_{uploaded_file.name}_{uploaded_file.size}"

            if st.session_state.get("active_pdf_key") != current_file_key:
                with st.spinner("Extracting pages and building document chunks..."):
                    try:
                        file_bytes = uploaded_file.read()
                        validate_pdf_upload(file_bytes, uploaded_file.name, max_size_mb=config.MAX_UPLOAD_SIZE_MB)

                        # Extract text page by page
                        pages_data = pdf_service.extract_text_by_pages(file_bytes, uploaded_file.name)
                        total_pages = len(pages_data)
                        total_chars = sum(len(p["text"]) for p in pages_data)

                        # Chunk document
                        chunks = pdf_service.chunk_document(pages_data)

                        # Save to database
                        try:
                            doc_id = db_service.save_document(
                                user_id=user_id,
                                filename=uploaded_file.name,
                                page_count=total_pages,
                                extracted_characters=total_chars,
                                chunks=chunks,
                            )
                        except Exception:
                            doc_id = "local-session-doc"

                        # Cache in session state
                        st.session_state["active_pdf_key"] = current_file_key
                        st.session_state["active_pdf_id"] = doc_id
                        st.session_state["active_pdf_name"] = uploaded_file.name
                        st.session_state["active_pdf_pages"] = total_pages
                        st.session_state["active_pdf_chars"] = total_chars
                        st.session_state["active_pdf_chunks"] = chunks
                        st.session_state["pdf_qa_history"] = []

                        st.success(f"Successfully processed **{uploaded_file.name}** ({total_pages} pages, {len(chunks)} searchable chunks).")
                    except PDFProcessingError as pe:
                        st.error(pe.message)
                        return
                    except Exception as e:
                        st.error(f"Error processing document: {sanitize_error_message(e)}")
                        return

            # Document is loaded and ready for questions
            st.markdown(
                f"""
                <div style="background: #f1f5f9; border-left: 4px solid #3b82f6; padding: 0.8rem 1.2rem; border-radius: 4px; margin-bottom: 1rem;">
                    <strong>Active Document:</strong> {st.session_state.get('active_pdf_name')} 
                    • <strong>Pages:</strong> {st.session_state.get('active_pdf_pages')} 
                    • <strong>Chunks:</strong> {len(st.session_state.get('active_pdf_chunks', []))}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Question Input
            question = st.text_input(
                "Ask a question grounded in this document:",
                placeholder="e.g. What are the 4 conditions for deadlock discussed in chapter 3?",
            )

            if st.button("🔍 Search Document & Answer", type="primary") and question:
                with st.spinner("Retrieving relevant page chunks and formulating answer..."):
                    try:
                        chunks = st.session_state.get("active_pdf_chunks", [])
                        relevant_chunks = pdf_service.retrieve_relevant_chunks(question, chunks, top_k=4)

                        answer = gemini_service.answer_from_pdf_context(
                            question=question,
                            retrieved_chunks=relevant_chunks,
                            filename=st.session_state.get("active_pdf_name", "document.pdf"),
                        )

                        # Display Answer
                        st.subheader("📝 Grounded Answer")
                        st.markdown(answer)

                        # Expandable source snippets
                        if relevant_chunks:
                            with st.expander("🔎 View Source Document Excerpts & Evidence"):
                                for idx, rc in enumerate(relevant_chunks, 1):
                                    p_num = rc.get("page_start", 1)
                                    st.markdown(f"**Excerpt {idx} (Page {p_num})**")
                                    st.code(rc.get("chunk_text", "").strip(), language="markdown")

                    except Exception as e:
                        st.error(f"Error answering question: {sanitize_error_message(e)}")

    # -------------------------------------------------------------------------
    # TAB 2: MY PROCESSED DOCUMENTS
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("📚 Previously Uploaded Documents")
        docs = db_service.list_documents(user_id)

        if not docs:
            st.info("No documents uploaded yet. Upload a PDF in the first tab to begin.")
        else:
            for doc in docs:
                col_d1, col_d2, col_d3 = st.columns([3, 1, 1])
                with col_d1:
                    st.markdown(f"**{doc.get('filename')}**")
                    st.caption(f"{doc.get('page_count')} pages • {doc.get('extracted_characters')} chars • Uploaded on {str(doc.get('created_at'))[:10]}")
                with col_d2:
                    if st.button("Load", key=f"load_doc_{doc['id']}", use_container_width=True):
                        with st.spinner("Loading document chunks..."):
                            chunks = db_service.get_document_chunks(user_id, doc["id"])
                            st.session_state["active_pdf_key"] = f"loaded_{doc['id']}"
                            st.session_state["active_pdf_id"] = doc["id"]
                            st.session_state["active_pdf_name"] = doc["filename"]
                            st.session_state["active_pdf_pages"] = doc["page_count"]
                            st.session_state["active_pdf_chars"] = doc["extracted_characters"]
                            st.session_state["active_pdf_chunks"] = chunks
                            st.session_state["pdf_qa_history"] = []
                            st.success(f"Loaded '{doc['filename']}'! Switch to the 'Upload & Query' tab to ask questions.")
                with col_d3:
                    if st.button("🗑️ Delete", key=f"del_doc_{doc['id']}", use_container_width=True):
                        try:
                            db_service.delete_document(user_id, doc["id"])
                            st.success(f"Deleted '{doc['filename']}'.")
                            st.rerun()
                        except Exception as e:
                            st.error(sanitize_error_message(e))
                st.write("---")
