# NexDesk AI — Production Deployment Architecture & Guide (Module 13)

## 1. Deployment Status Overview

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Backend Production Hardening** | **Configured & Tested** | PostgreSQL pooling (`psycopg2-binary`), `postgres://` URL normalization, safe SQLite-only dialect guard on migrations, `/api/health` subsystem checks, startup secret validation. |
| **Frontend Production Build** | **Configured & Tested** | Production `tsc && vite build` clean (`0` errors), `/api` production fallback (no hardcoded `localhost`), SPA routing configs (`vercel.json`, `public/_redirects`), demo credential helper disabled in standard `PROD` builds. |
| **Container & Cloud Manifests** | **Configured** | `render.yaml`, `Procfile`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.prod.yml`, sanitized `.env.example`, and `backend/scripts/migrate_sqlite_to_postgres.py`. |
| **SMTP Email Integration** | **Configured & Live-Tested** | Verified live Gmail SMTP delivery (`smtp.gmail.com:587`) to `balaji.poet2312s@gmail.com`. |
| **Cloud Public URL Deployment** | **Pending Cloud Account / Git Push** | Local Git repo initialized and `.gitignore` verified, but remote repository (`https://github.com/Balaji-S2312/NexDesk-AI`) is not yet created/pushed and no cloud provider CLI tokens (Vercel/Render/Railway) are authenticated. |

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

1. **Render Free Tier Ephemeral Filesystem & Memory (~512 MB RAM):**
   - Free Render Web Services do **not** provide persistent disk storage across deploys/restarts (uploaded PDFs/DOCX and `./chroma_db` vectors will reset on redeploy) and spin down after 15 minutes of inactivity.
   - Furthermore, loading `sentence-transformers` (`all-MiniLM-L6-v2`) + PyTorch typically consumes **~600–900 MB RAM**, which can trigger Out-Of-Memory (OOM) kills on strict 512 MB free instances.
   - **Recommendation:** Use a **2 GB RAM tier** (e.g., Render Standard, Railway Hobby/Pro, or a VPS with `docker-compose.prod.yml`) and mount a persistent volume at `/app/chroma_db` and `/app/uploads`.
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

## 6. Post-Deployment Verification Checklist

After deploying to your live URLs, verify:
- [ ] `GET https://<backend>/api/health` returns `{"status": "healthy", "database": "healthy"}`.
- [ ] Employee registration triggers verification email to inbox and `/verify-email` activates the account.
- [ ] Unverified employees receive `403` on ticket creation.
- [ ] Verified employee ticket creation dispatches email to both employee and `balaji.poet2312s@gmail.com`.
- [ ] RAG knowledge base document upload persists across backend restarts and returns cited sources in AI chat.
- [ ] Admin dashboard KPIs, Recharts trends, SLA breach indicators, and audit logs load over HTTPS with zero CORS or console errors.

---

## 7. Pre-Deployment Verification Summary (Local Sandbox)

- **Backend Automated Tests:** Verified via `pytest backend/tests/ -q` (Modules 1–13 including health, production config validation, RBAC, RAG, Agentic HITL, SLA, and SMTP verification).
- **Frontend Production Build:** Verified via `tsc && vite build` (`0` TypeScript errors, clean production bundle in `frontend/dist/`).
- **Live SMTP Delivery:** Confirmed live delivery over `smtp.gmail.com:587` to `balaji.poet2312s@gmail.com`.
