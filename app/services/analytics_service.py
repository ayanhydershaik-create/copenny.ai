import os
import pandas as pd
from typing import List, Dict, Any, Optional
from app.tools.enhanced_csv_tools import get_user_csv_path

class AnalyticsEngine:
    def calculate_metrics(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch transaction data and compute financial analytics.
        """
        from app.tools.enhanced_csv_tools import load_user_data_smart
        df = load_user_data_smart(user_id)
        
        if df is None or df.empty:
            return self._empty_response()
            
        try:
            amount_col = "amount" # Always 'amount' after smart load
            date_col = "date"     # Always 'date' after smart load
            cat_col = "category"  # Always 'category' after smart load

            # 1. Monthly Spending Summary (Most recent month WITH expenses)
            expenses_only = df[df[amount_col] < 0]
            if not expenses_only.empty:
                latest_expense_date = expenses_only[date_col].max()
                # Get the start of the month containing the latest expense
                latest_month_start = latest_expense_date.replace(day=1)
                latest_month_df = df[df[date_col] >= latest_month_start]
            else:
                # Fallback to overall data if no negative expenses found after smart load
                latest_month_df = df
            
            # Group by normalized category for the selected month
            expenses_df = latest_month_df[latest_month_df[amount_col] < 0]
            
            if expenses_df.empty:
                # Final fallback: Categorize based on ALL data if the month is somehow empty of expenses
                if not expenses_only.empty:
                    # Use all expenses in history
                    summary = expenses_only.groupby(cat_col)[amount_col].sum().abs().to_dict()
                else:
                    # Treat everything as miscellaneous (positive-only user)
                    summary = {"Miscellaneous": abs(latest_month_df[amount_col].sum())}
            else:
                summary = expenses_df.groupby(cat_col)[amount_col].sum().abs().to_dict()
            
            total_spent = sum(summary.values())
            
            # 2. Spending Percentages
            percentages = {k: round((v / total_spent) * 100, 1) if total_spent > 0 else 0 for k, v in summary.items()}
            
            # 3. Top Spending Category
            top_category = max(summary, key=summary.get) if summary and total_spent > 0 else "Unknown"
            
            # 4. Financial Health Score
            health_score = self._compute_health_score(df, summary, total_spent)
            
            # 5. Potential Monthly Savings
            potential_savings = 0
            if total_spent > 0:
                for cat, amt in summary.items():
                    if amt > total_spent * 0.3: # > 30%
                        potential_savings += amt * 0.1 # 10% reduction recommendation
            
            return {
                "financialHealthScore": health_score,
                "topSpendingCategory": top_category,
                "potentialSavings": round(potential_savings, 2),
                "monthlySummary": {str(k): round(v, 2) for k, v in summary.items()},
                "percentages": {str(k): v for k, v in percentages.items()},
                "totalSpent": round(total_spent, 2),
                "has_data": True
            }
            
        except Exception as e:
            print(f"Analytics calculation error: {e}")
            return self._empty_response()

    def _compute_health_score(self, df: pd.DataFrame, summary: dict, total_spent: float) -> int:
        """
        Scoring logic (out of 100):
        Savings discipline -> 30
        Budget balance -> 30
        Spending stability -> 20
        Subscription control -> 20
        """
        score = 0
        
        # Savings discipline (Placeholder: Ratio of income vs expense if possible)
        # For now, base it on total volume vs a generic limit
        if total_spent < 50000: score += 25
        elif total_spent < 100000: score += 15
        else: score += 5
        
        # Budget balance (Number of categories > 30%)
        over_budget_cats = [c for c, a in summary.items() if a > total_spent * 0.3]
        if not over_budget_cats: score += 30
        elif len(over_budget_cats) == 1: score += 20
        else: score += 10
        
        # Spending stability (Transaction count density)
        if len(df) > 50: score += 20
        elif len(df) > 20: score += 10
        else: score += 5
        
        # Subscription control (Detecting common recurring patterns - simple mock)
        sub_words = ['netflix', 'spotify', 'amazon prime', 'subscriptions']
        sub_count = sum(1 for c in summary.keys() if any(w in c.lower() for w in sub_words))
        if sub_count < 3: score += 20
        elif sub_count < 6: score += 10
        else: score += 5
        
        return min(100, score + 5) # Base 5 points

    def _empty_response(self) -> Dict[str, Any]:
        return {
            "financialHealthScore": 0,
            "topSpendingCategory": "N/A",
            "potentialSavings": 0,
            "monthlySummary": {},
            "percentages": {},
            "totalSpent": 0,
            "has_data": False
        }

# Global singleton
analytics_engine = AnalyticsEngine()
