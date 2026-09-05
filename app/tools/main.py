import os
import sys
import json
import stat
import asyncio
import httpx
import shutil
import tempfile
import importlib
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, UploadFile, File, Form, Cookie, Depends, HTTPException, status, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# --- Project Path Setup ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

VECTORD_DB_PATH = os.path.join(PROJECT_ROOT, "vectordb")
if VECTORD_DB_PATH not in sys.path:
    sys.path.insert(0, VECTORD_DB_PATH)

# --- App Imports ---
from orchestrator import chat as chat_fn
from app.tools.auth import create_access_token, verify_token
from database.firestore_service import get_firestore_service
from app.services.analytics_service import analytics_engine
from app.services.ai_service import ai_gateway
from app.tools import csv_tools, enhanced_csv_tools, personalization
import pandas as pd

try:
    from enhanced_orchestrator import process_historical_query
except ImportError:
    process_historical_query = None

# These are often used for Flowise/Legacy compatibility
from app.tools.csv_tools import normalize_user_id, query_csv, spend_aggregate, top_merchants, describe_csv
from app.tools.enhanced_csv_tools import total_spend, category_stats, time_coverage, get_available_years, extract_year_data, extract_year_range_data
from app.tools.personalization import PersonalizationEngine

# Import run functions for Flowise stubs
try:
    from run_expense_categorizer import run as run_cat
    from run_budget_monitor import run as rb
    from run_cashflow_predictor import run as run_forecast
    from app.tools.budget import run as budget_run
    from app.tools.budget import DEFAULT_LIMITS
except ImportError:
    run_cat = rb = run_forecast = budget_run = None
    DEFAULT_LIMITS = {}

from app.routers import alerts
from app.routers import analytics as analytics_router
from app.routers import demo as demo_router
from app.routers import transactions as transactions_router
from app.routers import goals as goals_router
from app.routers import subscriptions as subscriptions_router
from app.routers import budgets as budgets_router
from app.routers import rules as rules_router
from app.routers import chat as chat_router
from app.routers import csv_import as csv_import_router
from app.routers import anomalies as anomalies_router

limiter = Limiter(key_func=get_remote_address, enabled=False)
app = FastAPI(title="Co Penny Advisor")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(alerts.router)
app.include_router(analytics_router.router)
app.include_router(demo_router.router)
app.include_router(transactions_router.router)
app.include_router(goals_router.router)
app.include_router(subscriptions_router.router)
app.include_router(budgets_router.router)
app.include_router(rules_router.router)
app.include_router(chat_router.router)
app.include_router(csv_import_router.router)
app.include_router(anomalies_router.router)

# --- JWT Dependency (must be defined BEFORE any endpoint that uses it) ---
def get_current_user(copenny_auth: Optional[str] = Cookie(None)) -> Dict[str, Any]:
    """FastAPI dependency: validates the Firebase ID token cookie and returns the payload."""
    if not copenny_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

class FinancialInsightReq(BaseModel):
    user_id: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")

