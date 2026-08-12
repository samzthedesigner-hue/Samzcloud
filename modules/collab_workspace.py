"""
Collaborative AI Workspace
Multi-user AI-moderated sessions with voting and task tracking.
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

class CollaborativeWorkspace:
    def __init__(self, storage_engine, groq_client):
        self.storage = storage_engine
        self.groq = groq_client
        self.active_sessions = {}
    
    def create_session(self, name: str, participants: List[str], topic: str = None) -> Dict:
        session_id = f"collab_{uuid.uuid4().hex[:12]}"
        
        session = {
            "id": session_id,
            "name": name,
            "participants": {p: {"role": "member", "joined": datetime.now().isoformat()} 
                           for p in participants},
            "topic": topic,
            "messages": [],
            "decisions": [],
            "tasks": [],
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        self.active_sessions[session_id] = session
        self._save(session_id)
        
        welcome = {
            "id": str(uuid.uuid4()),
            "user": "AI Moderator",
            "content": f"👋 Welcome {', '.join(participants)}! I'm your AI moderator. "
                      f"Topic: {topic or 'general'}. I'll track decisions and tasks.",
            "timestamp": datetime.now().isoformat(),
            "type": "system"
        }
        session["messages"].append(welcome)
        
        return {"session_id": session_id, "welcome": welcome["content"]}
    
    def add_message(self, session_id: str, user: str, content: str) -> Dict:
        session = self._get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        msg = {
            "id": str(uuid.uuid4()),
            "user": user,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "type": "user_message"
        }
        session["messages"].append(msg)
        
        # AI analysis
        analysis = self._analyze(session, msg)
        
        if analysis.get("tasks_extracted"):
            for task in analysis["tasks_extracted"]:
                session["tasks"].append({
                    "id": str(uuid.uuid4()),
                    "description": task.get("description", ""),
                    "assigned_to": task.get("assigned_to"),
                    "deadline": task.get("deadline"),
                    "status": "open",
                    "created_at": datetime.now().isoformat()
                })
        
        if analysis.get("should_respond"):
            ai_msg = {
                "id": str(uuid.uuid4()),
                "user": "AI Moderator",
                "content": analysis.get("ai_response", "Noted."),
                "timestamp": datetime.now().isoformat(),
                "type": "ai_response"
            }
            session["messages"].append(ai_msg)
        
        self._save(session_id)
        
        return {
            "message_added": True,
            "ai_response": analysis.get("ai_response"),
            "tasks_updated": len(session["tasks"])
        }
    
    def get_summary(self, session_id: str) -> Dict:
        session = self._get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        messages_text = "\n".join([
            f"{m['user']}: {m['content']}" for m in session["messages"][-50:]
        ])
        
        prompt = f"""Summarize this collaborative session:
Topic: {session.get('topic')}
Participants: {list(session['participants'].keys())}
Messages: {messages_text}
Tasks: {json.dumps(session.get('tasks', []))}

Return JSON with: summary, key_decisions, action_items, next_steps"""
        
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"summary": "Unable to generate summary"}
    
    def get_tasks(self, session_id: str, assigned_to: str = None) -> List[Dict]:
        session = self._get(session_id)
        if not session:
            return []
        tasks = session.get("tasks", [])
        if assigned_to:
            tasks = [t for t in tasks if t.get("assigned_to") == assigned_to]
        return tasks
    
    def complete_task(self, session_id: str, task_id: str, user: str) -> Dict:
        session = self._get(session_id)
        for task in session.get("tasks", []):
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_by"] = user
                task["completed_at"] = datetime.now().isoformat()
                self._save(session_id)
                return {"completed": True, "task": task}
        return {"error": "Task not found"}
    
    def vote(self, session_id: str, proposal_id: str, user: str, vote: str) -> Dict:
        session = self._get(session_id)
        for proposal in session.get("decisions", []):
            if proposal["id"] == proposal_id:
                if user in proposal.get("votes", {}):
                    proposal["votes"][user] = vote
                    self._save(session_id)
                    return {"voted": True}
        return {"error": "Proposal not found"}
    
    def _get(self, session_id: str) -> Optional[Dict]:
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        stored = self.storage.read_file(f"collab/{session_id}.json")
        if stored:
            session = json.loads(stored)
            self.active_sessions[session_id] = session
            return session
        return None
    
    def _save(self, session_id: str):
        if session_id in self.active_sessions:
            self.storage.write_file(
                f"collab/{session_id}.json",
                json.dumps(self.active_sessions[session_id])
            )
    
    def _analyze(self, session: Dict, message: Dict) -> Dict:
        try:
            response = self.groq.chat.completions.create(
                model="mistral-8x7b-32768",
                messages=[{
                    "role": "system",
                    "content": "Analyze message for tasks and responses. Return JSON: {should_respond, ai_response, tasks_extracted: [{description, assigned_to, deadline}]}"
                }, {
                    "role": "user",
                    "content": f"Topic: {session.get('topic')}\nUser: {message['user']}\nMessage: {message['content']}"
                }],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"should_respond": False}
