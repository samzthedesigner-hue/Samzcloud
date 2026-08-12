"""
Decision Simulation Engine
Monte Carlo, Bayesian, risk analysis for decision making.
"""

import json
import math
import random
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional

class DecisionSimulator:
    def __init__(self, storage_engine, groq_client):
        self.storage = storage_engine
        self.groq = groq_client
    
    def simulate_decision(self, decision: str, options: List[str],
                          factors: Dict, historical: List[Dict] = None,
                          simulations: int = 1000) -> Dict:
        results = {}
        
        for option in options:
            mc = self._monte_carlo(option, factors, historical, simulations)
            risk = self._risk_assessment(option, factors)
            
            results[option] = {
                "monte_carlo": mc,
                "risk": risk
            }
        
        ranked = self._rank_options(results)
        
        return {
            "decision": decision,
            "simulations": simulations * len(options),
            "results": results,
            "ranking": ranked,
            "recommendation": ranked[0] if ranked else None
        }
    
    def _monte_carlo(self, option: str, factors: Dict, history: List[Dict], n: int) -> Dict:
        base_prob = 0.5
        if history:
            successes = sum(1 for h in history if h.get("success", False))
            base_prob = successes / len(history) if history else 0.5
        
        outcomes = []
        for _ in range(n):
            prob = max(0.01, min(0.99, random.gauss(base_prob, 0.15)))
            success = random.random() < prob
            value = random.gauss(
                factors.get("success_value", 100) if success else factors.get("failure_cost", -50),
                factors.get("std", 20)
            )
            outcomes.append({"success": success, "value": round(value, 2)})
        
        successes = sum(1 for o in outcomes if o["success"])
        values = [o["value"] for o in outcomes]
        sorted_vals = sorted(values)
        
        return {
            "success_probability": round(successes / n * 100, 1),
            "expected_value": round(statistics.mean(values), 2),
            "best_case": round(max(values), 2),
            "worst_case": round(min(values), 2),
            "value_at_risk_95": round(sorted_vals[int(n * 0.05)], 2)
        }
    
    def _risk_assessment(self, option: str, factors: Dict) -> Dict:
        risks = []
        budget = factors.get("budget", 0)
        if budget:
            exposure = min(budget * 0.3, 500)
            risks.append({"type": "financial", "exposure": round(exposure, 2),
                         "level": "high" if exposure > 1000 else "medium" if exposure > 500 else "low"})
        
        time = factors.get("time_horizon_days", 30)
        risks.append({"type": "time", "days": time,
                     "level": "high" if time > 90 else "medium" if time > 30 else "low"})
        
        scores = {"low": 1, "medium": 2, "high": 3}
        overall = statistics.mean([scores[r["level"]] for r in risks]) if risks else 1
        
        return {"risks": risks, "overall_score": round(overall, 1),
                "level": "high" if overall > 2.3 else "medium" if overall > 1.6 else "low"}
    
    def _rank_options(self, results: Dict) -> List[Dict]:
        scored = []
        for option, data in results.items():
            mc = data["monte_carlo"]
            score = mc.get("expected_value", 0) * 0.5 + mc.get("success_probability", 50) * 0.3 - data["risk"]["overall_score"] * 10
            scored.append({"option": option, "score": round(score, 2),
                          "success_pct": mc.get("success_probability"),
                          "risk": data["risk"]["level"]})
        return sorted(scored, key=lambda x: x["score"], reverse=True)