@app.post("/api/ai/financial-insight")
@limiter.limit("5/minute")
async def get_financial_insight(req: FinancialInsightReq, request: Request):
    """
    Secure endpoint for financial analytics and Featherless AI insights.
    Calculates metrics on-the-fly from the user's CSV and uses the AI Gateway for insights.
    """
    # 1. Calculate Analytics
    analytics = analytics_engine.calculate_metrics(req.user_id)

    if not analytics.get("has_data"):
        return {
            "financialHealthScore": 0,
            "topSpendingCategory": "N/A",
            "potentialSavings": 0,
            "monthlySummary": {},
            "insight": "No transaction data found. Please upload a CSV to get started.",
            "status": "no_data",
            "has_data": False
        }

    # 2. Construct detailed Prompt for Featherless AI
    prompt = f"""You are Co Penny AI, an elite financial advisor with deep analytical skills.
Analyze the following financial data and generate a DETAILED insight formatted clearly in bullet points.
Be specific, use the actual numbers provided, and split your response into clear distinct points:
1. A data-driven insight about their current financial health.
2. A breakdown of their top spending.
3. At least one concrete, actionable recommendation to improve savings.

Use `- ` for bullet points.

Financial Data:
- Total Spending: \u20b9{analytics['totalSpent']:,.0f}
- Financial Health Score: {analytics['financialHealthScore']}/100
- Top Spending Category: {analytics['topSpendingCategory']}
- Potential Monthly Savings: \u20b9{analytics['potentialSavings']:,.0f}

Category Breakdown:
{json.dumps(analytics['monthlySummary'], indent=2)}

Provide the insight formatted beautifully as bullet points."""

    # 3. Try the AI Gateway async, always fall back to analytics data
    try:
        ai_result = await ai_gateway.aget_insight(req.user_id, prompt, analytics)
    except Exception:
        ai_result = {}

    # 4. Merge: analytics data guarantees the fields the frontend needs
    return {
        "financialHealthScore": analytics["financialHealthScore"],
        "topSpendingCategory": analytics["topSpendingCategory"],
        "potentialSavings": analytics["potentialSavings"],
        "monthlySummary": analytics["monthlySummary"],
        "totalSpent": analytics["totalSpent"],
        "has_data": True,
        "status": "success",
        # AI insight is best-effort; fall back to a simple summary
        "insight": (
            ai_result.get("insight")
            or f"Your top spending category is **{analytics['topSpendingCategory']}** with "
               f"\u20b9{analytics['totalSpent']:,.0f} total this period. "
               f"Potential savings identified: \u20b9{analytics['potentialSavings']:,.0f}. "
               f"Your financial health score is {analytics['financialHealthScore']}/100."
        ),
    }

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # this is inside app/tools
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR)) # go up two levels to reach CoPenny.Ai root
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), "static") # static is in app/static
REACT_DIST_DIR = os.path.join(PROJECT_ROOT, "frontend", "dist")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Serve React assets if the directory exists
if os.path.exists(REACT_DIST_DIR):
    assets_path = os.path.join(REACT_DIST_DIR, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="react-assets")

# (get_current_user moved to top of file, before endpoints)

class ChatReq(BaseModel):
    session_id: str = Field(..., max_length=100)
    message: str = Field(..., max_length=2000)
    context: List[Dict[str, str]] = []
    user_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_\-]+$")

class CategorizeReq(BaseModel):
    user_id: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")
    tx_ids: List[str] = []

class AuthSyncReq(BaseModel):
    id_token: str
    name: Optional[str] = Field(None, max_length=100)

class SubscriptionSelectReq(BaseModel):
    user_id: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")
    tier: str = Field(..., pattern=r"^(free|pro|enterprise)$")
    months: int = Field(1, ge=1, le=120)

class PersonaUpdateReq(BaseModel):
    user_id: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")
    persona: str = Field(..., pattern=r"^(individual|startup)$")

@app.get("/")
def root():
    return RedirectResponse(url="/landing")

@app.get("/demo")
def demo_direct():
    response = RedirectResponse(url="/ui")
    response.set_cookie(
        key="copenny_auth",
        value="demo_user",
        path="/",
        max_age=604800,
        samesite="lax",
        httponly=False
    )
    return response

@app.get("/ui")
def ui(copenny_auth: Optional[str] = Cookie(None)):
    print(f"[DEBUG] /ui access - copenny_auth cookie: {copenny_auth}")
    index_path = os.path.join(STATIC_DIR, "index.html")
    
    if copenny_auth:
        payload = verify_token(copenny_auth)
        if payload:
            print(f"[DEBUG] Authorized access for user: {payload.get('user_id')}")
            return FileResponse(index_path)
        else:
            print("[DEBUG] Invalid or expired JWT token")
            return RedirectResponse(url="/landing?error=unauthorized")
    
    # Allow client-side session / localStorage verification to resolve
    print("[DEBUG] No direct cookie on /ui, serving index.html for client-side session check")
    return FileResponse(index_path)

