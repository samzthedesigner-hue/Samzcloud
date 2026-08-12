# ⚡ SamzCloud

Personal cloud platform with SELF-CONTAINED storage.
All storage is built INTO SamzCloud — NOT on your phone, NOT on Render's default disk.

## Architecture
- **Total Storage:** 212GB (128GB Virtual Disk + 84GB ROM)
- **Storage Location:** Inside SAMZCLOUD_HOME directory (SamzCloud's own world)
- **AI:** Groq + Mistral 8x7B
- **Deployment:** Render + Termux dual-server
- **Research:** Tavily, SerpAPI, Wikipedia, DuckDuckGo, arXiv

## Storage Breakdown
### Virtual Disk (128GB) — Inside SAMZCLOUD_HOME/disk/
- Projects (deployed apps)
- User files
- Databases (auth, configs)
- Cache
- Build artifacts
- Logs

### ROM (84GB) — Inside SAMZCLOUD_HOME/rom/
- ML Models: 30GB (PyTorch, Transformers weights)
- System Packages: 20GB (pip packages)
- Knowledge Base: 20GB (research data, documents)
- System & Backups: 14GB

## IMPORTANT
SamzCloud does NOT use your phone's /sdcard/ or Render's default disk.
It creates its own isolated filesystem at SAMZCLOUD_HOME.
Everything — projects, models, files, databases — lives inside SamzCloud.

## Modules
1. AI Assistant with Compute Engine
2. Personal Data Miner & Pattern Engine
3. Collaborative AI Workspace
4. Code Whisperer (Cross-Repo Intelligence)
5. Decision Simulation Engine
6. Autonomous Research Agent
7. Personal AI Trainer
8. AI Accelerator Workflow Engine

## Environment Variables
- `GROQ_API_KEY` - Groq API key
- `TAVILY_API_KEY` - Tavily search API
- `SERPAPI_API_KEY` - SerpAPI key
- `DEPLOYMENT` - "render" or "termux"
- `SAMZCLOUD_HOME` - Where SamzCloud's storage lives (default: ~/samzcloud_data)
- `STORAGE_MAX_GB` - Virtual disk size (default 128)
- `ROM_MAX_GB` - ROM size (default 84)

## API Documentation
After starting, visit `/docs` for Swagger UI.
