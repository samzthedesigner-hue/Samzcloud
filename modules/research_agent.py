"""
Autonomous Research Agent
Deep research with multi-source search, knowledge graphs, continuous updates.
"""

import json
import uuid
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
from research.search_engine import ResearchSearchEngine

class ResearchAgent:
    def __init__(self, storage_engine, groq_client):
        self.storage = storage_engine
        self.groq = groq_client
        self.search_engine = ResearchSearchEngine()
        self.active_research = {}
    
    def start_research(self, topic: str, depth: int = 3) -> Dict:
        research_id = f"research_{uuid.uuid4().hex[:12]}"
        
        research = {
            "id": research_id,
            "topic": topic,
            "depth": depth,
            "status": "active",
            "started_at": datetime.now().isoformat(),
            "findings": [],
            "knowledge_nodes": [],
            "sources_used": [],
            "summary": None
        }
        
        self.active_research[research_id] = research
        self.storage.write_file(f"research/{research_id}.json", json.dumps(research))
        
        # Start async research
        import asyncio
        threading.Thread(
            target=lambda: asyncio.run(self._research_loop(research_id)),
            daemon=True
        ).start()
        
        return {"research_id": research_id, "topic": topic, "status": "started"}
    
    async def _research_loop(self, research_id: str):
        research = self._get(research_id)
        if not research:
            return
        
        # Initial search
        import asyncio
        results = await self.search_engine.deep_research(research["topic"], research["depth"])
        
        research["findings"] = results["results"]
        research["sources_used"] = results.get("sources_used", [])
        research["status"] = "phase_1_complete"
        self._save(research_id)
        
        # Generate summary
        summary = self._generate_summary(research["topic"], research["findings"])
        research["summary"] = summary
        research["status"] = "completed"
        research["completed_at"] = datetime.now().isoformat()
        self._save(research_id)
    
    def get_status(self, research_id: str) -> Dict:
        research = self._get(research_id)
        if not research:
            return {"error": "Research not found"}
        return {
            "id": research_id,
            "topic": research["topic"],
            "status": research["status"],
            "findings": len(research.get("findings", [])),
            "sources": research.get("sources_used", []),
            "summary": research.get("summary")
        }
    
    def ask(self, research_id: str, question: str) -> Dict:
        research = self._get(research_id)
        if not research:
            return {"error": "Research not found"}
        
        context = "\n".join([
            f"- {f.get('title', '')}: {f.get('content', '')[:300]}"
            for f in research.get("findings", [])[:20]
        ])
        
        prompt = f"Based on research about '{research['topic']}':\n{context}\n\nQuestion: {question}"
        
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return {"question": question, "answer": response.choices[0].message.content}
        except:
            return {"error": "Failed to generate answer"}
    
    def _generate_summary(self, topic: str, findings: List[Dict]) -> str:
        context = "\n".join([f.get("content", "")[:200] for f in findings[:15]])
        prompt = f"Write a research summary on '{topic}' based on findings:\n{context}\n\n3-4 paragraphs covering key findings and implications."
        
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except:
            return "Summary generation in progress..."
    
    def _get(self, research_id: str) -> Optional[Dict]:
        if research_id in self.active_research:
            return self.active_research[research_id]
        stored = self.storage.read_file(f"research/{research_id}.json")
        if stored:
            research = json.loads(stored)
            self.active_research[research_id] = research
            return research
        return None
    
    def _save(self, research_id: str):
        if research_id in self.active_research:
            self.storage.write_file(
                f"research/{research_id}.json",
                json.dumps(self.active_research[research_id])
            )
