"""
SamzCloud Main Server
Complete platform with all modules.
128GB + 84GB ROM | Multi-source research | 7 AI modules
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import time
import os
from datetime import datetime

from core.config import Config
from core.auth_engine import AuthEngine, KeyType
from core.deploy_engine import DeployEngine
from core.keepalive import start_keepalive
from storage.disk import VirtualDisk, ROM
from ai.assistant import AIAssistant, ComputeEngine
from research.search_engine import ResearchSearchEngine
from modules.personal_miner import PersonalMiner
from modules.collab_workspace import CollaborativeWorkspace
from modules.code_whisperer import CodeWhisperer
from modules.decision_simulator import DecisionSimulator
from modules.research_agent import ResearchAgent
from modules.ai_trainer import PersonalAITrainer
from modules.accelerator import AIAccelerator
from groq import Groq

# Initialize
Config.init_storage()

app = FastAPI(
    title="SamzCloud",
    version=Config.VERSION,
    description="Personal Cloud Platform | 128GB + 84GB ROM | Multi-Module AI"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Engines
auth_engine = AuthEngine()
virtual_disk = VirtualDisk()
rom = ROM()
groq_client = Groq(api_key=Config.GROQ_API_KEY)
deploy_engine = DeployEngine(auth_engine, virtual_disk)
ai_assistant = AIAssistant()
compute_engine = ComputeEngine()
search_engine = ResearchSearchEngine()
personal_miner = PersonalMiner(virtual_disk)
collab_workspace = CollaborativeWorkspace(virtual_disk, groq_client)
code_whisperer = CodeWhisperer(virtual_disk, groq_client)
decision_simulator = DecisionSimulator(virtual_disk, groq_client)
research_agent = ResearchAgent(virtual_disk, groq_client)
ai_trainer = PersonalAITrainer(virtual_disk, groq_client)
accelerator = AIAccelerator(virtual_disk, groq_client)

# Start keepalive
start_keepalive()

# ===== MIDDLEWARE =====
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public = ["/health","/version","/auth/challenge","/auth/generate-key","/docs","/openapi.json","/storage/info"]
    if request.url.path in public or request.url.path.startswith("/public/"):
        return await call_next(request)
    
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not api_key:
        return JSONResponse(status_code=401, content={"error":"API key required. Generate at /auth/generate-key"})
    
    validation = auth_engine.validate_api_key(api_key)
    if not validation:
        return JSONResponse(status_code=403, content={"error":"Invalid or revoked API key"})
    
    if not auth_engine.check_rate_limit(api_key[:11]):
        return JSONResponse(status_code=429, content={"error":"Rate limit exceeded"})
    
    return await call_next(request)

# ===== SYSTEM =====
@app.get("/health")
async def health():
    return {
        "status": "alive",
        "platform": Config.PLATFORM_NAME,
        "version": Config.VERSION,
        "deployment": Config.DEPLOYMENT,
        "storage": {
            "virtual_disk": virtual_disk.get_usage(),
            "rom": rom.get_usage()
        },
        "time": time.time()
    }

@app.get("/version")
async def version():
    return {"platform": Config.PLATFORM_NAME, "version": Config.VERSION, "build": Config.BUILD}

@app.get("/storage/info")
async def storage_info():
    return Config.get_storage_info()

# ===== AUTH =====
@app.get("/auth/challenge")
async def get_challenge():
    return auth_engine.create_challenge()

@app.post("/auth/generate-key")
async def generate_key(challenge_id: str, nonce: str, name: str = None,
                       key_type: str = "full_access", project_name: str = None,
                       expires_in_days: int = None):
    try:
        return auth_engine.generate_api_key(challenge_id, nonce, name, KeyType(key_type), project_name, expires_in_days)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

@app.get("/auth/keys")
async def list_keys():
    return auth_engine.list_api_keys()

@app.delete("/auth/keys/{key_id}")
async def revoke_key(key_id: str, confirm: bool = False):
    if not confirm:
        return {"message": "Set confirm=true to revoke permanently"}
    result = auth_engine.revoke_api_key(key_id)
    if result.get("error"):
        raise HTTPException(404, detail=result["error"])
    return result

# ===== STORAGE =====
@app.get("/storage/disk")
async def disk_usage():
    return virtual_disk.get_usage()

@app.get("/storage/rom")
async def rom_usage():
    return rom.get_usage()

@app.post("/storage/write")
async def write_file(path: str, content: str, app: str = "default"):
    try:
        return {"stored": virtual_disk.write_file(path, content, app)}
    except Exception as e:
        raise HTTPException(413, detail=str(e))

@app.get("/storage/read/{path:path}")
async def read_file(path: str):
    content = virtual_disk.read_file(path)
    if content is None:
        raise HTTPException(404)
    return {"content": content}

@app.get("/storage/list")
async def list_files(dir: str = ""):
    return virtual_disk.list_files(dir)

@app.delete("/storage/delete/{path:path}")
async def delete_file(path: str):
    if virtual_disk.delete_file(path):
        return {"deleted": True}
    raise HTTPException(404)

# ===== DEPLOY =====
@app.post("/deploy/add")
async def add_project(name: str, github_url: str, api_key: str,
                      branch: str = "main", build_cmd: str = None, start_cmd: str = None):
    try:
        return deploy_engine.add_app(name, github_url, api_key, branch, build_cmd, start_cmd)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

@app.post("/deploy/{name}")
async def deploy_project(name: str, api_key: str = None):
    return deploy_engine.deploy_app(name, api_key)

@app.get("/deploy/status")
async def deploy_status():
    return deploy_engine.list_apps()

@app.get("/deploy/{name}/logs")
async def deploy_logs(name: str, lines: int = 50):
    return deploy_engine.get_app_logs(name, lines)

@app.get("/deploy/{name}/build-logs")
async def build_logs(name: str):
    return deploy_engine.get_build_logs(name)

@app.get("/deploy/logs")
async def all_deploy_logs(project: str = None, limit: int = 50):
    return auth_engine.get_deploy_logs(project, limit)

@app.post("/deploy/{name}/stop")
async def stop_project(name: str):
    deploy_engine.stop_app(name)
    return {"stopped": True}

# ===== AI ASSISTANT =====
@app.post("/ai/chat")
async def chat(user_id: str, message: str):
    return await ai_assistant.process_message(user_id, message)

@app.post("/ai/compute")
async def compute(message: str):
    return compute_engine.route(message)

# ===== RESEARCH SEARCH =====
@app.post("/research/search")
async def research_search(query: str, max_results: int = 10, source: str = "auto"):
    import asyncio
    return await search_engine.search(query, max_results, source)

@app.post("/research/deep-search")
async def deep_search(query: str, depth: int = 3):
    import asyncio
    return await search_engine.deep_research(query, depth)

# ===== MODULE: RESEARCH AGENT =====
@app.post("/agent/research/start")
async def agent_research_start(topic: str, depth: int = 3):
    return research_agent.start_research(topic, depth)

@app.get("/agent/research/{research_id}")
async def agent_research_status(research_id: str):
    return research_agent.get_status(research_id)

@app.post("/agent/research/{research_id}/ask")
async def agent_research_ask(research_id: str, question: str):
    return research_agent.ask(research_id, question)

# ===== MODULE: PERSONAL MINER =====
@app.post("/miner/ingest")
async def miner_ingest(data_type: str, data: str):
    return personal_miner.ingest_data(data_type, json.loads(data))

@app.post("/miner/productivity")
async def miner_productivity(data: str):
    return personal_miner.find_productivity_patterns(json.loads(data))

@app.post("/miner/correlations")
async def miner_correlations(data: str):
    return personal_miner.find_behavioral_correlations(json.loads(data))

@app.post("/miner/anomalies")
async def miner_anomalies(data: str, metric_key: str):
    return personal_miner.detect_anomalies(json.loads(data), metric_key)

@app.post("/miner/predict")
async def miner_predict(data: str, periods: int = 3):
    return personal_miner.predict_next(json.loads(data), periods)

# ===== MODULE: COLLAB WORKSPACE =====
@app.post("/collab/create")
async def collab_create(name: str, participants: str, topic: str = None):
    return collab_workspace.create_session(name, json.loads(participants), topic)

@app.post("/collab/{session_id}/message")
async def collab_message(session_id: str, user: str, content: str):
    return collab_workspace.add_message(session_id, user, content)

@app.get("/collab/{session_id}/summary")
async def collab_summary(session_id: str):
    return collab_workspace.get_summary(session_id)

@app.get("/collab/{session_id}/tasks")
async def collab_tasks(session_id: str, assigned_to: str = None):
    return collab_workspace.get_tasks(session_id, assigned_to)

# ===== MODULE: CODE WHISPERER =====
@app.post("/code/index")
async def code_index(repo_name: str, files: str):
    return code_whisperer.index_repository(repo_name, json.loads(files))

@app.post("/code/cross-repo-bugs")
async def code_cross_bugs(changed_repo: str, files: str):
    return code_whisperer.find_cross_repo_bugs(changed_repo, json.loads(files))

# ===== MODULE: DECISION SIMULATOR =====
@app.post("/decide/simulate")
async def decide_simulate(decision: str, options: str, factors: str,
                           historical: str = None, simulations: int = 1000):
    return decision_simulator.simulate_decision(
        decision, json.loads(options), json.loads(factors),
        json.loads(historical) if historical else None, simulations
    )

# ===== MODULE: AI TRAINER =====
@app.post("/trainer/learn-style")
async def trainer_learn_style(samples: str):
    return ai_trainer.learn_writing_style(json.loads(samples))

@app.post("/trainer/generate-style")
async def trainer_generate(prompt: str, context: str = "email"):
    return ai_trainer.generate_in_my_style(prompt, context)

@app.post("/trainer/learn-decisions")
async def trainer_learn_decisions(decisions: str):
    return ai_trainer.learn_decisions(json.loads(decisions))

@app.post("/trainer/predict-decision")
async def trainer_predict(scenario: str, options: str):
    return ai_trainer.predict_decision(scenario, json.loads(options))

@app.post("/trainer/detect-anomaly")
async def trainer_detect(text: str, context: str = "general"):
    return ai_trainer.detect_not_like_me(text, context)

# ===== MODULE: ACCELERATOR =====
@app.post("/accelerate/pipeline")
async def accelerate_create(steps: str):
    return accelerator.create_pipeline(json.loads(steps))

@app.get("/accelerate/metrics")
async def accelerate_metrics():
    return accelerator.get_metrics()

@app.post("/accelerate/preload")
async def accelerate_preload(models: str):
    return accelerator.preload_models(json.loads(models))

# ===== START =====
if __name__ == "__main__":
    print(f"⚡ {Config.PLATFORM_NAME} v{Config.VERSION}")
    print(f"   Virtual Disk: {Config.STORAGE_MAX_SIZE_GB}GB")
    print(f"   ROM: {Config.ROM_MAX_SIZE_GB}GB")
    print(f"   Deployment: {Config.DEPLOYMENT}")
    print(f"   Port: {Config.MAIN_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=Config.MAIN_PORT)
