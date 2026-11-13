# NexDesk AI — Production Deployment Architecture & Guide (Module 13)

## 1. Deployment Status Overview

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Backend Production Hardening** | **Configured & Tested** | PostgreSQL pooling (`psycopg2-binary`), `postgres://` URL normalization, safe SQLite-only dialect guard on migrations, `/api/health` subsystem checks, startup secret validation. |
| **Frontend Production Build** | **Configured & Tested** | Production `tsc && vite build` clean (`0` errors), `/api` production fallback (no hardcoded `localhost`), SPA routing configs (`vercel.json`, `public/_redirects`), demo credential helper disabled in standard `PROD` builds. |
| **Container & Cloud Manifests** | **Configured** | `render.yaml`, `Procfile`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.prod.yml`, sanitized `.env.example`, and `backend/scripts/migrate_sqlite_to_postgres.py`. |
| **SMTP Email Integration** | **Configured (Platform-Gated on Render Free Tier)** | SMTP configured (`smtp.gmail.com:587` TLS) and 6-digit OTP rendering/logging unit-tested; **Render Free Tier** blocks outbound TCP ports `25/465/587` (`[Errno 101] Network is unreachable` in `EmailDeliveryLog`), requiring either Render Starter tier or an HTTPS Email API provider (port `443`) for live Render cloud delivery. |
| **Frontend Public Deployment (Vercel)** | **LIVE (`https://nexdesk-ai.vercel.app`)** | Connected to `Balaji-S2312/NexDesk-AI` (`rootDirectory: frontend`, Vite framework). Wired to `VITE_API_URL=https://nexdesk-backend-z98v.onrender.com/api`. HTTPS, SPA rewrites, security headers, Admin Dashboard telemetry, Incidents, Notifications, and AI Assistant verified live. |
| **Backend Public Deployment (Render)** | **LIVE (`https://nexdesk-backend-z98v.onrender.com`)** | Python Web Service (`rootDir: backend`, connected to `Balaji-S2312/NexDesk-AI`). Optimized for 512 MB free-tier containers (`vector_store.count() == 0` fast path + ChromaDB `ONNXMiniLM_L6_V2` low-memory embeddings). Connected to external Neon PostgreSQL, Groq LLM API, and Gmail SMTP. |

---

## 2. Recommended Production Architecture

Because NexDesk AI uses **Sentence Transformers (`all-MiniLM-L6-v2`) + PyTorch + ChromaDB persistent vector storage**, cloud hosting tiers must be chosen carefully for RAM and disk persistence:

| Layer | Recommended Option A (Split Cloud) | Recommended Option B (Unified Container + Volume) | Self-Hosted / Docker |
| :--- | :--- | :--- | :--- |
| **Frontend** | **Vercel** (Free Hobby tier, global CDN, automatic HTTPS, `frontend/vercel.json` SPA rewrites) | **Vercel** or **Railway** | Nginx (`frontend/Dockerfile`) |
| **Backend API** | **Render Web Service** (Starter tier w/ Persistent Disk for ChromaDB) | **Railway** (Supports persistent volumes & >=2GB RAM for embeddings) | Uvicorn (`backend/Dockerfile`) |
| **Database** | **Neon** / **Supabase** / **Render Managed PostgreSQL** | **Railway Managed PostgreSQL** | PostgreSQL 16 (`docker-compose.prod.yml`) |
| **Vector Store** | Persistent Disk mounted at `/app/chroma_db` (or Chroma Cloud) | Railway Volume mounted at `/app/chroma_db` | Docker Volume `chromadata` |
| **AI Inference** | **Groq API** (`openai/gpt-oss-120b`) | **Groq API** (`openai/gpt-oss-120b`) | **Groq API** |
| **Email Dispatch** | **Gmail SMTP** (`smtp.gmail.com:587` TLS) | **Gmail SMTP** (`smtp.gmail.com:587` TLS) | **Gmail SMTP** |

---

## 3. Hosting Limitations & Important Architectural Notes

1. **Render Free Tier Ephemeral Vector Disk & 512 MB RAM Optimization:**
   - Free Render Web Services spin down after 15 minutes of inactivity (first request after idle experiences a ~30–60s cold start) and do **not** provide persistent local disk across deploys/restarts (uploaded PDFs/DOCX and `./chroma_db` vectors reset on redeploy unless a persistent disk is attached, whereas relational PostgreSQL data in Neon persists).
   - Standard PyTorch + `sentence-transformers` exceeds 512 MB RAM during model load. `app/services/rag/embeddings.py` and `retriever.py` now detect constrained containers (`<= 768 MB` cgroup limit or `LOW_MEMORY_EMBEDDINGS=true`), skip embedding loads when the index is empty, and switch to lightweight 384-dim `ONNXMiniLM_L6_V2` (`onnxruntime`).
   - **Recommendation for Heavy Knowledge Bases:** Attach a Render Persistent Disk at `/var/data` (or upgrade tier / use `docker-compose.prod.yml`) so uploaded KB documents and ChromaDB vectors survive container restarts.
