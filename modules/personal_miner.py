"""
Personal Data Miner & Pattern Engine
Analyzes data to find hidden patterns, correlations, and predictions.
"""

import json
import math
import statistics
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple

class PersonalMiner:
    """Mines personal data for actionable patterns."""
    
    def __init__(self, storage_engine):
        self.storage = storage_engine
        self.data_dir = "miner_data"
    
    def ingest_data(self, data_type: str, data: List[Dict]) -> Dict:
        key = f"{self.data_dir}/{data_type}_{datetime.now().strftime('%Y%m%d')}.json"
        existing = self.storage.read_file(key)
        records = json.loads(existing) if existing else []
        records.extend(data)
        self.storage.write_file(key, json.dumps(records))
        return {"ingested": len(data), "total": len(records), "type": data_type}
    
    def find_productivity_patterns(self, calendar_data: List[Dict]) -> Dict:
        hourly = defaultdict(list)
        daily = defaultdict(list)
        
        for event in calendar_data:
            try:
                start = datetime.fromisoformat(event["start"])
                end = datetime.fromisoformat(event["end"])
                duration = (end - start).total_seconds() / 3600
                
                type_score = {
                    "deep_work": 10, "meeting": 3, "creative": 8,
                    "admin": 2, "learning": 7, "break": 1
                }.get(event.get("type", "meeting"), 5)
                
                hourly[start.hour].append(type_score * min(duration, 2))
                daily[start.strftime("%A")].append(type_score * min(duration, 2))
            except:
                continue
        
        hour_scores = {}
        for hour, scores in hourly.items():
            hour_scores[hour] = {
                "avg_score": round(statistics.mean(scores), 2),
                "events": len(scores),
                "peak": len(scores) > 3 and statistics.mean(scores) > 7
            }
        
        peak_hours = sorted(
            [h for h, s in hour_scores.items() if s["peak"]],
            key=lambda h: hour_scores[h]["avg_score"], reverse=True
        )[:5]
        
        day_scores = {}
        for day, scores in daily.items():
            day_scores[day] = {"avg_score": round(statistics.mean(scores), 2), "events": len(scores)}
        
        best_day = max(day_scores, key=lambda d: day_scores[d]["avg_score"]) if day_scores else "unknown"
        
        return {
            "peak_hours": [f"{h}:00-{h+1}:00" for h in peak_hours],
            "best_day": best_day,
            "hourly": hour_scores,
            "daily": day_scores,
            "insight": f"Productivity peaks at {peak_hours[0] if peak_hours else 'varying'}:00. Best day: {best_day}."
        }
    
    def find_behavioral_correlations(self, data_sources: Dict[str, List]) -> Dict:
        correlations = []
        
        for factor_name, factor_data in data_sources.items():
            if factor_name == "baseline":
                continue
            
            factor_days = set()
            for item in factor_data:
                try:
                    factor_days.add(datetime.fromisoformat(item["date"]).strftime("%Y-%m-%d"))
                except:
                    pass
            
            baseline = data_sources.get("baseline", [])
            with_factor = []
            without_factor = []
            
            for item in baseline:
                try:
                    day = datetime.fromisoformat(item["date"]).strftime("%Y-%m-%d")
                    val = float(item.get("score", item.get("value", 0)))
                    if day in factor_days:
                        with_factor.append(val)
                    else:
                        without_factor.append(val)
                except:
                    pass
            
            if with_factor and without_factor:
                avg_with = statistics.mean(with_factor)
                avg_without = statistics.mean(without_factor)
                change = ((avg_with - avg_without) / avg_without) * 100 if avg_without != 0 else 0
                
                correlations.append({
                    "factor": factor_name,
                    "with": round(avg_with, 2),
                    "without": round(avg_without, 2),
                    "change_pct": round(change, 1),
                    "interpretation": f"{factor_name} correlates with {abs(round(change,1))}% {'increase' if change > 0 else 'decrease'}"
                })
        
        return {"correlations": correlations, "count": len(correlations)}
    
    def detect_anomalies(self, data: List[Dict], metric_key: str) -> Dict:
        values = []
        valid = []
        for record in data:
            try:
                val = float(record.get(metric_key, 0))
                values.append(val)
                valid.append(record)
            except:
                continue
        
        if len(values) < 5:
            return {"error": "Need 5+ data points"}
        
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0
        
        anomalies = []
        for i, val in enumerate(values):
            z = (val - mean) / std if std > 0 else 0
            if abs(z) > 2:
                anomalies.append({
                    "value": val,
                    "z_score": round(z, 2),
                    "direction": "high" if z > 0 else "low",
                    "record": valid[i]
                })
        
        return {
            "total": len(values),
            "mean": round(mean, 2),
            "std": round(std, 2),
            "anomalies": len(anomalies),
            "details": anomalies[:10]
        }
    
    def predict_next(self, historical: List[float], periods: int = 3) -> Dict:
        if len(historical) < 3:
            return {"error": "Need 3+ data points"}
        
        n = len(historical)
        
        # Moving average
        window = min(5, n)
        ma = statistics.mean(historical[-window:])
        
        # Linear regression
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(historical)
        num = sum((i - x_mean) * (historical[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        
        lr_predictions = [slope * (n + i) + intercept for i in range(periods)]
        
        # Exponential smoothing
        alpha = 0.3
        smoothed = historical[0]
        for v in historical[1:]:
            smoothed = alpha * v + (1 - alpha) * smoothed
        
        es_predictions = [smoothed] * periods
        
        # Ensemble
        ensemble = []
        for i in range(periods):
            ensemble.append(round(statistics.mean([ma, lr_predictions[i], es_predictions[i]]), 2))
        
        return {
            "historical_points": n,
            "moving_average": round(ma, 2),
            "linear_regression": [round(p, 2) for p in lr_predictions],
            "exponential_smoothing": [round(p, 2) for p in es_predictions],
            "ensemble": ensemble,
            "trend": "increasing" if slope > 0 else "decreasing"
        }
