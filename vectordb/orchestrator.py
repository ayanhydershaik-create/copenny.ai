import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from llm.llm_client import LLMClient
from llm.prompts import system_advisor
from llm.json_guard import validate_json_response
from app.tools.csv_tools import query_csv, spend_aggregate, top_merchants, describe_csv
from app.tools.visualization import generate_visualizations, generate_dynamic_visualizations
from app.tools.enhanced_csv_tools import (
    total_spend,
    monthly_spend,
    daily_spend,
    category_stats,
    merchant_stats,
    time_coverage,
)

# VectorDB and Agent imports
try:
    from vectordb.knowledge_store import get_knowledge_store
    from agents.parsing_agent import ParsingAgent
    from agents.strategy_agent import StrategyAgent
    from agents.risk_agent import RiskAgent
    from agents.output_agent import OutputAgent
    from agents.analysis_agent import AnalysisAgent
    from agents.implementation_agent import ImplementationAgent
    from agents.goal_agent import GoalModelingAgent
    from agents.nudge_agent import NudgeAgent
    VECTORDB_AVAILABLE = True
except ImportError:
    VECTORDB_AVAILABLE = False
    get_knowledge_store = None
    ParsingAgent = None
    StrategyAgent = None
    RiskAgent = None
    OutputAgent = None
    AnalysisAgent = None
    ImplementationAgent = None

