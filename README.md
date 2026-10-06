# AI-Driven Intelligent Academic Assessment and Performance Analytics System

## Phase 1 — Backend Foundation

A FastAPI + PostgreSQL backend with JWT authentication and role-based access control (RBAC), designed as the foundation for an AI-powered academic assessment platform.

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

---

## API Endpoints (Phase 1)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check |
| POST | `/api/auth/register` | None | Register new user |
| POST | `/api/auth/login` | None | Login, receive JWT |
| GET | `/api/auth/me` | Bearer JWT | Current user profile |
| GET | `/api/student/dashboard` | STUDENT JWT | Student-only test endpoint |
| GET | `/api/faculty/dashboard` | FACULTY JWT | Faculty-only test endpoint |

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

## Roadmap

- **Phase 1** ✅ — Backend foundation, auth, RBAC
- **Phase 2** — Assignments, subjects, student submissions
- **Phase 3** — PDF/DOCX processing, document ingestion
- **Phase 4** — RAG + vector database (knowledge retrieval)
- **Phase 5** — LLM evaluation, AI assessment agents
- **Phase 6** — Personalized feedback, analytics dashboards
- **Phase 7** — React frontend