2. **PostgreSQL vs. SQLite:**
   - Local development runs cleanly on SQLite (`nexdesk.db`).
   - Production deployments should set `DATABASE_URL` to a managed PostgreSQL instance. `app/database/session.py` automatically rewrites `postgres://` to `postgresql://` and enables `pool_pre_ping=True`, while `app/database/init_db.py` skips SQLite-only `ALTER TABLE` backfills when running on PostgreSQL.
3. **Production Admin Account Security:**
   - In `ENVIRONMENT=production`, insecure demo defaults (`AdminPassword123!` / `EmployeePassword123!`) are **not** seeded unless `SEED_DEMO_ACCOUNTS=true` is explicitly set, and the quick demo login buttons on `/login` are hidden in production builds unless `VITE_ENABLE_DEMO_LOGIN=true`.
   - Always configure `ADMIN_SEED_EMAIL` and a strong `ADMIN_SEED_PASSWORD` in your cloud provider's secret manager before first boot.

---

## 4. Required Environment Variables

### Backend Environment Variables (`backend`)
Store these strictly in your hosting provider's secret dashboard (never commit `.env` to Git):

```env
ENVIRONMENT=production
PROJECT_NAME=NexDesk AI
VERSION=0.1.0
API_V1_STR=/api

# Strong random secret (e.g., `openssl rand -hex 32`)
JWT_SECRET=<your-strong-32+-char-random-secret>

# Managed PostgreSQL connection string
DATABASE_URL=postgresql://user:password@host:5432/nexdesk?sslmode=require

# Persistent directory mounted to a cloud disk/volume
CHROMA_PERSIST_DIRECTORY=/var/data/chroma_db
KNOWLEDGE_UPLOAD_DIR=/var/data/uploads/knowledge

# Groq LLM Inference
GROQ_API_KEY=<your-groq-api-key>
GROQ_MODEL=openai/gpt-oss-120b

# Initial Production Admin Credentials
ADMIN_SEED_EMAIL=balaji.poet2312s@gmail.com
ADMIN_SEED_PASSWORD=<strong-production-admin-password>
SEED_DEMO_ACCOUNTS=false

# CORS & Public URLs
CORS_ORIGINS=["https://your-frontend.vercel.app"]
FRONTEND_BASE_URL=https://your-frontend.vercel.app
BACKEND_PUBLIC_URL=https://your-backend.onrender.com

# Gmail SMTP Email Dispatch
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=balaji.poet2312s@gmail.com
SMTP_PASSWORD=<your-16-char-gmail-app-password>
SMTP_FROM_EMAIL=balaji.poet2312s@gmail.com
SMTP_FROM_NAME=NexDesk AI – IT Service Desk
SMTP_USE_TLS=true
ADMIN_NOTIFICATION_EMAIL=balaji.poet2312s@gmail.com
ADMIN_EMAIL=balaji.poet2312s@gmail.com
```

### Frontend Environment Variables (`frontend`)
```env
VITE_API_URL=https://your-backend.onrender.com/api
```

---

## 5. Step-by-Step Deployment Guide

### Option A: Vercel (Frontend) + Render / Railway (Backend)

1. **Push Source Code to GitHub:**
   ```bash
   git add .
   git commit -m "Prepare NexDesk AI for Module 13 production deployment"
   git branch -M main
   git remote add origin https://github.com/Balaji-S2312/NexDesk-AI.git
   git push -u origin main
   ```
   *(Verify `.env`, `*.db`, and `chroma_db/` remain untracked via `.gitignore`.)*

2. **Deploy Managed PostgreSQL:**
   - Create a PostgreSQL database on **Neon**, **Supabase**, **Railway**, or **Render** (from `render.yaml`).
   - Copy the `DATABASE_URL` connection string.
   - *(Optional)* Migrate existing local SQLite data safely:
     ```bash
     cd backend
     .venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py "sqlite:///../nexdesk.db" "<POSTGRES_DATABASE_URL>"
     ```

3. **Deploy Backend (`backend/`):**
   - Connect your GitHub repository in **Render** (Blueprint via `render.yaml`) or **Railway**.
   - **Root Directory:** `backend`
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`
   - Mount a persistent volume/disk at `/var/data` and set `CHROMA_PERSIST_DIRECTORY=/var/data/chroma_db`.
   - Add all backend environment variables listed in Section 4.

4. **Deploy Frontend (`frontend/`):**
   - Import the repository into **Vercel** (or **Netlify**).
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - **Environment Variable:** `VITE_API_URL=https://<your-backend-domain>/api`
   - `frontend/vercel.json` automatically configures SPA React Router rewrites and security headers (`X-Frame-Options`, `X-Content-Type-Options`).

