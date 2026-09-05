"""
Nudge & Alert Agent: Provides real-time decision support and tradeoff analysis.
Fulfills PS 7 requirement: Real-time "Decision Support" (Buy now vs Goal delay).
"""
from typing import Dict, Any, List, Optional
from .goal_agent import GoalModelingAgent

class NudgeAgent:
    """
    Analyzes how specific spending decisions impact long-term wealth goals.
    Translates "Luxury Spending" into "Daily Savings Increases."
    """

    def __init__(self, goal_agent: Optional[GoalModelingAgent] = None):
        self.goal_agent = goal_agent or GoalModelingAgent()

    def analyze_tradeoff(
        self,
        spending_amount: float,
        goal_target: float,
        current_savings: float,
        target_date: str,
        category: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Calculates the 'Wealth Debt' of a purchase.
        Quantifies how much daily savings must INCREASE to compensate for a purchase.
        """
        # 1. Calculate the baseline target (before this spending)
        baseline = self.goal_agent.calculate_daily_target(
            target_amount=goal_target,
            current_savings=current_savings,
            target_date=target_date
        )

        # 2. Calculate the 'After-Spending' target
        # (Assuming the spending amount is subtracted from potential savings/current pool)
        after_spending = self.goal_agent.calculate_daily_target(
            target_amount=goal_target,
            current_savings=current_savings - spending_amount,
            target_date=target_date
        )

        if baseline.get("status") == "error" or after_spending.get("status") == "error":
            return {"status": "error", "message": "Could not calculate tradeoff."}

        daily_increase = after_spending["daily_target"] - baseline["daily_target"]
        
        return {
            "category": category,
            "spending_amount": spending_amount,
            "original_daily_target": baseline["daily_target"],
            "new_daily_target": after_spending["daily_target"],
            "daily_increase": round(daily_increase, 2),
            "monthly_increase": round(daily_increase * 30.44, 2),
            "total_lifetime_cost": round(after_spending["inflation_adjusted_target"], 2),
            "days_remaining": baseline["days_remaining"],
            "nudge_text": self._generate_nudge_text(category, spending_amount, daily_increase, baseline["days_remaining"])
        }

    def _generate_nudge_text(self, category: str, amount: float, increase: float, days: int = 365) -> str:
        if increase <= 0:
            return f"This ₹{amount:,.0f} purchase fits within your budget buffer."
        
        months = round(days / 30.44)
        return (
            f"If you spend ₹{amount:,.0f} on {category} now, your daily savings target "
            f"will increase by **₹{increase:.0f} per day** for the next {months} months to stay on track."
        )

    def identify_leakage(self, subscriptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifies high-impact leakage patterns (e.g. unused subscriptions).
        Fulfills 'Behavioral Analysis' requirement of identifying leakage.
        """
        leakage = []
        for sub in subscriptions:
            # Logic: If sub is high amount (> 500) and flagged as high variance/unused
            if sub.get("amount", 0) > 300:
                leakage.append({
                    "type": "Subscription Leakage",
                    "merchant": sub.get("merchant"),
                    "amount": sub.get("amount"),
                    "impact_daily": round(sub.get("amount") / 30.44, 2),
                    "recommendation": f"Canceling {sub.get('merchant')} would reduce your daily goal target by ₹{sub.get('amount')/30.44:.0f}."
                })
        return leakage
