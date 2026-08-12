"""
SamzCloud AI Assistant with Compute Engine
"""

import json
from groq import Groq
from core.config import Config

SYSTEM_PROMPT = """You are SamzCloud AI Assistant. You can chat, analyze data, make predictions, 
and help with tasks. Be precise and helpful. When analyzing data, show your reasoning."""

class AIAssistant:
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.conversations = {}
        self.compute_engine = ComputeEngine()
    
    async def process_message(self, user_id, message):
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        compute_result = None
        if any(k in message.lower() for k in ["calculate","predict","analyze","statistics","probability","forecast","trend","risk","regression","matrix","compute"]):
            compute_result = self.compute_engine.route(message)
        
        context = ""
        if compute_result:
            context = f"\n[COMPUTATION]: {json.dumps(compute_result)}\nUse this data."
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.conversations[user_id][-15:],
            {"role": "user", "content": message + context}
        ]
        
        response = self.client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=messages,
            temperature=0.3
        )
        
        reply = response.choices[0].message.content
        
        self.conversations[user_id].append({"role": "user", "content": message})
        self.conversations[user_id].append({"role": "assistant", "content": reply})
        
        return {"response": reply, "computation": compute_result}
    
    def search_memory(self, query, n_results=5):
        return {"results": [], "query": query}


import re
import math
import statistics
from collections import Counter

class ComputeEngine:
    def route(self, message):
        msg = message.lower()
        if any(w in msg for w in ["predict","forecast","trend"]):
            return self.predictive_analysis(message)
        elif any(w in msg for w in ["statistics","mean","average","std","standard deviation"]):
            return self.statistical_analysis(message)
        elif any(w in msg for w in ["probability","risk","chance"]):
            return self.probability_analysis(message)
        else:
            return self.general_compute(message)
    
    def predictive_analysis(self, message):
        numbers = [float(n) for n in re.findall(r'-?\d+\.?\d*', message)]
        if len(numbers) < 3:
            return {"error": "Need 3+ data points"}
        
        n = len(numbers)
        x_mean = sum(range(n)) / n
        y_mean = sum(numbers) / n
        
        num = sum((i - x_mean) * (numbers[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        
        predictions = [slope * (n + i) + intercept for i in range(3)]
        
        return {
            "type": "predictive",
            "slope": round(slope, 4),
            "trend": "upward" if slope > 0 else "downward",
            "next_3": [round(p, 2) for p in predictions]
        }
    
    def statistical_analysis(self, message):
        numbers = [float(n) for n in re.findall(r'-?\d+\.?\d*', message)]
        if len(numbers) < 2:
            return {"error": "Need 2+ numbers"}
        
        n = len(numbers)
        mean = statistics.mean(numbers)
        sorted_nums = sorted(numbers)
        median = statistics.median(numbers)
        std = statistics.stdev(numbers) if n > 1 else 0
        
        return {
            "type": "statistical",
            "count": n, "mean": round(mean, 4), "median": round(median, 4),
            "std": round(std, 4), "min": min(numbers), "max": max(numbers)
        }
    
    def probability_analysis(self, message):
        numbers = [float(n) for n in re.findall(r'-?\d+\.?\d*', message)]
        if len(numbers) >= 2:
            events, total = numbers[0], numbers[1]
            prob = events / total if total > 0 else 0
            pct = prob * 100
            risk = "very low" if pct < 1 else "low" if pct < 5 else "moderate" if pct < 15 else "high" if pct < 30 else "very high"
            return {"probability": round(prob, 6), "percentage": round(pct, 2), "risk_level": risk}
        return {"error": "Need events and total"}
    
    def general_compute(self, message):
        numbers = [float(n) for n in re.findall(r'-?\d+\.?\d*', message)]
        if not numbers:
            return {"numbers_found": 0}
        return {"count": len(numbers), "sum": sum(numbers), "average": statistics.mean(numbers)}