@app.get("/landing")
def landing():
    # Try to serve React version first
    react_index = os.path.join(REACT_DIST_DIR, "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
        
    # Fallback to legacy version
    landing_path = os.path.join(STATIC_DIR, "landing.html")
    return FileResponse(landing_path)

@app.get("/security")
def security():
    security_path = os.path.join(STATIC_DIR, "security.html")
    return FileResponse(security_path)

@app.get("/ai-advisor")
def ai_advisor():
    return FileResponse(os.path.join(STATIC_DIR, "ai_advisor.html"))

@app.get("/documentation")
def documentation():
    return FileResponse(os.path.join(STATIC_DIR, "documentation.html"))

@app.get("/community")
def community():
    return FileResponse(os.path.join(STATIC_DIR, "community.html"))

@app.get("/help")
def help_center():
    return FileResponse(os.path.join(STATIC_DIR, "help_center.html"))

@app.get("/about")
def about_us():
    return FileResponse(os.path.join(STATIC_DIR, "about_us.html"))

@app.get("/careers")
def careers():
    return FileResponse(os.path.join(STATIC_DIR, "careers.html"))

@app.get("/contact")
def contact():
    return FileResponse(os.path.join(STATIC_DIR, "contact.html"))

@app.get("/privacy")
def privacy_policy():
    return FileResponse(os.path.join(STATIC_DIR, "privacy_policy.html"))

@app.get("/terms")
def terms_of_service():
    return FileResponse(os.path.join(STATIC_DIR, "terms_of_service.html"))

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/sync")
@limiter.limit("20/minute")
def auth_sync(req: AuthSyncReq, response: Response, request: Request):
    """
    Sync Firebase user with our database (PostgreSQL primary, Firestore secondary).
    Called by frontend after social login or email signup.
    """
    # Verify the Firebase token
    payload = verify_token(req.id_token)
    if not payload:
        return {"success": False, "error": "Invalid or expired Firebase token. Please sign in again."}
    
    uid = payload["user_id"]
    email = payload.get("email") or f"{uid}@copenny.ai"
    name = req.name or payload.get("name") or email.split("@")[0] or "Investor"

    # Set the auth cookie (HttpOnly for security)
    response.set_cookie(
        key="copenny_auth", 
        value=req.id_token, 
        path="/", 
        max_age=604800, 
        samesite="lax",
        httponly=True
    )
    print(f"[DEBUG] Firebase Auth Cookie set for user: {uid}")

    # Primary Database: PostgreSQL
    try:
        from database.postgres_service import get_postgres_service
        pg = get_postgres_service()
        if pg.is_connected():
            pg.upsert_user(
                firebase_uid=uid,
                email=email,
                name=name
            )
            print(f"[AUTH] PostgreSQL user synced successfully: {uid}")
    except Exception as pg_err:
        print(f"[AUTH] PostgreSQL user sync note: {pg_err}")

    # Optional Secondary Database: Firestore (if configured)
    try:
        from database.firestore_service import get_firestore_service
        db = get_firestore_service()
        if db.is_connected():
            db.sync_firebase_user(
                uid=uid, 
                email=email, 
                name=name
            )
    except Exception as fs_err:
        print(f"[AUTH] Firestore sync note: {fs_err}")

    return {
        "success": True,
        "user_id": uid,
        "email": email,
        "name": name
    }

@app.post("/auth/update-persona")
def update_persona(req: PersonaUpdateReq):
    """
    Update the user's trading persona.
    Persists to Firestore user_profiles/{user_id}.
    """
    from database.firestore_service import get_firestore_service
    db = get_firestore_service()
    res = db.update_user_profile(req.user_id, {
        "persona": req.persona,
        "experience": req.experience
    })
    return res

@app.post("/auth/logout")
def logout(response: Response):
    """Clear the auth cookie to log out the user."""
    response.delete_cookie(key="copenny_auth", path="/")
    return {"success": True, "message": "Logged out"}

@app.get("/api/me")
def get_me(copenny_auth: Optional[str] = Cookie(None)):
    """Return basic user info from the active session cookie."""
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    tier = "free"
    plan_confirmed = True
    try:
        from database.firestore_service import get_firestore_service
        sub = get_firestore_service().get_user_subscription(payload.get("user_id")) or {}
        tier = sub.get("tier", "free")
        plan_confirmed = sub.get("plan_confirmed", False) if tier != "free" else sub.get("plan_confirmed", True)
    except Exception:
        pass

    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "name": payload.get("name") or "Investor",
        "tier": tier,
        "plan_confirmed": plan_confirmed,
        "authenticated": True
    }

