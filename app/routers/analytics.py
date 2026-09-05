"""
Analytics Router for Co Penny.
Exposes endpoints for health score, subscriptions, predictions, smart alerts, tax tags, and demo mode.
"""
from fastapi import APIRouter, Query, Request
from typing import Optional

import datetime
from app.tools.enhanced_csv_tools import load_user_data_smart

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ─────────────────────────────────────────────────────────────────
#  Health Score
# ─────────────────────────────────────────────────────────────────

@router.get("/health-score")
def get_health_score(user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]+$")):
    """Return the financial health score (0-1000) with breakdown using PostgreSQL or CSV fallback."""
    try:
        from database.postgres_service import get_postgres_service
        pg = get_postgres_service()
        if pg.is_connected():
            pg_res = pg.calculate_health_score(user_id)
            if pg_res.get("has_data"):
                total_1000 = pg_res["total"]
                total_100 = round(total_1000 / 10)
                return {
                    "total": total_100,
                    "score_1000": total_1000,
                    "components": pg_res.get("components", {}),
                    "income_90d": pg_res.get("income_90d", 0),
                    "expense_90d": pg_res.get("expense_90d", 0),
                    "source": "postgresql",
                    "disclaimer": "This score is an informational metric designed to assist budgeting, not a regulated credit or financial rating."
                }

        from app.tools.health_score import calculate_health_score
        res = calculate_health_score(user_id=user_id)
        if isinstance(res, dict) and "total" in res:
            res["score_1000"] = min(1000, res["total"] * 10)
            res["disclaimer"] = "This score is an informational metric designed to assist budgeting, not a regulated credit or financial rating."
        return res
    except Exception as e:
        return {"status": "error", "error": str(e), "total": 0, "score_1000": 0}


# ─────────────────────────────────────────────────────────────────
#  Subscription Detection
# ─────────────────────────────────────────────────────────────────