5. **Connect CORS:**
   - After obtaining your live Vercel URL (e.g. `https://nexdesk-ai.vercel.app`), update `CORS_ORIGINS` and `FRONTEND_BASE_URL` in the backend service environment variables and redeploy/restart the backend.

---

### Option B: Full-Stack Production Docker Compose

1. Create a root `.env` with `GROQ_API_KEY`, `JWT_SECRET`, and `SMTP_PASSWORD`.
2. Launch all services (PostgreSQL 16 + FastAPI Backend + Nginx Frontend + persistent volumes):
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Verify health at `http://localhost/api/health` and UI at `http://localhost`.

---

## 6. Live Production Verification Summary (2026-11-13)

- **Live Frontend (Vercel):** `https://nexdesk-ai.vercel.app` (`HTTP 200`, SPA routing & security headers active, `VITE_API_URL` pointed to Render).
- **Live Backend (Render):** `https://nexdesk-backend-z98v.onrender.com`
  - [x] `GET /api/health` -> `200 OK` (`"status": "healthy"`, `"environment": "production"`, `"database": "healthy"`).
  - [x] `POST /api/auth/login` -> `200 OK` for Admin & Employee; `401` on invalid credentials.
  - [x] `GET /api/dashboard/stats`, `/api/analytics/summary`, `/api/sla/overview`, `/api/notifications` -> `200 OK` from Vercel origin with CORS headers.
  - [x] `POST /api/chat` (Groq LLM + tool orchestration) -> `200 OK` with zero OOM or 502 errors.
  - [x] `POST /api/knowledge/upload` + RAG citation chat + `DELETE /api/knowledge/documents/{id}` -> `201` / `200 OK` using low-memory `ONNXMiniLM_L6_V2` embeddings inside Render 512 MB RAM.
  - [x] `POST /api/tickets` -> `201 Created`, `PATCH /api/tickets/{id}` -> `200 OK` (`in_progress` -> `resolved`), real-time notifications updated in UI.
  - [x] Live browser UI verification on `https://nexdesk-ai.vercel.app`: Admin Dashboard KPIs & Recharts trends, Incidents queue, Notification Bell, and AI Assistant chat verified cleanly with zero 4xx/5xx/CORS errors.

  - [x] **6-Digit Email OTP & Adaptive Dropdown Production Fix (`2f52be2`):**
    - Verified `/api/auth/send-otp` cooldown (`429`), anti-enumeration (`200`), wrong-OTP rejection (`400`), duplicate registration guard (`409`), unverified ticket creation gate (`403`), and clean `verify-email` validation (`400`) on live Render.
    - Verified `/login`, `/register` duplicate alert + confirmation card, `/verify-email` (zero `?email=` query parameter, 6 individual digit boxes, countdown timer), `/profile` Verified badge, and `AdaptiveSelect` category icons on desktop floating panels & `390x844` mobile bottom sheets on live `https://nexdesk-ai.vercel.app`.
    - Live `EmailDeliveryLog` inspection (`GET /api/notifications/email-history`) confirmed Render Free Tier blocks outbound SMTP port `587` (`[Errno 101] Network is unreachable`), while logging and handling the `503` failure cleanly without falsely verifying accounts.

---

## 7. Local Pre-Push Verification Summary

- **Backend Automated Tests (`pytest backend/tests/ -q`):** **141 passed, 0 failed** (Modules 1–13 plus OTP hashing, cooldown, lockout, expiry, reuse prevention, anti-enumeration, `409` duplicate registration guard, SMTP failure `503` handling, PostgreSQL compatibility, RBAC, Agentic HITL, SLA, and ONNX RAG).
- **Low-Memory ONNX Embedding Check (`LOW_MEMORY_EMBEDDINGS=true`):** Verified 384-dim embeddings generated cleanly via `ONNXMiniLM_L6_V2`.
- **Frontend Verification (`npm run lint && npm run build`):** `eslint --max-warnings 0` (`0` warnings/errors), `tsc` (`0` errors), clean Vite production bundle in `frontend/dist/`.
- **Live SMTP Delivery Note:** Application SMTP delivery works over `smtp.gmail.com:587` TLS where outbound port `587` is permitted; Render Free Web Services block outbound SMTP ports `25`, `465`, and `587` (`[Errno 101] Network is unreachable`), so live cloud email delivery on Render requires upgrading to a paid Render tier (`Starter`+) or switching email transport to an HTTPS REST Email API over port `443` (e.g., Resend or Brevo).