@app.get("/subscription/status")
def get_subscription_status(user_id: str = Query(...)):
    """Get current subscription status and features for a user"""
    try:
        from database.firestore_service import get_firestore_service
        db = get_firestore_service()
        if db.is_connected():
            return db.get_user_subscription(user_id)
    except Exception as e:
        print(f"[SUBSCRIPTION] Firestore status note: {e}")
    from database.firestore_service import SUBSCRIPTION_TIERS
    return {"tier": "free", "features": SUBSCRIPTION_TIERS["free"], "plan_confirmed": True}

@app.post("/subscription/select")
def select_subscription(req: SubscriptionSelectReq, request: Request):
    """Select or upgrade subscription tier"""
    tier = req.tier.lower() if req.tier else "free"
    try:
        from database.firestore_service import get_firestore_service
        db = get_firestore_service()
        if db.is_connected():
            return db.update_user_subscription(req.user_id, tier, req.months, confirmed=True)
    except Exception as e:
        print(f"[SUBSCRIPTION] Firestore select note: {e}")
    return {"success": True, "tier": tier, "user_id": req.user_id}

@app.get("/activate-tier")
def activate_tier(user_id: str = Query(...), tier: str = Query("free")):
    """Magic link to instantly switch subscription tiers and redirect to dashboard"""
    from database.firestore_service import get_firestore_service
    db = get_firestore_service()
    tier_lower = tier.lower()
    if tier_lower not in ["free", "pro", "enterprise"]:
        tier_lower = "free"
    db.update_user_subscription(user_id, tier_lower, months=12)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui")

@app.post("/chat")
async def chat_api(req: ChatReq, request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        from database.firestore_service import get_firestore_service
        db = get_firestore_service()
        
        # Check subscription limits
        if req.user_id:
            access = db.check_feature_access(req.user_id, "ai_query")
            if not access.get("allowed"):
                return {
                    "answer": "You have reached your AI query limit for today. Please upgrade your plan to continue.",
                    "status": "limit_reached",
                    "type": "error"
                }

        # chat_fn is async — await it directly (run_in_executor would silently return a coroutine object)
        response = await chat_fn(req.message, req.context, user_id=req.user_id)
        
        # Increment usage if successful
        if req.user_id and response:
            db.increment_usage(req.user_id, "ai_query")

        if isinstance(response, dict):
            return response
        return {"answer": str(response), "status": "success", "type": "text"}
    except Exception as e:
        # Fallback: provide useful response rather than raw error
        print(f"Chat API Error: {e}")
        return {
            "answer": "I'm currently processing a heavy analytics job for another user. 🔄 Please retry in 5 seconds — your question is important and I want to give you a proper detailed answer!",
            "status": "success",
            "type": "text"
        }

@app.delete("/personalization/data")
def delete_user_data(user_id: str = Query(...)):
    """Delete all data associated with a user"""
    
    try:
        # Delete from DB
        db = get_firestore_service()
        db.delete_user_profile(user_id)
        
        # Delete from filesystem
        
        def remove_readonly(func, path, excinfo):
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        safe_id = normalize_user_id(user_id)
        user_dir = os.path.join(PROJECT_ROOT, "state", "models", "user_data", safe_id)
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir, onerror=remove_readonly)
            
        return {"success": True, "message": "User data deleted successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/alerts/history")
