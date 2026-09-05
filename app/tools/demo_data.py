"""
Demo Data Generator for Co Penny
Generates realistic sample transaction data for live demonstrations and testing.
"""
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

# ── constants ────────────────────────────────────────────────────────────────

DEMO_USER_ID = "demo_user"

CATEGORIES = {
    "Food & Dining":    {"min": 200,  "max": 1500, "freq": 15, "emoji": "🍽️"},
    "Transportation":  {"min": 50,   "max": 800,  "freq": 20, "emoji": "🚗"},
    "Entertainment":   {"min": 300,  "max": 2000, "freq": 4,  "emoji": "🎬"},
    "Shopping":        {"min": 500,  "max": 5000, "freq": 6,  "emoji": "🛍️"},
    "Healthcare":      {"min": 200,  "max": 3000, "freq": 2,  "emoji": "🏥"},
    "Utilities":       {"min": 500,  "max": 2500, "freq": 1,  "emoji": "💡"},
    "Education":       {"min": 1000, "max": 8000, "freq": 1,  "emoji": "📚"},
    "Groceries":       {"min": 300,  "max": 2000, "freq": 8,  "emoji": "🛒"},
    "Coffee & Cafe":   {"min": 100,  "max": 500,  "freq": 12, "emoji": "☕"},
    "Subscriptions":   {"min": 99,   "max": 500,  "freq": 3,  "emoji": "📱"},
}

MERCHANTS = {
    "Food & Dining":   ["Zomato", "Swiggy", "Pizza Hut", "Dominos", "Subway"],
    "Transportation":  ["Ola", "Uber", "IRCTC", "IndiGo Airlines", "Metro Card"],
    "Entertainment":   ["PVR Cinemas", "BookMyShow", "Disney+ Hotstar", "Netflix"],
    "Shopping":        ["Amazon", "Flipkart", "Myntra", "H&M", "Reliance Trends"],
    "Healthcare":      ["Apollo Pharmacy", "MedPlus", "Practo", "1mg"],
    "Utilities":       ["BESCOM", "Airtel", "Jio Postpaid", "Aquaguard"],
    "Education":       ["Udemy", "Coursera", "Unacademy", "BYJU's"],
    "Groceries":       ["BigBasket", "Blinkit", "DMart", "Spencer's", "Nature's Basket"],
    "Coffee & Cafe":   ["Starbucks", "Café Coffee Day", "Blue Tokai", "Third Wave Coffee"],
    "Subscriptions":   ["Netflix", "Spotify", "Amazon Prime", "YouTube Premium", "GitHub"],
}

INCOME_SOURCES = [
    {"merchant": "Company Salary", "amount": 65000, "day": 1},
    {"merchant": "Freelance Payment", "amount": 15000, "day": 15},
    {"merchant": "Interest Credit", "amount": 1200, "day": 5},
]

SUBSCRIPTIONS_FIXED = [
    {"merchant": "Netflix", "amount": 199, "category": "Subscriptions"},
    {"merchant": "Spotify", "amount": 119, "category": "Subscriptions"},
    {"merchant": "Amazon Prime", "amount": 149, "category": "Subscriptions"},
    {"merchant": "GitHub Copilot", "amount": 830, "category": "Subscriptions"},
]

# ── generator ─────────────────────────────────────────────────────────────────

def generate_demo_transactions(months: int = 6) -> pd.DataFrame:
    """Generate realistic demo transaction data for `months` months."""
    rng = np.random.default_rng(42)  # reproducible
    rows: List[Dict[str, Any]] = []

    end_date   = datetime(2026, 3, 8)
    start_date = end_date - timedelta(days=30 * months)
    current    = start_date

    while current <= end_date:
        # ── Income ─────────────────────────────────────────────────────────
        for src in INCOME_SOURCES:
            if current.day == src["day"] or (current.day == 1 and src["day"] == 1):
                rows.append({
                    "date":     current.strftime("%Y-%m-%d"),
                    "amount":   src["amount"] + int(rng.integers(-2000, 2001)),
                    "category": "Income",
                    "merchant": src["merchant"],
                    "type":     "income",
                })

        # ── Fixed subscriptions on 5th ──────────────────────────────────
        if current.day == 5:
            for sub in SUBSCRIPTIONS_FIXED:
                rows.append({
                    "date":     current.strftime("%Y-%m-%d"),
                    "amount":   -sub["amount"],
                    "category": sub["category"],
                    "merchant": sub["merchant"],
                    "type":     "expense",
                })

        # ── Variable expenses ───────────────────────────────────────────
        for cat, cfg in CATEGORIES.items():
            if cat == "Subscriptions":
                continue  # handled above
            # Poisson-distributed number of transactions per day for each category
            expected_per_day = cfg["freq"] / 30
            n = int(rng.poisson(expected_per_day))
            for _ in range(n):
                amt = int(rng.integers(cfg["min"], cfg["max"] + 1))
                merchant = rng.choice(MERCHANTS[cat])
                rows.append({
                    "date":     current.strftime("%Y-%m-%d"),
                    "amount":   -amt,
                    "category": cat,
                    "merchant": merchant,
                    "type":     "expense",
                })

        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["date"]   = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df.sort_values("date").reset_index(drop=True)


def get_demo_csv_path() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "state", "models", "user_data"))
    demo_dir = os.path.join(base, DEMO_USER_ID)
    os.makedirs(demo_dir, exist_ok=True)
    return os.path.join(demo_dir, "transactions.csv")


def ensure_demo_data() -> str:
    """Ensure demo CSV exists; generate it if not. Returns the CSV path."""
    path = get_demo_csv_path()
    if not os.path.exists(path):
        df = generate_demo_transactions(months=6)
        df.to_csv(path, index=False)
    return path


def get_demo_summary() -> Dict[str, Any]:
    """Return a pre-computed summary dict for the demo user."""
    path = ensure_demo_data()
    df   = pd.read_csv(path, parse_dates=["date"])

    expenses = df[df["type"] == "expense"].copy()
    income   = df[df["type"] == "income"].copy()

    total_expense = expenses["amount"].abs().sum()
    total_income  = income["amount"].sum()
    balance       = total_income - total_expense

    # Monthly breakdown (last 6 months)
    expenses["month"] = expenses["date"].dt.to_period("M").astype(str)
    monthly = expenses.groupby("month")["amount"].apply(lambda x: x.abs().sum()).reset_index()
    monthly.columns = ["month", "spent"]

    # Category breakdown
    cat_breakdown = (
        expenses.groupby("category")["amount"]
        .apply(lambda x: x.abs().sum())
        .sort_values(ascending=False)
        .head(8)
        .to_dict()
    )

    # Top subscriptions
    subs = expenses[expenses["category"] == "Subscriptions"].groupby("merchant")["amount"].apply(lambda x: x.abs().mean()).to_dict()

    return {
        "balance":       round(float(balance), 2),
        "total_income":  round(float(total_income), 2),
        "total_expense": round(float(total_expense), 2),
        "monthly":       monthly.to_dict("records"),
        "categories":    {k: round(float(v), 2) for k, v in cat_breakdown.items()},
        "subscriptions": {k: round(float(v), 2) for k, v in subs.items()},
        "transaction_count": int(len(df)),
        "has_data": True,
    }
