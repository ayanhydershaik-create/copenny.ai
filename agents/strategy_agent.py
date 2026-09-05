"""
Strategy Agent: Generates investment strategies based on knowledge and context.
Adaptive/RL-Enabled: Learns from user feedback to refine prescriptive insights.
"""
import os
import json
from typing import Dict, Any, List, Optional
from llm.llm_client import LLMClient


class StrategyAgent:
    """
    Generates investment strategies by combining:
    - Retrieved knowledge from VectorDB
    - User risk profile
    - Current market context
    - Transaction patterns (if available)
    - REINFORCEMENT FEEDBACK (Human-in-the-loop adaptation)
    """
    
    def __init__(self, llm_client: LLMClient = None, user_id: Optional[str] = None):
        self.llm_client = llm_client or LLMClient()
        self.user_id = user_id
        # State directory for RL user preferences
        self.state_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "user_preferences")
        os.makedirs(self.state_dir, exist_ok=True)

    def _get_user_preference_path(self) -> str:
        safe_id = self.user_id or "default_user"
        return os.path.join(self.state_dir, f"{safe_id}_rl_state.json")

    def _load_rl_state(self) -> Dict[str, Any]:
        path = self._get_user_preference_path()
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"bias": "neutral", "risk_adjustment": 0.0, "feedback_count": 0}

    def update_feedback(self, feedback_type: str):
        """
        REINFORCEMENT LEARNING: Update model state based on user reward/penalty.
        Feedback types: 'too_risky', 'too_conservative', 'helpful'
        """
        state = self._load_rl_state()
        state["feedback_count"] += 1
        
        if feedback_type == "too_risky":
            state["risk_adjustment"] -= 0.1 # Nudge towards conservative
            state["bias"] = "conservative_tilt"
        elif feedback_type == "too_conservative":
            state["risk_adjustment"] += 0.1 # Nudge towards aggressive
            state["bias"] = "aggressive_tilt"
        elif feedback_type == "helpful":
            # Positive reinforcement
            pass
            
        with open(self._get_user_preference_path(), 'w') as f:
            json.dump(state, f)
        print(f"🔄 RL State Updated for {self.user_id}: {state}")

    def generate_strategy(
        self,
        user_query: str,
        knowledge_context: List[Dict[str, Any]],
        risk_profile: Dict[str, Any] = None,
        transaction_summary: Dict[str, Any] = None,
        market_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate investment strategy recommendation with RL-adaptive weighting.
        """
        # Load RL-driven user preference state
        rl_state = self._load_rl_state()
        
        # Build knowledge context string
        knowledge_text = ""
        if knowledge_context:
            knowledge_text = "RELEVANT KNOWLEDGE:\n"
            for i, chunk in enumerate(knowledge_context[:5], 1):
                knowledge_text += f"\n[{i}] {chunk.get('content', '')}\n"
        
        # Build risk profile context
        risk_text = ""
        if risk_profile:
            curr_risk = risk_profile.get('risk_tolerance', 'moderate')
            risk_text = f"\nUSER RISK PROFILE:\n"
            risk_text += f"- Baseline Tolerance: {curr_risk}\n"
            risk_text += f"- Adaptive RL Adjustment: {rl_state['bias']} (Factor: {rl_state['risk_adjustment']})\n"
        
        # Build transaction context
        transaction_text = ""
        if transaction_summary:
            transaction_text = f"\nTRANSACTION PATTERNS:\n"
            transaction_text += f"- Monthly spending: {transaction_summary.get('monthly_spend', 'N/A')}\n"
            transaction_text += f"- Top categories: {transaction_summary.get('top_categories', [])}\n"
        
        prompt = f"""You are an advanced financial strategy advisor powered by Reinforcement Learning.

### REINFORCEMENT LEARNING CONTEXT:
- The system has detected a '{rl_state['bias']}' preference from the user. 
- Adjust your recommendations accordingly to remain PREDICTIVE, PRESCRIPTIVE, and ADAPTIVE.

### FAIRNESS & BIAS MITIGATION PROTOCOL:
- Provide OBJECTIVE advice based on financial data. 
- Scan for and remove any demographic/proxy bias.
- If data is missing, prioritize safety and transparency.

USER QUERY: {user_query}

{knowledge_text}

{risk_text}

{transaction_text}

Generate a prescriptive strategy recommendation in JSON format:
{{
    "strategy_summary": "...",
    "recommendations": [
        {{
            "category": "...",
            "allocation_percentage": number,
            "rationale": "...",
            "adaptive_note": "How RL feedback influenced this"
        }}
    ],
    "action_items": [],
    "xai_trace": "Methodological proof of unbiased logic",
    "fairness_score": 1.0
}}"""
        
        try:
            response = self.llm_client.complete(prompt)
            
            # Extract JSON
            import json
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"strategy_summary": response[:200], "recommendations": []}
        except Exception as e:
            return {"error": str(e), "strategy_summary": "Error generating strategy"}
