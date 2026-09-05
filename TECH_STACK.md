# CoPenny AI — Complete Tech Stack

**Project:** CoPenny AI — Track Smart. Spend Smarter.  
**Team:** RedHack  

---

## 🎨 Frontend

| Technology | Purpose |
|---|---|
| **React 19** | Core UI framework (Single Page Application) |
| **TypeScript** | Type-safe JavaScript for fewer runtime bugs |
| **Vite** | Lightning-fast build tool & dev server |
| **TailwindCSS** | Utility-first CSS framework adhering to clean slate/zinc design |
| **GSAP & Lucide Icons** | Smooth micro-interactions & accessible iconography |
| **Recharts / Visualizations** | Category spending breakdowns & progress metrics |
| **Firebase Auth SDK** | Google & Email sign-in on client-side |

---

## ⚙️ Backend

| Technology | Purpose |
|---|---|
| **Python 3.11** | Core backend language |
| **FastAPI** | High-performance async REST API framework |
| **Uvicorn** | ASGI server for async streaming & SSE handling |
| **Featherless.ai API** | OpenAI-compatible LLM gateway hosting `Qwen/Qwen2.5-7B-Instruct` |
| **Psycopg2** | Threaded PostgreSQL connection pool with parameterized queries |
| **Pandas & DuckDB** | High-performance CSV data parsing & OLAP analytics |
| **Scikit-Learn** | Anomaly detection & confidence scoring |
| **SlowAPI** | Rate limiting middleware |
| **Pydantic** | Strict request/response data validation |

---

## 🗄️ Database

| Technology | Purpose |
|---|---|
| **PostgreSQL (`hackwave_db`)** | Primary application database (users, transactions, goals, subscriptions, budgets, rules, messages) |
| **Firebase Authentication** | Identity provider & token validation (Google SSO & Email/Password) |
| **Firebase Firestore** | User cloud profiles & alert fallback |
| **Firebase Storage** | User file/image storage |

---

## 🤖 Six Specialized Featherless AI Agents

| Agent | Responsibilities |
|---|---|
| **1. Conversation Agent** | Understands user intent and routes to the appropriate specialist agent |
| **2. Budget Optimizer Agent** | Analyzes spending vs limits, identifies problem categories, generates recommendations |
| **3. Goal Execution Agent** | Formulates savings schedules, calculates timelines, tracks auto-save progress |
| **4. Subscription Manager Agent** | Detects recurring payments, flags unused subscriptions, prepares honest cancellation workflows |
| **5. Anomaly Detection Agent** | Analyzes unusual transactions (>2σ), assigns confidence score, explains risks |
| **6. Rules Engine Agent** | Translates natural language into structured IFTTT rules stored in PostgreSQL |

---

## 🛡️ Security

| Technology | Purpose |
|---|---|
| **JWT Tokens** | Session management via HttpOnly cookies |
| **Firebase Admin SDK** | Cryptographic verification of client identity |
| **Parameterized SQL** | 100% injection-proof queries via Psycopg2 |
| **Server-Side API Keys** | `FEATHERLESS_API_KEY` never exposed to browser |
| **CORS Protection** | Controlled origin requests |

---

## 🚀 Hosting & Deployment

| Layer | Platform |
|---|---|
| **Backend API** | Render Web Service (FastAPI + Uvicorn) |
| **Application Database** | PostgreSQL (`hackwave_db`) |
| **Identity & Storage** | Firebase Auth & Firebase Storage |
| **AI Inference** | Featherless.ai (`Qwen/Qwen2.5-7B-Instruct`) |

---

*CoPenny AI — Engineered with precision by Team RedHack.*
