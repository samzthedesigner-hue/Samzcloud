"""
Personal AI Trainer
Learns writing style, decisions, detects anomalies.
"""

import json
import statistics
from datetime import datetime
from typing import List, Dict, Any
from collections import Counter

class PersonalAITrainer:
    def __init__(self, storage_engine, groq_client):
        self.storage = storage_engine
        self.groq = groq_client
        self.models = {}
    
    def learn_writing_style(self, samples: List[Dict]) -> Dict:
        if len(samples) < 5:
            return {"error": "Need 5+ samples"}
        
        all_text = " ".join([s["text"] for s in samples])
        words = all_text.split()
        
        profile = {
            "avg_sentence_length": self._avg_sentence_len(samples),
            "vocabulary_size": len(set(words)),
            "common_words": self._top_words(words, 50),
            "formality": self._formality(samples),
            "tone": self._analyze_tone(samples),
            "trained_at": datetime.now().isoformat(),
            "samples": len(samples)
        }
        
        self.models["writing"] = profile
        self.storage.write_file("trainer/writing_style.json", json.dumps(profile))
        
        return {"trained": True, "samples": len(samples), "vocabulary": profile["vocabulary_size"]}
    
    def generate_in_my_style(self, prompt: str, context: str = "email") -> Dict:
        style = self.models.get("writing") or json.loads(
            self.storage.read_file("trainer/writing_style.json") or "{}"
        )
        
        if not style:
            return {"error": "Train writing style first"}
        
        style_prompt = f"""Write in this style:
- Sentence length: {style.get('avg_sentence_length', 15)} words avg
- Formality: {style.get('formality', 5)}/10
- Tone: {style.get('tone', 'neutral')}
- Common words: {', '.join(style.get('common_words', [])[:15])}

Context: {context}
Prompt: {prompt}"""
        
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{"role": "user", "content": style_prompt}],
                temperature=0.4
            )
            return {"generated": response.choices[0].message.content}
        except:
            return {"error": "Generation failed"}
    
    def learn_decisions(self, decisions: List[Dict]) -> Dict:
        patterns = {
            "risk_preference": self._analyze_risk(decisions),
            "samples": len(decisions),
            "trained_at": datetime.now().isoformat()
        }
        self.models["decisions"] = patterns
        self.storage.write_file("trainer/decision_patterns.json", json.dumps(patterns))
        return patterns
    
    def predict_decision(self, scenario: str, options: List[str]) -> Dict:
        patterns = self.models.get("decisions") or json.loads(
            self.storage.read_file("trainer/decision_patterns.json") or "{}"
        )
        
        prompt = f"Based on risk preference: {patterns.get('risk_preference', 'moderate')}\nScenario: {scenario}\nOptions: {options}\nPredict which option this person chooses and why."
        
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return {"prediction": response.choices[0].message.content}
        except:
            return {"error": "Prediction failed"}
    
    def detect_not_like_me(self, text: str, context: str = "general") -> Dict:
        style = self.models.get("writing", {})
        anomalies = []
        
        if style and context in ("email", "message", "text"):
            words = text.split()
            sentences = text.replace("!", ".").replace("?", ".").split(".")
            lengths = [len(s.split()) for s in sentences if s.strip()]
            avg = statistics.mean(lengths) if lengths else 0
            
            expected = style.get("avg_sentence_length", 15)
            if avg > expected * 1.5:
                anomalies.append(f"Sentences much longer than usual ({round(avg)} vs {expected})")
            elif avg < expected * 0.5:
                anomalies.append(f"Sentences much shorter than usual ({round(avg)} vs {expected})")
        
        return {
            "anomalies": len(anomalies),
            "details": anomalies,
            "verdict": "This seems unusual" if anomalies else "This matches your patterns"
        }
    
    def _avg_sentence_len(self, samples: List[Dict]) -> int:
        lengths = []
        for s in samples:
            for sent in s["text"].replace("!", ".").replace("?", ".").split("."):
                words = sent.strip().split()
                if words:
                    lengths.append(len(words))
        return round(statistics.mean(lengths)) if lengths else 15
    
    def _top_words(self, words: List[str], n: int) -> List[str]:
        stop = {"the","a","an","is","was","are","were","be","been","have","has","had",
                "do","does","did","will","would","could","should","may","might","can",
                "shall","to","of","in","for","on","with","at","by","from","as","and","or","but"}
        filtered = [w.lower() for w in words if w.lower() not in stop and len(w) > 2]
        return [w for w, _ in Counter(filtered).most_common(n)]
    
    def _formality(self, samples: List[Dict]) -> float:
        formal = ["dear","sincerely","regards","furthermore","however","therefore","consequently"]
        informal = ["hey","yeah","cool","awesome","gonna","wanna","btw","lol","thx"]
        text = " ".join([s["text"].lower() for s in samples])
        f_count = sum(1 for w in formal if w in text)
        i_count = sum(1 for w in informal if w in text)
        total = f_count + i_count
        return round((f_count / total) * 10, 1) if total > 0 else 5.0
    
    def _analyze_tone(self, samples: List[Dict]) -> str:
        text = " ".join([s["text"].lower() for s in samples])
        pos = sum(1 for w in ["great","good","excellent","happy","love","thanks","awesome"] if w in text)
        neg = sum(1 for w in ["bad","sorry","unfortunately","issue","problem","fail","terrible"] if w in text)
        return "positive" if pos > neg else "negative" if neg > pos else "neutral"
    
    def _analyze_risk(self, decisions: List[Dict]) -> str:
        if not decisions:
            return "unknown"
        risky = sum(1 for d in decisions if d.get("risk_level", "medium") == "high")
        ratio = risky / len(decisions)
        return "risk_tolerant" if ratio > 0.6 else "moderate" if ratio > 0.3 else "risk_averse"
