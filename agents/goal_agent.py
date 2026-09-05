"""
Goal-Modeling Agent: Calculates inflation-adjusted savings targets and wealth projections.
Fulfills PS 7 requirement: Goal-Based Investing logic with inflation and market returns.
"""
from typing import Dict, Any, Optional
from datetime import datetime, date

class GoalModelingAgent:
    """
    Calculates exactly how much a user needs to save per day to reach a target
    based on inflation (6% default) and market returns (12% default).
    """

    def __init__(self, default_inflation: float = 0.06, default_return: float = 0.12):
        self.default_inflation = default_inflation
        self.default_return = default_return

    def calculate_daily_target(
        self,
        target_amount: float,
        current_savings: float,
        target_date: str,  # Format: YYYY-MM-DD
        inflation_rate: Optional[float] = None,
        expected_return: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate the daily savings requirement to reach a target amount.
        Accounts for inflation (purchasing power) and investment returns.
        """
        inf = inflation_rate if inflation_rate is not None else self.default_inflation
        ret = expected_return if expected_return is not None else self.default_return

        try:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            today = date.today()
            
            # 1. Calculate time horizon in years and days
            delta = target_dt - today
            days_remaining = delta.days
            
            if days_remaining <= 0:
                return {"error": "Target date must be in the future", "status": "error"}
            
            years_remaining = days_remaining / 365.25
            
            # 2. Adjust target for INFATION (Purchasing Power)
            # Factoring in how much the 'cost' of the goal will rise
            inflation_adjusted_target = target_amount * ((1 + inf) ** years_remaining)
            
            # 3. Calculate Daily Savings required using Compound Interest
            # Formula: Sink Fund PMT = (FV - PV*(1+r)^n) * (r / [(1+r)^n - 1])
            # where FV = inf_adj_target, PV = current_savings, r = daily return rate, n = days
            
            daily_ret = (1 + ret) ** (1/365.25) - 1
            
            # Growth of current savings
            future_value_of_current = current_savings * ((1 + daily_ret) ** days_remaining)
            
            # Remaining gap to cover via new savings
            gap_to_fill = max(0, inflation_adjusted_target - future_value_of_current)
            
            if gap_to_fill == 0:
                return {
                    "daily_target": 0,
                    "total_required": inflation_adjusted_target,
                    "days_remaining": days_remaining,
                    "message": "Goal already reached via projected growth of current savings!"
                }
            
            # PMT formula for daily contributions
            # PMT = Gap * r / ((1+r)^n - 1)
            daily_target = gap_to_fill * daily_ret / (((1 + daily_ret) ** days_remaining) - 1)
            
            return {
                "daily_target": round(daily_target, 2),
                "monthly_target": round(daily_target * 30.44, 2),
                "inflation_adjusted_target": round(inflation_adjusted_target, 2),
                "gap_to_fill": round(gap_to_fill, 2),
                "days_remaining": days_remaining,
                "years_remaining": round(years_remaining, 2),
                "inflation_rate_used": inf,
                "expected_return_used": ret,
                "status": "success"
            }

        except Exception as e:
            return {"error": str(e), "status": "error"}

    def get_goal_summary(self, goal_data: Dict[str, Any]) -> str:
        """Helper to generate a human-readable summary for the AI Advisor"""
        if goal_data.get("status") == "error":
            return f"Error calculating goal requirements: {goal_data.get('error')}"
        
        return (
            f"To reach your goal of ₹{goal_data['inflation_adjusted_target']:,.0f} (inflation-adjusted) "
            f"in {goal_data['years_remaining']} years, you need to save **₹{goal_data['daily_target']:,.0f} per day** "
            f"(assuming {goal_data['expected_return_used']*100:.1f}% annual returns)."
        )
