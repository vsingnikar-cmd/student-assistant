# 🎓 AI Student Assistant Agent

A modern, production-oriented educational SaaS web application designed for college and university students. The application centralizes academic concept explanations, textbook and syllabus PDF question-answering with exact page citations, exam-tailored 2-, 5-, and 10-mark notes generation, automated MCQ quiz practice with deterministic scoring, and personalized day-by-day exam study planning.

Built with **Streamlit**, **Google Gemini AI**, and **Supabase (PostgreSQL with Row Level Security)**.

---

## 🌟 Key Features

1. **🔐 Secure Authentication & Academic Profiles**
   - Email/password and username/password login.
   - Secure server-side username resolution without exposing emails to public enumeration.
   - Comprehensive student profile (Course, Department, Semester, College, Enrolled Subjects).
   - Strict per-user Row Level Security (RLS) ensuring complete data isolation.

2. **💬 Academic Chatbot**
   - Context-aware academic assistant personalized to the student's degree and semester.
   - Multi-turn conversation support with token-bounded context history.
   - Derivations with LaTeX equations, structured definitions, and intuitive analogies.
   - Persistent chat conversations stored in Supabase.

3. **📄 PDF Assistant (Document-Grounded Q&A)**
   - Page-aware PDF text extraction and validation.
   - Automatic detection of empty, encrypted, or scanned documents without selectable text.
   - Overlapping text chunking preserving original page number boundaries.
   - Fast lexical / BM25 token retrieval to isolate evidence chunks.
   - Verifiable `[Page X]` citations; explicitly indicates when evidence is missing to prevent AI hallucinations.
   - Inspection panel allowing students to view the exact document excerpts used as evidence.

4. **📝 Exam Notes Generator**
   - **2-mark answers**: Crisp definition and 1-2 core high-yield points (40-70 words).
   - **5-mark answers**: Definition, key points, conceptual explanation, and illustrative example (150-250 words).
   - **10-mark answers**: Detailed breakdown with headings, core architecture, formulas, real-world case study, advantages/limitations, and conclusion (400-600 words).
   - One-click export to Markdown (`.md`).

5. **🎯 MCQ Quiz Generator & Evaluator**
   - Generates 3 to 15 questions across Easy, Medium, and Hard difficulty levels.
   - Strict Pydantic schema validation rejecting duplicate choices or malformed structures.
   - Deterministic scoring executed in application logic (not trusted to LLM evaluation).
   - Immediate feedback showing score percentage, correct/incorrect/unanswered tallies, and in-depth explanations.
   - Automatic persistence to `quiz_attempts` table.

6. **📅 Study Planner**
   - Computes remaining days until examination and total available study capacity.
   - Rejects past dates and unrealistic study workloads.
   - Generates day-by-day milestones covering core learning, problem-solving, and revision.
   - Persistent study schedules saved to the student's profile.

7. **📜 Learning History & Analytics**
   - Centralized dashboard displaying total chat interactions, quiz attempts, average scores, and saved plans.
   - History logs allowing students to review past quiz attempts, re-read schedules, and manage uploaded documents.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Frontend** | Streamlit | Responsive SaaS web application interface with custom CSS design tokens |
| **Backend & Logic** | Python 3.11+ / 3.14 | Typed service layer, Pydantic schemas, and robust validation |
| **AI Engine** | Google Gemini API | Official `google-genai` SDK with configurable models (`gemini-2.5-flash`) |
| **Database & Auth** | Supabase | PostgreSQL with Row Level Security (RLS), Supabase Auth, and Edge Functions |
| **PDF Processing** | PyMuPDF / pypdf | Resilient page-by-page text extraction, chunking, and lexical search |
| **Testing** | Pytest | Automated test suite covering validation, scoring, PDF, and planning |

---

## 📂 Project Structure