@router.get("/subscriptions")
def get_subscriptions(user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]+$")):
    """Detect recurring subscription-style transactions."""
    try:
        from app.tools.health_score import detect_subscriptions
        return detect_subscriptions(user_id=user_id)
    except Exception as e:
        return {"items": [], "monthly_total": 0, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
#  Spending Predictions
# ─────────────────────────────────────────────────────────────────

@router.get("/predictions")
def get_predictions(user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]+$"), budget: float = Query(50000.0, ge=0)):
    """Predict next month's spending and flag budget overruns."""
    try:
        from app.tools.prediction import predict_next_month
        return predict_next_month(user_id=user_id, budget_limit=budget)
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────
#  Smart Alerts
# ─────────────────────────────────────────────────────────────────

@router.get("/smart-alerts")
def get_smart_alerts(user_id: str = Query(...)):
    """Generate proactive smart alerts based on week-over-week spending spikes and budget forecasts."""
    try:
        import pandas as pd
        from app.tools.enhanced_csv_tools import get_user_csv_path

        path = get_user_csv_path(user_id)
        if not path:
            return {"alerts": [], "count": 0}

        df = pd.read_csv(path)
        date_col   = next((c for c in ["date", "Date", "ts"] if c in df.columns), None)
        amount_col = next((c for c in ["amount", "Amount", "monthly_expense_total"] if c in df.columns), None)
        cat_col    = next((c for c in ["category", "Category"] if c in df.columns), None)

        if not (date_col and amount_col):
            return {"alerts": [], "count": 0}

        df[date_col]   = pd.to_datetime(df[date_col], errors="coerce")
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)

        alerts = []
        now = df[date_col].max()

        if cat_col and now is not None and not pd.isnull(now):
            current_week = df[df[date_col] >= now - pd.Timedelta(days=7)]
            last_week    = df[(df[date_col] < now - pd.Timedelta(days=7)) &
                              (df[date_col] >= now - pd.Timedelta(days=14))]

            if not current_week.empty and not last_week.empty:
                cw_cats = current_week[current_week[amount_col] < 0].groupby(cat_col)[amount_col].sum().abs()
                lw_cats = last_week[last_week[amount_col] < 0].groupby(cat_col)[amount_col].sum().abs()

                for cat in cw_cats.index:
                    cw_amt = float(cw_cats.get(cat, 0))
                    lw_amt = float(lw_cats.get(cat, 1))
                    if lw_amt > 0 and cw_amt / lw_amt > 1.3:
                        pct_increase = round((cw_amt / lw_amt - 1) * 100)
                        alerts.append({
                            "type": "unusual_spending",
                            "severity": "medium" if pct_increase < 70 else "high",
                            "title": f"Unusual Spike: {cat}",
                            "message": f"You spent {pct_increase}% more on {cat} this week vs last week (₹{cw_amt:,.0f} vs ₹{lw_amt:,.0f}).",
                            "created_at": now.isoformat(),
                        })

        # Budget forecast alert
        try:
            from app.tools.prediction import predict_next_month
            pred = predict_next_month(user_id=user_id)
            if pred.get("over_budget"):
                alerts.append({
                    "type": "budget_alert",
                    "severity": "high",
                    "title": "Budget Limit Warning",
                    "message": pred.get("alert", "You may exceed your budget next month."),
                    "created_at": (now.isoformat() if now is not None and not pd.isnull(now) else ""),
                })
        except Exception:
            pass

        # Persist to DB
        try:
            from database.firestore_service import get_firestore_service
            db = get_firestore_service()
            for a in alerts:
                db.save_cashflow_alert(user_id, a)
        except Exception:
            pass

        return {"alerts": alerts, "count": len(alerts)}

    except Exception as e:
        return {"alerts": [], "count": 0, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
#  Tax Tags
# ─────────────────────────────────────────────────────────────────

@router.get("/tax-tags")
def get_tax_tags(user_id: str = Query(..., pattern=r"^[a-zA-Z0-9_\-]+$")):
    """Tag potentially tax-deductible transactions (Education, Medical, Business)."""
    try:
        import pandas as pd
        from app.tools.enhanced_csv_tools import get_user_csv_path

        TAX_CATEGORIES = {
            "education": "📚 Education — deductible under 80C/80E",
            "healthcare": "🏥 Medical — deductible under 80D",
            "medical": "🏥 Medical — deductible under 80D",
            "health": "🏥 Health — deductible under 80D",
            "insurance": "🛡️ Insurance — deductible under 80D/80C",
            "business": "💼 Business — deductible under 37(1)",
        }

        path = get_user_csv_path(user_id)
        if not path:
            return {"items": [], "count": 0}

        df = pd.read_csv(path)
        cat_col    = next((c for c in ["category", "Category"] if c in df.columns), None)
        amount_col = next((c for c in ["amount", "Amount", "monthly_expense_total"] if c in df.columns), None)
        date_col   = next((c for c in ["date", "Date"] if c in df.columns), None)

        if not (cat_col and amount_col):
            return {"items": [], "count": 0}

        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
        items = []
        for _, row in df.iterrows():
            cat = str(row.get(cat_col, "")).lower()
            for kw, note in TAX_CATEGORIES.items():
                if kw in cat:
                    items.append({
                        "date":     str(row.get(date_col, "")),
                        "category": str(row.get(cat_col, "")),
                        "amount":   abs(float(row[amount_col])),
                        "note":     note,
                    })
                    break

        total_deductible = sum(i["amount"] for i in items)
        return {
            "items":            items[:100],
            "count":            len(items),
            "total_deductible": round(total_deductible, 2),
        }
    except Exception as e:
        return {"items": [], "count": 0, "error": str(e)}

# ─────────────────────────────────────────────────────────────────
#  Current Stats (Real-time)
# ─────────────────────────────────────────────────────────────────

@router.get("/current-stats")
def get_current_stats(user_id: str = Query(...)):
    """Return real-time spending for today, this week, and monthly average."""
    try:
        import pandas as pd
        df = load_user_data_smart(user_id)
        
        if df is None or df.empty:
            return {
                "today_spent": 0,
                "week_spent": 0,
                "monthly_avg": 0,
                "has_data": False
            }

        # Normalize amount to absolute for spending
        df["abs_amount"] = df["amount"].abs()
        df["year_month"] = df["date"].dt.to_period("M")
        
        # Create an independent copy of expenses to avoid SettingWithCopy warnings and missing columns
        expenses = df[df["amount"] < 0].copy()

        # Use the latest date in the CSV as "today" for better demo consistency
        latest_date = df["date"].max()
        ref_date = latest_date if latest_date else datetime.datetime.now()
        
        # Today's spent
        today_spent = expenses[expenses["date"].dt.date == ref_date.date()]["abs_amount"].sum() if not expenses.empty else 0
        
        # This week's spent (last 7 days from ref_date)
        week_ago = ref_date - datetime.timedelta(days=7)
        week_spent = expenses[(expenses["date"] > week_ago) & (expenses["date"] <= ref_date)]["abs_amount"].sum() if not expenses.empty else 0
        
        # Monthly Average (across all months with data)
        monthly_avg = 0
        if not expenses.empty:
            monthly_exp = expenses.groupby("year_month", observed=True)["abs_amount"].sum()
            monthly_avg = monthly_exp.mean() if not monthly_exp.empty else 0
        
        return {
            "today_spent": round(float(today_spent), 2),
            "week_spent": round(float(week_spent), 2),
            "monthly_avg": round(float(monthly_avg), 2),
            "ref_date": ref_date.strftime("%Y-%m-%d"),
            "has_data": True
        }
    except Exception as e:
        return {
            "today_spent": 0,
            "week_spent": 0,
            "monthly_avg": 0,
            "has_data": False,
            "error": str(e)
        }
