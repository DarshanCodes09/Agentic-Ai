# AI-Driven Intelligent Academic Assessment and Performance Analytics System

## Phase 1–6 — Backend + Web Portal

A FastAPI + PostgreSQL backend with JWT authentication, role-based access control (RBAC), AI-assisted assessment, analytics, and a React web portal for students and faculty.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.142 |
| Database | PostgreSQL + SQLAlchemy 2.x |
| Migrations | Alembic 1.20 |
| Auth | JWT (python-jose) + bcrypt |
| Validation | Pydantic v2 |
| Config | pydantic-settings |
| Runtime | Python 3.14 + Uvicorn |
| Testing | pytest + SQLite (in-memory) |
| Frontend | React + TypeScript + Vite |
| Routing | React Router |
| HTTP Client | Axios |
| Styling | Tailwind CSS |
| Charts | Recharts |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI application factory
│   ├── core/
│   │   ├── config.py            # pydantic-settings configuration
│   │   ├── security.py          # bcrypt hashing + JWT utils
│   │   └── exceptions.py        # Domain exceptions + handlers
│   ├── database/
│   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   ├── database.py          # Engine + SessionLocal
│   │   └── session.py           # get_db() FastAPI dependency
│   ├── models/
│   │   └── user.py              # User ORM model + UserRole enum
│   ├── schemas/
│   │   ├── auth.py              # RegisterRequest/Response, LoginRequest, TokenResponse
│   │   └── user.py              # UserPublic, UserBrief
│   ├── api/
│   │   ├── dependencies.py      # get_current_user, require_student, require_faculty
│   │   ├── auth.py              # /api/auth/* routes
│   │   └── protected.py         # RBAC test endpoints
│   └── services/
│       ├── user_service.py      # User CRUD operations
│       └── auth_service.py      # Login / authenticate logic
├── alembic/                     # Alembic migration environment
├── tests/
│   ├── conftest.py              # Fixtures + SQLite test DB
│   └── test_auth.py             # 23 auth + RBAC tests
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Quick Start

### Backend

### 1. Activate the virtual environment

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
```

### 2. Create your local `.env`

```powershell
copy .env.example .env
```

Edit `backend/.env` and set:

```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/academic_assessment_db
JWT_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. Create the PostgreSQL database

```sql
CREATE DATABASE academic_assessment_db;
```

### 4. Run Alembic migrations

```powershell
cd backend
alembic upgrade head
```

### 5. Start the development server

```powershell
cd backend
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

### 6. Run tests

```powershell
cd backend
python -m pytest tests/ -v
```

### Frontend

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

Frontend URL: http://localhost:5173

The frontend expects the backend at:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not put database credentials, JWT secrets, LLM API keys, or other backend secrets in frontend environment variables.

### Run Both Apps

Terminal 1:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

### Production Frontend Build

```powershell
cd frontend
npm run build
```

---

## API Endpoints (Phase 1)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check |
| POST | `/api/auth/register` | None | Register new user |
| POST | `/api/auth/login` | None | Login, receive JWT |
| GET | `/api/auth/me` | Bearer JWT | Current user profile |
| GET | `/api/subjects` | Bearer JWT | Faculty owned subjects or student subject catalog |
| POST | `/api/subjects/{subject_id}/enroll` | STUDENT JWT | Enroll in a subject |
| GET | `/api/subjects/{subject_id}/assignments` | Bearer JWT | List subject assignments |
| POST | `/api/assignments/{assignment_id}/submit` | STUDENT JWT | Submit text, PDF, or DOCX work |
| GET | `/api/submissions` | STUDENT JWT | List current student's submissions |
| GET | `/api/submissions/{submission_id}/assessment` | Bearer JWT | Retrieve assessment details |
| POST | `/api/submissions/{submission_id}/assess` | FACULTY JWT | Trigger AI assessment |
| POST | `/api/assessments/{assessment_id}/approve` | FACULTY JWT | Approve AI score |
| PUT | `/api/assessments/{assessment_id}` | FACULTY JWT | Save modified final score |
| GET | `/api/students/me/analytics` | STUDENT JWT | Student analytics overview |
| GET | `/api/faculty/subjects/{subject_id}/analytics` | FACULTY JWT | Faculty subject analytics |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes | Secret for signing JWTs — generate with `secrets.token_hex(32)` |
| `JWT_ALGORITHM` | No | JWT algorithm (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Token lifetime in minutes (default: `30`) |

---

## User Model

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | Primary Key, auto-increment |
| `full_name` | VARCHAR(255) | NOT NULL |
| `email` | VARCHAR(320) | UNIQUE, NOT NULL, indexed |
| `password_hash` | VARCHAR(255) | NOT NULL (bcrypt, never plaintext) |
| `role` | ENUM (STUDENT/FACULTY) | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, default TRUE |
| `created_at` | TIMESTAMPTZ | server default NOW() |
| `updated_at` | TIMESTAMPTZ | server default NOW(), auto-updates |

---

## JWT Flow

1. Client POSTs credentials to `/api/auth/login`
2. Server validates email + bcrypt password
3. Server creates JWT with `sub=user_id`, `exp=now+30min`
4. Client stores token and sends it as `Authorization: Bearer <token>`
5. Protected routes call `get_current_user()` → decodes JWT → fetches user from DB

---

## Web Portal Workflows

### Student Workflow

1. Register or log in as `STUDENT`.
2. Browse subjects from `/student/subjects`.
3. Enroll in a subject and open assignments.
4. Submit text answers, PDF files, DOCX files, or mixed submissions.
5. Track submissions from `/student/submissions`.
6. Open assessment results once faculty has triggered and reviewed AI assessment.
7. Review analytics at `/student/analytics`, including subject performance, concept mastery, gaps, and trends.

### Faculty Workflow

1. Register or log in as `FACULTY`.
2. Create and manage subjects from `/faculty/subjects`.
3. Create subject assignments from `/faculty/subjects/{subjectId}/assignments`.
4. Upload course materials from `/faculty/subjects/{subjectId}/materials`.
5. Open assignment submissions from `/faculty/assignments/{assignmentId}/submissions`.
6. Trigger AI assessment, inspect reasoning and feedback, then approve or modify the final score.
7. Review class analytics, concept mastery, score distribution, and learning gaps from `/faculty/subjects/{subjectId}/analytics`.

---

## Frontend Architecture

The React app lives in `frontend/`:

```
frontend/src/
├── api/              # Axios client and endpoint modules
├── components/       # Layout, reusable UI, charts, common display components
├── context/          # AuthContext with token persistence
├── hooks/            # Shared async data loading helper
├── pages/            # Auth, student, and faculty pages
├── routes/           # Protected role-based routing
├── types/            # TypeScript models matching FastAPI schemas
└── utils/            # Formatting helpers
```

The design system uses a neutral paper background, charcoal primary actions, subtle borders, restrained shadows, compact tables, and quiet status indicators.

---

## Roadmap

- **Phase 1** ✅ — Backend foundation, auth, RBAC
- **Phase 2** — Assignments, subjects, student submissions
- **Phase 3** — PDF/DOCX processing, document ingestion
- **Phase 4** — RAG + vector database (knowledge retrieval)
- **Phase 5** — LLM evaluation, AI assessment agents
- **Phase 6** ✅ — Student and faculty React web portal
- **Phase 7** — Future enhancements