```text
student assistant/
├── app.py                      # Main Streamlit application and auth router
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment configuration
├── .gitignore                  # Git exclusions for secrets, venv, and cache
├── README.md                   # Complete documentation
├── schema.sql                  # Supabase PostgreSQL schema with RLS policies
├── supabase/
│   └── functions/
│       └── username-login/
│           └── index.ts        # Secure Edge Function for username authentication
├── pages/
│   ├── dashboard.py            # Student dashboard and metrics
│   ├── academic_chat.py        # Conversational academic chatbot
│   ├── pdf_assistant.py        # PDF upload, chunking, and grounded Q&A
│   ├── exam_notes.py           # 2-, 5-, and 10-mark notes generator
│   ├── quiz_generator.py       # MCQ test generator and score evaluator
│   ├── study_planner.py        # Exam schedule generator and saver
│   ├── learning_history.py     # Past quizzes, study plans, and documents
│   └── profile.py              # Academic profile management
├── services/
│   ├── auth_service.py         # Supabase Auth and session management
│   ├── database_service.py     # Database queries and persistence
│   ├── gemini_service.py       # Google Gemini LLM API integration
│   ├── pdf_service.py          # PDF text extraction and chunk retrieval
│   ├── quiz_service.py         # Deterministic quiz scoring
│   └── study_plan_service.py   # Study plan generation and calculation
├── models/
│   ├── schemas.py              # Pydantic schemas for profiles, chat, plans
│   └── quiz_models.py          # Strict Pydantic models for quiz generation
├── utils/
│   ├── config.py               # Environment variables and configuration
│   ├── errors.py               # Custom exceptions and error sanitization
│   └── validators.py           # Form, date, and parameter validators
└── tests/
    ├── test_validators.py      # Tests for validation logic
    ├── test_quiz_service.py    # Tests for quiz schemas and deterministic scoring
    ├── test_pdf_service.py     # Tests for PDF extraction, chunking, and retrieval
    └── test_study_plan.py      # Tests for study plan capacity and date logic
```

---

## 🚀 Quickstart & Installation

### 1. Clone or Open Workspace
Ensure you are in the project root:
```bash
cd "student assistant"
```

### 2. Create and Activate Virtual Environment (Recommended)
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and fill in your credentials:
```env
# Gemini API Key from Google AI Studio: https://aistudio.google.com/
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL="gemini-2.5-flash"

# Supabase Project URL & Anon Key from Project Settings -> API
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="eyJhbGciOi..."

# Optional: Service Role Key (for server-side username resolution if Edge Function is not used)
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOi..."
```

---

## 🗄️ Database Setup (Supabase)

1. Open your **Supabase Dashboard** and navigate to the **SQL Editor**.
2. Open the file [`schema.sql`](file:///c:/Users/vaibh/OneDrive/Desktop/student%20assistant/schema.sql) from this project.
3. Paste the contents into the Supabase SQL Editor and click **Run**.
4. This will create:
   - Tables: `profiles`, `conversations`, `chat_messages`, `documents`, `document_chunks`, `quiz_attempts`, `study_plans`.
   - Indexes on frequently queried columns (`user_id`, `created_at`, `username`).
   - Case-insensitive unique index on `LOWER(username)`.
   - Complete **Row Level Security (RLS)** policies ensuring students only ever read, write, or delete their own data (`auth.uid() = user_id`).
   - Automated timestamp trigger `update_modtime`.

### Deploying the Username-Login Edge Function (Optional)
If using Supabase CLI to host the username login edge function:
```bash
supabase functions deploy username-login --no-verify-jwt
```

---

## 🧪 Running Automated Tests

Run the full pytest suite covering validation, deterministic scoring, PDF parsing, and study planner logic:
```bash
pytest tests -v
```

All 20 test cases will execute and verify the integrity of the application.

---

## 💻 Running the Application

Launch the Streamlit web application:
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

*Note: For testing and review purposes, the login screen also includes a **"🚀 Explore in Demo / Sandbox Mode"** button that lets you instantly test the full UI, dashboard, quiz taking, and study planning.*

---

## 🔒 Security Best Practices

- **Zero Secret Leakage**: API keys and database credentials are strictly read from environment variables and never logged or exposed in client responses.
- **Data Isolation**: Row Level Security (RLS) is enforced on all tables. A student can never query or manipulate another student's documents, chats, or scores.
- **Anti-Enumeration**: Username and password login returns identical, generic error messages on failure, preventing malicious users from discovering registered usernames or emails.
- **Input Sanitization**: All file uploads are validated by content size and extension, preventing oversized uploads and denial-of-service risks.

---

## 📄 License
MIT License. Built for students and academic institutions.