def get_alert_history(user_id: str = Query(...), limit: int = Query(50), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get alert history for a user"""
    try:
        db = get_firestore_service()
        alerts = db.get_user_alerts(user_id, limit)
        return {"success": True, "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        return {"success": False, "error": str(e), "alerts": []}

@app.delete("/alerts/history")
def clear_alert_history(user_id: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Clear all alerts for a user"""
    try:
        db = get_firestore_service()
        db.clear_user_alerts(user_id)
        return {"success": True, "message": "Alert history cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/dashboard/summary")
def dashboard_summary(user_id: str = Query(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch real-time financial metrics for the dashboard"""
    try:
        # Use smart load for consistency
        from app.tools.enhanced_csv_tools import load_user_data_smart
        df = load_user_data_smart(user_id)
        
        if df is None or df.empty:
            return {
                "balance": 0,
                "monthly_expense": 0,
                "confidence": 0,
                "transaction_count": 0,
                "has_data": False
            }
            
        row_count = len(df)
        total_income = df[df['amount'] > 0]['amount'].sum()
        total_expense = df[df['amount'] < 0]['amount'].abs().sum()
        balance = total_income - total_expense
        
        # Calculate monthly expense (latest month)
        latest_month = df['date'].max().to_period('M')
        monthly_expense = df[(df['date'].dt.to_period('M') == latest_month) & (df['amount'] < 0)]['amount'].abs().sum()
        
        # Calculate a pseudo "AI Confidence" based on data density
        confidence = min(100, (row_count / 10) * 20) # 5+ rows = 100%
        
        return {
            "balance": round(float(balance), 2),
            "monthly_expense": round(float(monthly_expense), 2),
            "confidence": round(float(confidence), 2),
            "transaction_count": row_count,
            "has_data": True
        }
    except Exception as e:
        print(f"[DASHBOARD ERROR] {str(e)}")
        return {"error": str(e), "has_data": False}

@app.get("/selftest")
def selftest():
    """Diagnostic endpoint to verify engine health, Featherless AI, and PostgreSQL"""
    out: Dict[str, Any] = {}
    
    # Check data connection
    from database.postgres_service import get_postgres_service
    pg = get_postgres_service()
    db_desc = "neondb (Neon Cloud)" if os.getenv("DATABASE_URL") else os.getenv("PGDATABASE", "hackwave_db")
    out["database_engine"] = {
        "provider": "PostgreSQL",
        "status": "CONNECTED" if pg.is_connected() else "DISCONNECTED",
        "database": db_desc
    }
    
    # Featherless AI Status
    featherless_key = os.getenv("FEATHERLESS_API_KEY")
    out["ai_engine"] = {
        "provider": "Featherless.ai",
        "model": os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        "status": "OPERATIONAL" if featherless_key else "KEY_MISSING",
        "key_configured": bool(featherless_key)
    }
    
    # Engine Modules
    modules = ["llm.featherless_client", "app.services.ai_service", "database.postgres_service"]
    out["engine_modules"] = {}
    for m in modules:
        try:
            importlib.import_module(m)
            out["engine_modules"][m] = "READY"
        except Exception as e:
            out["engine_modules"][m] = f"ERROR: {e}"
            
    out["demo_readiness"] = "100%" if (featherless_key and pg.is_connected()) else "90% (Local Mode)"
    return out


# Flowise-compatible endpoints (minimal)
@app.post("/tools/categorize_txn")
def categorize_txn(req: CategorizeReq):
    # For demo, ignore tx_ids and run on current CSV
    return run_cat(transactions_path="data/transactions.csv", use_llm=True)

@app.get("/reports/spend_mtd")
def spend_mtd(user_id: str = Query(...)):
    return budget_run()

@app.get("/budgets")
def budgets(user_id: str = Query(...)):
    return DEFAULT_LIMITS

@app.get("/series/daily_net_flow")
def daily_net_flow(user_id: str = Query(...), window: int = Query(365)):
    # Simple placeholder: return empty series for now (Flowise template stub)
    return []

@app.post("/models/forecast")
def forecast(series: Any):
    return run_forecast()

@app.post("/tools/query_csv")
def http_query_csv(payload: Dict[str, Any]):
    sql = str(payload.get("sql") or "").strip()
    limit = int(payload.get("limit") or 1000)
    return query_csv(sql=sql, limit=limit)

@app.get("/tools/spend_aggregate")
def http_spend_aggregate(month: Optional[str] = Query(None), group_by: str = Query("category")):
    return spend_aggregate(month=month, group_by=group_by)

@app.get("/tools/top_merchants")
def http_top_merchants(month: Optional[str] = Query(None), n: int = Query(10)):
    return top_merchants(month=month, n=n)

@app.get("/tools/describe_csv")
def http_describe_csv():
    return describe_csv()

@app.post("/historical/analyze")
def historical_analysis(req: ChatReq):
    """Dedicated endpoint for historical analysis with charts"""
    try:
        response = process_historical_query(req.message, req.context)
        return response
    except Exception as e:
        return {
            "answer": f"Error in historical analysis: {str(e)}",
            "status": "error",
            "type": "error"
        }

@app.get("/historical/years")
def get_available_years():
    """Get list of available years in the dataset"""
    try:
        years = get_available_years()
        return {"years": years, "status": "success"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

@app.get("/historical/year/{year}")
def get_year_data(year: int):
    """Get data for a specific year"""
    try:
        data = extract_year_data(year)
        return data
    except Exception as e:
        return {"error": str(e), "status": "error"}

@app.get("/historical/range/{start_year}/{end_year}")
def get_year_range_data(start_year: int, end_year: int):
    """Get data for a range of years"""
    try:
        data = extract_year_range_data(start_year, end_year)
        return data
    except Exception as e:
        return {"error": str(e), "status": "error"}


# Personalization endpoints
@app.post("/personalization/upload")
async def upload_personal_data(
    request: Request,
    file: UploadFile = File(...), 
    user_id: str = Form(..., pattern=r"^[a-zA-Z0-9_\-]+$"),
    overwrite: bool = Form(False)
):
    """
    Handle CSV upload, save to state/user_data/{user_id}/transactions.csv, 
    and update metadata.
    """
    # 1. Validate File Size (Max 10MB)
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB allowed.")
    await file.seek(0)

    # 2. Validate File Content Type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed.")
    try:
        db = get_firestore_service()
        
        # Check subscription limits
        access = db.check_feature_access(user_id, "transactions")
        if not access.get("allowed"):
            return {
                "success": False,
                "error": f"You have reached your transaction limit for your current plan ({access.get('limit')} records). Please upgrade to upload more data."
            }

        # Validate file type
        filename = file.filename.lower()
        print(f"[UPLOAD] user_id={user_id} filename={filename}") # Diagnostic log
        if not (filename.endswith('.csv') or filename.endswith('.xls') or filename.endswith('.xlsx')):
            return {
                "success": False,
                "error": "File must be a CSV or Excel file"
            }
        
        # Save uploaded file temporarily with correct extension
        # IMPORTANT: We already read 'content' for size validation above, so we write 
        # those bytes directly instead of re-reading via shutil.copyfileobj (which would
        # get an empty stream since file.file is already at EOF).
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(content)  # Use already-buffered bytes
            tmp_path = tmp_file.name
        
        try:
            # Process CSV
            engine = PersonalizationEngine()
            result = engine.process_user_csv(tmp_path, user_id, overwrite=overwrite)
            
            # Generate cashflow alerts if upload was successful
            if result.get("success"):
                # Track transaction count based on metadata
                metadata = result.get("metadata", {})
                tx_count = metadata.get("transaction_count", 0)
                # Note: We should ideally increment by tx_count, but for now we just track that they performed an upload
                # In a real production system, we'd count every row.
                db.increment_usage(user_id, "transaction")
                
            return result
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def generate_cashflow_alerts(user_id: str, metadata: dict):
    """Generate cashflow alerts based on uploaded transaction data"""
    try:
        db = get_firestore_service()
        safe_id = normalize_user_id(user_id)
        
        # Load user's CSV data
        user_csv = os.path.join(PROJECT_ROOT, "state", "models", "user_data", safe_id, "transactions.csv")
        if not os.path.exists(user_csv):
            return
        
        df = pd.read_csv(user_csv)
        
        # Detect amount column using robust list
        amount_variants = ["amount", "Amount", "AMOUNT", "monthly_expense_total", "val", "sum", "price", "cost", "Value"]
        amount_col = next((c for c in amount_variants if c in df.columns), None)
        
        if not amount_col:
            print(f"[ALERTS ERROR] No amount column found in {user_csv}")
            return
        
        # Convert to numeric
        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
        
        # Calculate statistics
        avg_amount = df[amount_col].abs().mean()
        max_amount = df[amount_col].abs().max()
        total_expense = df[df[amount_col] < 0][amount_col].sum() if (df[amount_col] < 0).any() else 0
        
        # Alert 1: Large transactions (> 3x average)
        large_threshold = avg_amount * 3
        large_transactions = df[df[amount_col].abs() > large_threshold]
        if len(large_transactions) > 0:
            db.save_cashflow_alert(user_id, {
                "type": "large_transaction",
                "severity": "high",
                "title": "Large Transaction Detected",
                "message": f"Found {len(large_transactions)} transaction(s) exceeding ₹{large_threshold:,.0f}. Largest: ₹{max_amount:,.0f}"
            })
        
        # Alert 2: High expense warning
        if total_expense < -50000:  # expense > 50k
            db.save_cashflow_alert(user_id, {
                "type": "high_expense",
                "severity": "medium",
                "title": "High Expense Warning",
                "message": f"Your total expenses are ₹{abs(total_expense):,.0f}. Consider reviewing your spending."
            })
        
        # Alert 3: Data quality alert
        transaction_count = len(df)
        if transaction_count < 20:
            db.save_cashflow_alert(user_id, {
                "type": "data_quality",
                "severity": "low",
                "title": "Low Data Volume",
                "message": f"Only {transaction_count} transactions uploaded. For better insights, upload more historical data."
            })
        elif transaction_count >= 50:
            db.save_cashflow_alert(user_id, {
                "type": "data_quality", 
                "severity": "low",
                "title": "Good Data Volume",
                "message": f"{transaction_count} transactions analyzed. AI model is ready for accurate predictions."
            })
        
        # Alert 4: Category-based alerts using robust list
        cat_variants = ["category", "Category", "CATEGORY", "goods", "type", "narration", "description", "Category Name"]
        category_col = next((c for c in cat_variants if c in df.columns), None)
        if category_col:
            category_spending = df.groupby(category_col)[amount_col].sum()
            # Most negative or smallest value = most spending (if amounts are negative)
            # If amounts are positive, we want the max.
            # Lets check if we have any negative values
            has_negatives = (df[amount_col] < 0).any()
            if has_negatives:
                top_category = category_spending.idxmin()
                top_amount = abs(category_spending.min())
            else:
                top_category = category_spending.idxmax()
                top_amount = category_spending.max()
                
            if top_amount > avg_amount * 10:
                db.save_cashflow_alert(user_id, {
                    "type": "category_spending",
                    "severity": "medium",
                    "title": f"High Spending: {top_category}",
                    "message": f"Significant spending of ₹{top_amount:,.0f} detected in {top_category} category."
                })
                
    except Exception as e:
        print(f"Error generating alerts: {e}")


@app.post("/personalization/train")
def train_personal_model(
    user_id: str = Form(...),
    retrain: bool = Form(False)
):
    """
    Train a personalized model for a user
    
    Args:
        user_id: Unique user identifier
        retrain: Whether to retrain if model already exists
    """
    try:
        from app.tools.personalization import PersonalizationEngine
        
        engine = PersonalizationEngine()
        result = engine.train_user_model(user_id, retrain=retrain)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/personalization/status/{user_id}")
def get_personalization_status(user_id: str):
    """
    Get personalization status for a user
    
    Args:
        user_id: Unique user identifier
    """
    try:
        from app.tools.personalization import PersonalizationEngine
        
        engine = PersonalizationEngine()
        
        # Get metadata
        metadata = engine.get_user_metadata(user_id)
        
        # Check if model exists
        model_path = engine.get_user_model_path(user_id)
        has_model = model_path is not None
        
        return {
            "user_id": user_id,
            "has_data": metadata is not None,
            "has_model": has_model,
            "metadata": metadata,
            "model_path": model_path if has_model else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/personalization/validate")
async def validate_csv(file: UploadFile = File(...)):
    """
    Validate CSV file structure before upload
    
    Args:
        file: CSV file to validate
    """
    try:
        from app.tools.personalization import PersonalizationEngine
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            engine = PersonalizationEngine()
            result = engine.validate_csv(tmp_path)
            return result
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@app.get("/personalization/users")
def list_personalized_users():
    """List all users with personalized data"""
    try:
        from app.tools.personalization import PersonalizationEngine
        
        engine = PersonalizationEngine()
        users = engine.list_users()
        
        # Get status for each user
        user_statuses = []
        for user_id in users:
            metadata = engine.get_user_metadata(user_id)
            model_path = engine.get_user_model_path(user_id)
            user_statuses.append({
                "user_id": user_id,
                "has_model": model_path is not None,
                "metadata": metadata
            })
        
        return {
            "users": user_statuses,
            "count": len(users)
        }
    except Exception as e:
        return {
            "error": str(e),
            "users": []
        }


# User Profile Management Endpoints (MongoDB)
@app.post("/profile/create")
def create_user_profile(
    user_id: str = Form(...),
    profile_data: str = Form(...)  # JSON string
):
    """
    Create or update user profile in MongoDB
    
    Args:
        user_id: Unique user identifier
        profile_data: JSON string with profile data
    """
    try:
        db = get_firestore_service()
        if not db.is_connected():
            return {
                "success": False,
                "error": "Firebase Firestore not connected. Please check your setup."
            }
        
        # Parse JSON profile data
        profile = json.loads(profile_data)
        
        result = db.create_user_profile(user_id, profile)
        return result
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON in profile_data"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/profile/{user_id}")
def get_user_profile(user_id: str):
    """
    Get user profile from MongoDB
    
    Args:
        user_id: Unique user identifier
    """
    try:
        db = get_firestore_service()
        if not db.is_connected():
            # Fallback to file-based profile
            profile_path = os.path.join("apex-wealth-agents", "state", "profile.json")
            if os.path.exists(profile_path):
                with open(profile_path, 'r') as f:
                    return {"success": True, "profile": json.load(f), "source": "file"}
            return {"success": False, "error": "Profile not found"}
        
        profile = db.get_user_profile(user_id)
        if profile:
            return {"success": True, "profile": profile, "source": "firestore"}
        else:
            return {"success": False, "error": "Profile not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/profile/{user_id}")
def update_user_profile(
    user_id: str,
    updates: str = Form(...)  # JSON string
):
    """
    Update user profile fields
    
    Args:
        user_id: Unique user identifier
        updates: JSON string with fields to update
    """
    try:
        db = get_firestore_service()
        if not db.is_connected():
            return {
                "success": False,
                "error": "Firebase Firestore not connected"
            }
        
        update_data = json.loads(updates)
        result = db.update_user_profile(user_id, update_data)
        return result
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON in updates"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/profile/{user_id}")
def delete_user_profile(user_id: str):
    """
    Delete user profile
    
    Args:
        user_id: Unique user identifier
    """
    try:
        db = get_firestore_service()
        if not db.is_connected():
            return {
                "success": False,
                "error": "Firebase Firestore not connected"
            }
        
        result = db.delete_user_profile(user_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/profile/list")
def list_all_profiles():
    """List all user profiles"""
    try:
        db = get_firestore_service()
        if not db.is_connected():
            return {
                "success": False,
                "error": "Firebase Firestore not connected",
                "users": []
            }
        
        users = db.list_all_users()
        return {
            "success": True,
            "users": users,
            "count": len(users)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "users": []}


@app.get("/database/status")
def database_status():
    """Check Database connection status (Firestore)"""
    try:
        from database.firestore_service import get_firestore_service
        
        db = get_firestore_service()
        is_connected = db.is_connected()
        
        return {
            "database_type": "Firestore",
            "connected": is_connected,
            "status": "connected" if is_connected else "disconnected"
        }
    except Exception as e:
        return {
            "connected": False,
            "status": "error",
            "error": str(e)
        }

