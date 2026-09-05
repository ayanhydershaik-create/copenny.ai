"""
Financial Health Score Calculator for Co Penny.
Produces a score out of 100 with a breakdown across four dimensions.
"""
import os
import math
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def _load_df_smart(user_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Load and normalize user transaction data."""
    from app.tools.enhanced_csv_tools import load_user_data_smart
    return load_user_data_smart(user_id)


def calculate_health_score(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate a financial health score (0-100) across four dimensions:
      1. Savings Habit       (30 pts)
      2. Budget Discipline   (30 pts)
      3. Spending Stability  (20 pts)
      4. Subscription Mgmt   (20 pts)

    Returns a dict with `total`, `breakdown`, and `level` fields.
    """
    df = _load_df_smart(user_id)

    if df is None or df.empty:
        return _empty_score("No transaction data found.")

    # All columns are already normalized to "date", "amount", "category"
    date_col = "date"
    amount_col = "amount"
    cat_col = "category"
    
    # We don't need type_col anymore because sign detection is handled in load_user_data_smart
    
    # Separate income & expense
    expenses = df[df[amount_col] < 0][amount_col].abs()
    income   = df[df[amount_col] > 0][amount_col]

    total_income  = float(income.sum())
    total_expense = float(expenses.sum())

    # ── 1. Savings Habit (30 pts) ─────────────────────────────────────────
    if total_income > 0:
        savings_rate = (total_income - total_expense) / total_income
    else:
        savings_rate = 0.0
    savings_pts = _clamp(savings_rate * 2.0) * 30   # 50% savings → full score

    # ── 2. Budget Discipline (30 pts) ─────────────────────────────────────
    # Look at monthly expense growth; stable or declining = good
    if date_col and df[date_col].notna().any():
        df["__month"] = df[date_col].dt.to_period("M")
        monthly_exp   = df[df[amount_col] < 0].groupby("__month")[amount_col].sum().abs()
        if len(monthly_exp) >= 2:
            pct_changes = monthly_exp.pct_change().dropna()
            avg_growth  = float(pct_changes.mean())
            # negative growth (spending dropping) → good
            discipline_score = _clamp(0.5 - avg_growth)
        else:
            discipline_score = 0.5  # neutral
    else:
        discipline_score = 0.5
    budget_pts = discipline_score * 30

    # ── 3. Spending Stability (20 pts) ────────────────────────────────────
    if date_col and df[date_col].notna().any():
        monthly_std  = monthly_exp.std() if 'monthly_exp' in dir() else 0
        monthly_mean = monthly_exp.mean() if 'monthly_exp' in dir() else 1
        cv = (monthly_std / monthly_mean) if monthly_mean > 0 else 1.0
        stability_score = _clamp(1 - cv)  # low variation → high score
    else:
        stability_score = 0.5
    stability_pts = stability_score * 20

    # ── 4. Subscription Management (20 pts) ───────────────────────────────
    if cat_col:
        sub_expenses = df[(df[amount_col] < 0) & (df[cat_col].str.lower().str.contains("sub", na=False))][amount_col].abs().sum()
        sub_ratio    = sub_expenses / total_expense if total_expense > 0 else 0
        sub_score    = _clamp(1 - sub_ratio * 5)   # <20% on subs → full score
    else:
        sub_score = 0.7
    sub_pts = sub_score * 20

    total = round(savings_pts + budget_pts + stability_pts + sub_pts)
    total = max(0, min(100, total))

    breakdown = {
        "savings_habit":      {"score": round(savings_pts),   "max": 30, "label": _label(savings_pts,   30)},
        "budget_discipline":  {"score": round(budget_pts),    "max": 30, "label": _label(budget_pts,    30)},
        "spending_stability": {"score": round(stability_pts), "max": 20, "label": _label(stability_pts, 20)},
        "subscription_mgmt":  {"score": round(sub_pts),       "max": 20, "label": _label(sub_pts,       20)},
    }

    return {
        "total":     total,
        "breakdown": breakdown,
        "level":     _tier(total),
        "status":    "success",
        "monthlySummary": {str(k): float(v) for k, v in monthly_exp.to_dict().items()} if 'monthly_exp' in locals() else {}
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _label(score: float, max_score: int) -> str:
    ratio = score / max_score
    if ratio >= 0.85:
        return "Excellent"
    elif ratio >= 0.65:
        return "Good"
    elif ratio >= 0.45:
        return "Fair"
    return "Needs Work"


def _tier(total: int) -> Dict[str, str]:
    if total >= 80:
        return {"name": "Budget Master", "level": 3, "color": "#10b981", "badge": "🏆"}
    elif total >= 55:
        return {"name": "Smart Planner", "level": 2, "color": "#f59e0b", "badge": "⭐"}
    return {"name": "Beginner Saver", "level": 1, "color": "#6366f1", "badge": "🌱"}


def _empty_score(reason: str) -> Dict[str, Any]:
    return {
        "total": 0,
        "breakdown": {},
        "level": _tier(0),
        "status": "no_data",
        "message": reason,
    }


# ── Subscription detection ─────────────────────────────────────────────────

def detect_subscriptions(user_id: Optional[str] = None, tolerance: float = 0.05) -> Dict[str, Any]:
    """
    Heuristically detect recurring charges (subscriptions) by finding
    merchant+amount combos that repeat across multiple months.
    """
    df = _load_df_smart(user_id)
    if df is None or df.empty:
        return {"items": [], "monthly_total": 0}

    # Normalized columns
    date_col = "date"
    amount_col = "amount"
    cat_col = "category"
    
    # For merchant, we can use the specialized detector or fallback
    from app.tools.enhanced_csv_tools import _merchant_column
    merchant_col = _merchant_column(df)
    if not merchant_col:
        return {"items": [], "monthly_total": 0}

    # Separate expenses and add temporary month col for grouping
    expenses = df[df[amount_col] < 0].copy()
    if expenses.empty:
        return {"items": [], "monthly_total": 0}

    expenses["__month"] = expenses[date_col].dt.to_period("M")
    
    # Round amount to nearest 10 for fuzzy grouping
    expenses["__bucket"] = expenses[amount_col].abs().apply(lambda x: round(x / 10) * 10)

    grouped = (
        expenses.groupby([merchant_col, "__bucket"])["__month"]
        .nunique()
        .reset_index()
    )
    grouped.columns = ["merchant", "amount_bucket", "months_seen"]

    min_months = 2
    subs = grouped[grouped["months_seen"] >= min_months].copy()
    subs = subs.sort_values("amount_bucket", ascending=False)

    items = [
        {
            "merchant":    str(r["merchant"]),
            "amount":      float(r["amount_bucket"]),
            "months_seen": int(r["months_seen"]),
            "category":    "Subscriptions",
            "flag":        "⚠️" if r["amount_bucket"] > 500 else "",
        }
        for _, r in subs.iterrows()
    ]

    monthly_total = sum(i["amount"] for i in items)
    return {"items": items, "monthly_total": round(monthly_total, 2)}
