"""
Spending Prediction & Budget Forecasting for Co Penny.
Uses simple linear regression on monthly totals per category.
"""
import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional


def _load_df_smart(user_id: Optional[str] = None) -> Optional[pd.DataFrame]:
    from app.tools.enhanced_csv_tools import load_user_data_smart
    return load_user_data_smart(user_id)


def _simple_linear_forecast(values: List[float], steps: int = 1) -> List[float]:
    """Linear regression on a list of values, return `steps` future predictions."""
    n = len(values)
    if n < 2:
        return [values[-1]] * steps if values else [0.0] * steps
    x  = np.arange(n, dtype=float)
    y  = np.array(values, dtype=float)
    # normal equations
    x_mean = x.mean()
    y_mean = y.mean()
    denom  = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return [y_mean] * steps
    slope  = ((x - x_mean) * (y - y_mean)).sum() / denom
    intercept = y_mean - slope * x_mean
    return [max(0.0, slope * (n + i) + intercept) for i in range(steps)]


def predict_next_month(user_id: Optional[str] = None, budget_limit: float = 50000.0) -> Dict[str, Any]:
    """
    Predict total spending for the next month using linear regression.
    Returns prediction, breakdown by category, and budget alert.
    """
    df = _load_df_smart(user_id)
    if df is None or df.empty:
        return {"status": "no_data", "message": "No transaction data found."}

    # Normalized columns after smart load
    date_col = "date"
    amount_col = "amount"
    cat_col = "category"

    # Only look at expenses (negative amounts)
    expenses = df[df[amount_col] < 0].copy()
    # Absolute values for simple forecast
    expenses[amount_col] = expenses[amount_col].abs()

    expenses["__month"] = expenses[date_col].dt.to_period("M").astype(str)

    # Overall monthly totals
    monthly_totals = expenses.groupby("__month")[amount_col].sum().sort_index()
    all_months     = sorted(monthly_totals.index.tolist())

    if len(all_months) < 2:
        predicted_total = float(monthly_totals.iloc[-1])
    else:
        predicted_total = _simple_linear_forecast(monthly_totals.values.tolist(), steps=1)[0]

    predicted_total = round(predicted_total, 2)
    over_budget = predicted_total > budget_limit
    excess      = round(predicted_total - budget_limit, 2) if over_budget else 0.0

    # Category-level predictions
    category_predictions = []
    if cat_col:
        for cat, grp in expenses.groupby(cat_col):
            monthly_cat = grp.groupby("__month")[amount_col].sum().reindex(all_months, fill_value=0)
            cat_values  = monthly_cat.values.tolist()
            pred        = _simple_linear_forecast(cat_values, steps=1)[0]
            category_predictions.append({
                "category":   str(cat),
                "predicted":  round(pred, 2),
                "avg_monthly": round(float(monthly_cat.mean()), 2),
            })

    category_predictions.sort(key=lambda x: x["predicted"], reverse=True)

    # Smart budget alert message
    if over_budget:
        alert = (
            f"⚠️ Based on your spending pattern, you may exceed your "
            f"₹{budget_limit:,.0f} monthly budget by ₹{excess:,.0f} next month."
        )
        top_savings = category_predictions[:2]
        if top_savings:
            cuts = ", ".join(
                [f"{c['category']} (₹{c['predicted']:,.0f})" for c in top_savings]
            )
            alert += f" Consider reducing: {cuts}."
    else:
        saved = round(budget_limit - predicted_total, 2)
        alert = (
            f"✅ You're on track! Predicted spend is ₹{predicted_total:,.0f}, "
            f"leaving ₹{saved:,.0f} under budget."
        )

    # Find coffee / daily habits if present
    coffee_pred = next((c for c in category_predictions if "coffee" in c["category"].lower()), None)
    coffee_tip  = None
    if coffee_pred and len(all_months) > 0:
        daily_rate = coffee_pred["predicted"] / 30
        for days in [15, 20, 25]:
            if daily_rate * days > 2000:
                coffee_tip = (
                    f"☕ At your current coffee spending rate, you will exceed ₹2,000 "
                    f"in this category by day {days}."
                )
                break

    return {
        "status":                 "success",
        "predicted_total":        float(predicted_total),
        "budget_limit":           float(budget_limit),
        "over_budget":            bool(over_budget),
        "excess":                 float(excess),
        "alert":                  str(alert),
        "coffee_tip":             str(coffee_tip) if coffee_tip else None,
        "category_predictions":   category_predictions[:8],
        "monthly_history":        [
            {"month": str(m), "spent": round(float(v), 2)}
            for m, v in zip(all_months, monthly_totals.values)
        ],
    }