class EnhancedOrchestrator:
    def __init__(self):
        self.llm_client = LLMClient()
        
        # Initialize VectorDB components if available
        if VECTORDB_AVAILABLE:
            try:
                self.knowledge_store = get_knowledge_store()
                self.parsing_agent = ParsingAgent(self.llm_client)
                self.strategy_agent = StrategyAgent(self.llm_client)
                self.risk_agent = RiskAgent(self.llm_client)
                self.output_agent = OutputAgent()
                self.analysis_agent = AnalysisAgent() if AnalysisAgent else None
                self.implementation_agent = ImplementationAgent() if ImplementationAgent else None
                self.goal_agent = GoalModelingAgent() if GoalModelingAgent else None
                self.nudge_agent = NudgeAgent(self.goal_agent) if NudgeAgent else None
                self.use_vectordb = False # Streamlined for speed
            except Exception as e:
                print(f"Warning: VectorDB initialization failed: {e}. Continuing without VectorDB.")
                self.use_vectordb = False
                self.analysis_agent = None
        else:
            self.use_vectordb = False
            self.analysis_agent = None
        
    def _extract_year_month(self, message: str) -> tuple:
        """Extract year and optional month integer from free-form text."""
        import re
        msg = message.lower()
        # Year: any 4-digit between 1900-2099
        year = None
        m = re.search(r"\b(19\d{2}|20\d{2})\b", msg)
        if m:
            year = int(m.group(1))
        # Month by number or name
        month = None
        # numeric MM or M
        mnum = re.search(r"\b(1[0-2]|0?[1-9])\s*(?:/|-|\\s|,|\b)\s*(?:'?(?:19\d{2}|20\d{2}))?\b", msg)
        # month names
        months = {
            'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
            'july':7,'august':8,'september':9,'sept':9,'october':10,'november':11,'december':12,
            'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'oct':10,'nov':11,'dec':12
        }
        for name, idx in months.items():
            if re.search(rf"\b{name}\b", msg):
                month = idx
                break
        if month is None and mnum:
            try:
                month = int(mnum.group(1))
            except Exception:
                month = None
        return year, month

    def _should_generate_charts(self, message: str) -> bool:
        """Determine if charts should be generated based on the message"""
        chart_keywords = [
            'chart', 'graph', 'plot', 'visualize', 'visualization', 'show me',
            'display', 'picture', 'image', 'diagram', 'breakdown', 'analysis',
            'trend', 'pattern', 'comparison', 'distribution', 'pie', 'bar', 'line',
            'histogram', 'monthly', 'daily', 'weekly', 'timeline', 'over time',
            'amount', 'spending', 'category', 'merchant', 'top', 'highest',
            'compare', 'vs', 'versus', 'create', 'generate', 'make', 'expenditure'
        ]
        return any(keyword in message.lower() for keyword in chart_keywords)

    async def _get_comprehensive_data_context(self, message: str, user_id: Optional[str] = None) -> tuple:
        """
        Get comprehensive data context for the LLM based on the user's question (Parallelized)
        """
        try:
            # ... (keywords list omitted for brevity in replacement, but kept intact)
            data_keywords = [
                'spending', 'expense', 'budget', 'category', 'monthly', 'historical',
                'trend', 'pattern', 'analysis', 'breakdown', 'summary', 'total',
                'how much', 'what did', 'when did', 'where did', 'merchant', 'chart',
                'graph', 'plot', 'visualize', 'show me', 'data', 'transaction', 'update',
                'dashboard', 'current', 'latest', 'status', 'tell me about', 'show',
                'spending habits', 'my money', 'financial', 'how much',
                'save', 'saving', 'savings', 'invest', 'investment', 'tip', 'tips',
                'advice', 'advise', 'help', 'suggest', 'recommend', 'money', 'income',
                'earn', 'reduce', 'cut', 'cost', 'plan', 'goal', 'debt', 'loan',
                'credit', 'insurance', 'tax', 'salary', 'pay', 'bill', 'rent',
                'subscription', 'predict', 'forecast', 'future', 'next month'
            ]
            
            if not any(keyword in message.lower() for keyword in data_keywords):
                if len(message.strip()) > 15:
                    pass
                else:
                    return "", {}
            
            # PARALLEL FETCH 1: Basic Info
            from database.firestore_service import get_firestore_service
            db = get_firestore_service()
            
            # Start multiple threads for data fetching
            csv_task = asyncio.to_thread(describe_csv, user_id=user_id)
            sub_task = asyncio.to_thread(db.get_user_subscription, user_id)
            date_range_task = asyncio.to_thread(self._get_date_range, user_id=user_id)
            
            csv_info, sub, date_range = await asyncio.gather(csv_task, sub_task, date_range_task)
            
            tier = sub.get("tier", "free")
            row_count = csv_info.get('row_estimate', 0)

            # Build context based on question type
            context_parts = []
            context_parts.append(f"USER SUBSCRIPTION TIER: {tier.upper()}")
            
            # Basic data overview
            row_count = csv_info.get('row_estimate', 0)
            print(f"DEBUG: orchestrator _get_comprehensive_data_context: user_id={user_id}, row_count={row_count}, tier={tier}") # Debug print
            
            try:
                rc = int(row_count)
            except:
                rc = 0

            if rc == 0:
                # Double check with a direct path check if row_estimate failed
                from app.tools.csv_tools import get_user_csv_path
                path = get_user_csv_path(user_id=user_id)
                if not path:
                     return "SYSTEM ALERT: NO DATA AVAILABLE. The user has NOT uploaded any transaction data. You MUST NOT provide any analysis, fake numbers, or dates. You MUST reply with exactly: 'I do not have access to your financial data yet. Please upload a CSV file in the Data Management section so I can help you.' Do not say anything else.", {}

            context_parts.append(f"DATA OVERVIEW:")
            context_parts.append(f"- Total records: {row_count}")
            context_parts.append(f"- Date range: {date_range}")
            
            # Extract year/month intent
            year, month = self._extract_year_month(message)
            
            # PARALLEL FETCH 2: Specific Analysis and Global Stats
            analysis_task = asyncio.to_thread(self._get_specific_analysis, message, user_id=user_id)
            total_spend_task = asyncio.to_thread(total_spend, user_id=user_id)
            
            specific_analysis, stats_res = await asyncio.gather(analysis_task, total_spend_task)
            
            if specific_analysis:
                context_parts.append(f"\nSPECIFIC ANALYSIS:")
                context_parts.append(specific_analysis)
            
            # Generate visualizations in parallel if needed
            visualizations = {}
            should_chart = self._should_generate_charts(message) or any(w in message.lower() for w in ["analyze", "analysis", "breakdown", "insight", "overview", "show", "plot", "chart", "graph", "visualize", "expenditure", "spending"]) or (year is not None or month is not None)
            
            if should_chart:
                try:
                    # Build filtered inputs for visualizations in parallel
                    where = ""
                    if year and month: where = f" WHERE CAST(date AS VARCHAR) LIKE '{year}-{month:02d}%'"
                    elif year: where = f" WHERE CAST(date AS VARCHAR) LIKE '{year}%'"
                    recent_sql = "SELECT date, amount FROM t" + where + " ORDER BY date ASC LIMIT 5000"
                    
                    recent_task = asyncio.to_thread(query_csv, recent_sql, limit=5000, user_id=user_id)
                    cat_task = asyncio.to_thread(category_stats, year=year, month=month, user_id=user_id)
                    merch_task = asyncio.to_thread(merchant_stats, year=year, month=month, top_n=10, user_id=user_id)
                    
                    recent_data, cat, merchants_data = await asyncio.gather(recent_task, cat_task, merch_task)
                    
                    label_parts = [str(year)] if year else []
                    if month: label_parts.append(f"{month:02d}")
                    time_label = "-".join(label_parts) if label_parts else "all time"
                    
                    recent_data = {**recent_data, "meta": {"label": time_label}}
                    spending_data = {
                        "totals": [{"key": it.get("category", "Unknown"), "spent": it.get("spent", 0.0)} for it in cat.get("items", [])],
                        "meta": {"label": time_label}
                    }
                    merchants_data = {**merchants_data, "meta": {"label": time_label}}
                    
                    visualizations = generate_dynamic_visualizations(message, spending_data, recent_data, merchants_data)
                except Exception as e:
                    print(f"Visualization error: {e}")
            
            # Goal modeling logic for context
            goal_context = ""
            if self.goal_agent:
                try:
                    # Fetch goal from risk profile or state
                    risk_profile = self.risk_agent.get_risk_profile()
                    goals = risk_profile.get("goals", [])
                    if goals:
                        # For demo, take the first goal or look for match in message
                        target_goal = goals[0] if isinstance(goals[0], dict) else {"name": "Wealth", "target": 1000000, "date": "2030-12-31"}
                        
                        # Calculate daily target
                        current_savings = stats_res.get("total", 0.0) # Assume current total is savings proxy for now
                        goal_res = self.goal_agent.calculate_daily_target(
                            target_amount=target_goal.get("target", 1000000),
                            current_savings=current_savings,
                            target_date=target_goal.get("date", "2030-12-31")
                        )
                        if goal_res.get("status") == "success":
                            goal_context = f"\nGOAL ARCHITECT DATA:\n- Target Goal: {target_goal.get('name')}\n- Daily Savings Target: ₹{goal_res['daily_target']}\n- Inflation Adjusted Cost: ₹{goal_res['inflation_adjusted_target']:,.0f}\n"
                            
                            # Add tradeoff nudge if message mentions a potential purchase
                            spend_match = re.search(r"₹?(\d+(?:,\d+)?)\b", message)
                            if spend_match and any(w in message.lower() for w in ["buy", "cost", "purchase", "shopping", "item"]):
                                amount = float(spend_match.group(1).replace(",", ""))
                                nudge_res = self.nudge_agent.analyze_tradeoff(
                                    spending_amount=amount,
                                    goal_target=target_goal.get("target", 1000000),
                                    current_savings=current_savings,
                                    target_date=target_goal.get("date", "2030-12-31")
                                )
                                if nudge_res.get("status") != "error":
                                    goal_context += f"- Spending Tradeoff: {nudge_res['nudge_text']}\n"
                                    goal_context += f"- Wealth Impact: You'll need to save ₹{nudge_res['daily_increase']:.0f} more per day for next {nudge_res['days_remaining']} days to stay on track.\n"
                except Exception as ge:
                    print(f"Goal context generation error: {ge}")

            analysis = "\n".join(context_parts) + goal_context
            return analysis, visualizations
            
        except Exception as e:
            return f"Error analyzing transaction data: {str(e)}", {}

    def _get_date_range(self, user_id: Optional[str] = None) -> str:
        """Get the date range of the transaction data"""
        try:
            cov = time_coverage(user_id=user_id)
            if cov.get("min") or cov.get("max"):
                return f"{cov.get('min', 'Unknown')} to {cov.get('max', 'Unknown')}"
            return "Unknown"
        except Exception as e:
            print(f"Date range error: {e}")
            return "Unknown"

    def _get_specific_analysis(self, message: str, user_id: Optional[str] = None) -> str:
        """Get specific analysis based on the user's question - optimized for accuracy and tool usage"""
        try:
            message_lower = message.lower()
            year, month = self._extract_year_month(message)
            
            # Always try to get a baseline category breakdown for financial questions
            cat_stats = category_stats(year=year, month=month, user_id=user_id)
            baseline_analysis = []
            
            if cat_stats.get('items'):
                baseline_analysis.append("CATEGORY BREAKDOWN:")
                for item in cat_stats['items'][:5]:
                    baseline_analysis.append(f"- {item['category']}: ₹{abs(item['spent']):,.0f}")
                baseline_analysis.append("")
            
            # 1. Monthly Trends
            if any(word in message_lower for word in ['monthly', 'trend', 'month', 'history', 'pattern']):
                m_spend = monthly_spend(year=year, user_id=user_id)
                if m_spend.get('items'):
                    baseline_analysis.append("MONTHLY TRENDS:")
                    for item in m_spend['items'][-6:]: # Last 6 months
                        baseline_analysis.append(f"- {item['month']}: ₹{abs(item['spent']):,.0f}")
                    baseline_analysis.append("")
            
            # 2. Merchant Analysis
            if any(word in message_lower for word in ['merchant', 'where', 'spent on', 'shop', 'vendor', 'store']):
                m_stats = merchant_stats(year=year, month=month, top_n=5, user_id=user_id)
                if m_stats.get('items'):
                    baseline_analysis.append("TOP MERCHANTS/VENDORS:")
                    for item in m_stats['items']:
                        baseline_analysis.append(f"- {item['merchant']}: ₹{abs(item['spent']):,.0f}")
                    baseline_analysis.append("")
            
            # 3. Time-based insights (First week vs others)
            if any(word in message_lower for word in ['when', 'time', 'week', 'day']):
                # This could be more complex, but a simple list is fine for now
                baseline_analysis.append("TIME ANALYSIS: Look at the day-by-day distribution to see if spending spikes at the start of the month.")
            
            return "\n".join(baseline_analysis) if baseline_analysis else "No specific data breakdown available for this query."
            
        except Exception as e:
            print(f"Error in _get_specific_analysis: {e}")
            return "Unable to retrieve detailed data breakdown."
            
            # Year/month specific analysis (generic)
            y, m = self._extract_year_month(message)
            if y is not None or m is not None:
                ts = total_spend(year=y, month=m, user_id=user_id)
                parts = [f"FILTER: year={y or 'all'} month={m or 'all'}", f"- Total spent: ₹{ts.get('total', 0.0):,.0f}"]
                cats = category_stats(year=y, month=m, user_id=user_id)
                if cats.get("items"):
                    topcats = ", ".join([f"{it['category']}: ₹{it['spent']:,.0f}" for it in cats['items'][:3]])
                    parts.append(f"- Top categories: {topcats}")
                merch = merchant_stats(year=y, month=m, top_n=3, user_id=user_id)
                if merch.get("items"):
                    topm = ", ".join([f"{it['merchant']}: ₹{it['spent']:,.0f}" for it in merch['items']])
                    parts.append(f"- Top merchants: {topm}")
                return "\n".join(parts)
            
            # Quick summary for general questions
            if any(word in message_lower for word in ['summary', 'overview', 'total', 'how much']):
                ts = total_spend(year=year, month=month, user_id=user_id)
                t_cov = time_coverage(user_id=user_id)
                baseline_analysis.append(f"TOTAL SPENDING: ₹{ts.get('total', 0):,.0f}")
                baseline_analysis.append(f"DATE RANGE: {t_cov.get('min', 'N/A')} to {t_cov.get('max', 'N/A')}")
                baseline_analysis.append("")
            
            return "\n".join(baseline_analysis) if baseline_analysis else "No specific data breakdown available for this query."
            
        except Exception as e:
            print(f"Error in _get_specific_analysis: {e}")
            return f"Error in specific analysis: {str(e)}"

    async def craft_advisor_reply(self, user_message: str, observations_text: str = "", user_id: Optional[str] = None) -> str:
        """
        Craft a detailed advisor reply with data context.
        """
        guidance = (
            "URGENT: Provide a HIGHLY DETAILED, POINTS-WISE response. "
            "Use clear bullet points for all data insights. "
            "Start with a one-paragraph 'Executive Assessment' with specific numbers. "
            "Then provide 4-6 detailed points with concrete actions grounded in data. "
            "End with one actionable 'Quick Win'. "
            "Always reference specific categories and ₹ amounts from the context."
        )
        
        # Lightweight CSV context
        try:
            meta = describe_csv(user_id=user_id)
            colnames = ", ".join([c.get("name","?") for c in meta.get("columns", [])][:12])
            data_context = f"Data columns: {colnames}."
        except Exception:
            data_context = "Data columns: (unavailable)"
        
        user_prompt = f"Data Context:\n{data_context}\nObservations:\n{observations_text}\nUser: {user_message}\n{guidance}\nFinal answer:"
        return await self.llm_client.acomplete(prompt=user_prompt, system=system_advisor)

    async def _process_with_vectordb_workflow(
        self,
        message: str,
        context: List[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process query using VectorDB workflow:
        User Query → Parsing Agent → Embedding → VectorDB Search → Strategy Agent → Risk Agent → Output Agent
        (Parallelized Async)
        """
        try:
            # Step 1: Parsing Agent - Extract intent and requirements
            parsed = self.parsing_agent.parse_query(message, context)
            
            # Step 2: Retrieve knowledge from VectorDB if needed
            knowledge_task = asyncio.to_thread(lambda: [] if not parsed.get('requires_knowledge', False) else self.knowledge_store.retrieve_knowledge(
                query=' '.join(parsed.get('keywords', [message])),
                namespace=None,
                top_k=5
            ))
            
            # Step 3: Get transaction data if needed in parallel
            transaction_summary = None
            financial_analysis = None
            if parsed.get('requires_transaction_data', False):
                try:
                    # Parallel fetching of core stats
                    total_task = asyncio.to_thread(total_spend, user_id=user_id)
                    monthly_task = asyncio.to_thread(monthly_spend, user_id=user_id)
                    categories_task = asyncio.to_thread(category_stats, user_id=user_id)
                    
                    total, monthly, categories, knowledge_context = await asyncio.gather(total_task, monthly_task, categories_task, knowledge_task)
                    
                    category_breakdown = {it.get('category', 'Unknown'): it.get('spent', 0) for it in categories.get('items', []) if it.get('spent', 0) > 0}
                    
                    transaction_summary = {
                        'total_spend': total.get('total', 0),
                        'monthly_spend': monthly.get('recent_monthly', {}).get('total', 0) if monthly else 0,
                        'top_categories': [cat.get('category') for cat in categories.get('items', [])[:5]],
                        'category_breakdown': category_breakdown,
                        'savings_rate': 0
                    }
                    
                    if self.analysis_agent:
                        financial_analysis = await asyncio.to_thread(self._run_heavy_analysis, transaction_summary, user_id)
                except Exception as e:
                    print(f"Parallel data extraction error: {e}")
                    knowledge_context = await knowledge_task
            else:
                knowledge_context = await knowledge_task

            # Step 4: Determine if this is a strategy/investment query
            query_type = parsed.get('query_type', '')
            is_investment_query = query_type in ['investment_advice', 'portfolio_question', 'market_question']
            
            if is_investment_query and knowledge_context:
                # Step 5: Strategy Agent - Generate strategy
                risk_profile = self.risk_agent.get_risk_profile()
                strategy = self.strategy_agent.generate_strategy(
                    user_query=message,
                    knowledge_context=knowledge_context,
                    risk_profile=risk_profile,
                    transaction_summary=transaction_summary,
                    market_context=None  # Could fetch real-time market data here
                )
                
                # Step 6: Risk Agent - Assess risk alignment
                risk_assessment = self.risk_agent.assess_risk(
                    strategy=strategy,
                    risk_profile=risk_profile,
                    knowledge_context=knowledge_context
                )
                
                # Step 7: Implementation Agent - Generate execution plan
                implementation_plan = None
                if self.implementation_agent:
                    try:
                        risk_tolerance = risk_profile.get("risk_tolerance", "Moderate")
                        recommendations = risk_assessment.get('adjusted_recommendations') or strategy.get('recommendations', [])
                        
                        # Extract specific products if mentioned in strategy
                        recommended_assets = []
                        for rec in recommendations:
                            if rec.get("specific_products"):
                                recommended_assets.extend(rec.get("specific_products", []))
                        
                        if recommendations:
                            implementation_plan = self.implementation_agent.generate_implementation_plan(
                                risk_profile=risk_tolerance,
                                allocation=recommendations,
                                recommended_assets=recommended_assets if recommended_assets else None
                            )
                    except Exception as e:
                        print(f"Implementation plan generation error: {e}")
                
                # Step 8: Output Agent - Format response
                response = self.output_agent.format_response(
                    user_query=message,
                    strategy=strategy,
                    risk_assessment=risk_assessment,
                    transaction_insights=transaction_summary,
                    knowledge_sources=knowledge_context
                )
                
                # Add financial analysis if available
                if financial_analysis:
                    response["financial_analysis"] = financial_analysis
                    response["type"] = "strategy_with_analysis"
                
                # Add implementation plan if available
                if implementation_plan:
                    # Format implementation plan into response
                    impl_response = self.implementation_agent.format_implementation_response(implementation_plan)
                    response["implementation_plan"] = impl_response["data"]
                    # Append implementation plan to answer
                    response["answer"] += "\n\n---\n\n" + impl_response["answer"]
                    if response["type"] == "strategy_with_analysis":
                        response["type"] = "strategy_with_analysis_and_implementation"
                    else:
                        response["type"] = "strategy_with_implementation"
                
                return response
            else:
                # For non-investment queries, use knowledge context but simpler output
                data_analysis, visualizations = self._get_comprehensive_data_context(message, user_id=user_id)
                
                # Build prompt with knowledge context
                full_prompt = f"{system_advisor}\n\n"
                
                if knowledge_context:
                    knowledge_text = "RELEVANT KNOWLEDGE:\n"
                    for i, chunk in enumerate(knowledge_context[:3], 1):
                        knowledge_text += f"\n[{i}] {chunk.get('content', '')}\n"
                    full_prompt += f"{knowledge_text}\n\n"
                
                if data_analysis:
                    full_prompt += f"TRANSACTION DATA CONTEXT:\n{data_analysis}\n\n"
                
                full_prompt += f"User Question: {message}\n\n"
                
                # Get response from LLM
                response_text = self.llm_client.complete(full_prompt)
                
                # Format with Output Agent
                response = self.output_agent.format_simple_response(
                    answer=response_text,
                    knowledge_sources=knowledge_context
                )
                
                # Add visualizations if available
                if visualizations:
                    response["visualizations"] = visualizations
                    response["type"] = "visualization"
                
                # Add financial analysis if available
                if financial_analysis:
                    response["financial_analysis"] = financial_analysis
                    if response["type"] == "visualization":
                        response["type"] = "visualization_with_analysis"
                    else:
                        response["type"] = "analysis"
                
                return response
                
        except Exception as e:
            # Fallback to original workflow on error
            print(f"VectorDB workflow error: {e}")
            return None
    
    def _run_heavy_analysis(self, transaction_summary: dict, user_id: Optional[str] = None) -> Any:
        try:
            profile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state', 'profile.json')
            profile = {}
            if os.path.exists(profile_path):
                import json
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
            
            financial_data = self.analysis_agent.extract_financial_data_from_transactions(transaction_summary, profile)
            return self.analysis_agent.analyze(financial_data, user_id=user_id)
        except Exception as e:
            print(f"Error in heavy analysis: {e}")
            return None

    def _generate_local_insight(self, data_analysis: str, message: str) -> str:
        """
        FAIL-SAFE: Generate a high-quality human-like insight locally from pre-fetched data
        when all remote LLMs are offline or rate-limited.
        """
        import re
        
        # Extract some basic stats from the analysis string if possible
        total_spend = "N/A"
        top_cats = []
        
        m_total = re.search(r"TOTAL HISTORICAL SPENDING: ₹([\d,.]+)", data_analysis)
        if m_total: total_spend = m_total.group(1)
        
        m_cats = re.findall(r"- ([\w\s]+): ₹([\d,.]+)", data_analysis)
        if m_cats: top_cats = m_cats[:3]
        
        # Build a rule-based executive response
        res = [
            "### 🛡️ Executive Data Assessment (Local Mode)",
            f"I've synchronized with your transaction history. Although our primary AI brain is experiencing high demand, I have performed a local analysis of your data context.",
            ""
        ]
        
        if total_spend != "N/A":
            res.append(f"**Key Finding:** Your total historical expenditure stands at **₹{total_spend}**. ")
        
        if top_cats:
            cat_str = ", ".join([f"**{c[0]}** (₹{c[1]})" for c in top_cats])
            res.append(f"Analyzing your distributions, your highest spending categories are {cat_str}.")
            res.append("\n**Recommended Concrete Actions:**")
            res.append(f"1. **Audit Subscriptions:** Check if any recurring charges in {top_cats[0][0]} can be optimized.")
            res.append(f"2. **Category Cap:** Consider setting a ₹2,000 weekly soft-cap for {top_cats[0][0]} to increase your potential savings.")
            res.append("3. **Budget Buffer:** Maintain a 10% cash reserve based on your average monthly velocity.")
        else:
            res.append("I have successfully retrieved your transaction metadata. Please upload more structured data or ask a specific question about your merchants to unlock deeper local insights.")
            
        res.append("\n**Quick Win:** Review the 'Data Engine' tab for any missing category labels to improve analysis precision.")
        return "\n".join(res)

    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main chat function (Natively ASYNC).
        Handles vector-search hybrid paths or falls back to direct data-grounded reasoning.
        """
        data_analysis = ""
        visualizations = {}
        try:
            # Try VectorDB workflow first if available
            if self.use_vectordb:
                vectordb_response = await self._process_with_vectordb_workflow(message, context, user_id=user_id)
                if vectordb_response:
                    return vectordb_response
            
            # Fallback to direct analytical reasoning
            context_str = ""
            if context:
                recent_context = context[-5:]
                context_str = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in recent_context])
            
            import time
            start_time = time.time()
            
            # Get comprehensive data context (Parallelized Async)
            data_analysis, visualizations = await self._get_comprehensive_data_context(message, user_id=user_id)
            
            # Create the data context for user message
            user_prompt = ""
            if data_analysis:
                user_prompt += f"TRANSACTION DATA CONTEXT:\n{data_analysis}\n\n"
            
            if context_str:
                user_prompt += f"Recent conversation:\n{context_str}\n\n"
            
            user_prompt += f"User Question: {message}\n"
            
            # Enforce POINTS-WISE requirements in the SYSTEM prompt
            system_prompt = f"{system_advisor}\n\nURGENT RESPONSE REQUIREMENTS:\n- Provide a HIGHLY DETAILED, POINTS-WISE response (minimum 5 clear bullet points).\n- Quote SPECIFIC numbers (₹ amounts, categories) from the provided context.\n- Tone: warm, executive, professional.\n- Start with a clear 'Executive Summary' and end with a 'Quick Win'."
            
            # Get response from LLM (Awaited for high speed)
            response = await self.llm_client.acomplete(prompt=user_prompt, system=system_prompt)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            response_data = {
                "answer": response,
                "status": "success",
                "type": "text",
                "latency_ms": latency_ms,
                "provider": "AI Advisor (Resilient Mode)"
            }
            
            if visualizations:
                response_data["visualizations"] = visualizations
                response_data["type"] = "visualization"
            
            # Optimized JSON parsing: FAILURE IS NOT AN ERROR ANYMORE
            try:
                json_response = validate_json_response(response)
                if json_response and "answer" in json_response:
                    response_data["answer"] = json_response["answer"]
            except Exception as json_err:
                print(f"[Orchestrator] JSON Guard caught malformed JSON, using raw text instead. Error: {json_err}")
            
            return response_data
                
        except Exception as e:
            err_msg = str(e)
            print(f"CRITICAL: LLM Failure during chat: {err_msg}")
            
            # LAST RESORT: Try to get a simple response if the complex one failed
            try:
                print("[Orchestrator] Complex query failed. Attempting Deep Recovery with simplified prompt...")
                recovery_prompt = f"Provide a short, helpful financial response to: {message}"
                recovery_response = await self.llm_client.acomplete(prompt=recovery_prompt)
                return {
                    "answer": recovery_response,
                    "status": "success",
                    "type": "text",
                    "provider": "AI Advisor (Recovery Mode)"
                }
            except Exception as final_e:
                print(f"[Orchestrator] Remote AI fully exhausted: {final_e}. Triggering Local Intelligence.")
                # ABSOLUTE FINAL SAFETY NET: Never show an error message
                local_answer = self._generate_local_insight(data_analysis, message)
                return {
                    "answer": local_answer,
                    "status": "success",
                    "type": "text",
                    "provider": "Local Intelligence Fail-Safe"
                }

# Create global instance
enhanced_orchestrator = EnhancedOrchestrator()

async def chat(message: str, context: List[Dict[str, str]] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main chat function that can be imported by other modules (Awaited)
    """
    return await enhanced_orchestrator.chat(message, context, user_id=user_id)

def craft_answer(user_message: str, observations_text: str = "") -> str:
    """
    Convenience function for backward compatibility with advisor_reply.py
    """
    return enhanced_orchestrator.craft_advisor_reply(user_message, observations_text)
