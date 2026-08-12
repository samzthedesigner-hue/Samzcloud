"""
SamzCloud Global Configuration
Self-contained storage system — SamzCloud owns its entire storage world.
212GB total: 128GB Virtual Disk + 84GB ROM
All storage is built INTO SamzCloud, isolated from host device.
"""

import os
from pathlib import Path

class Config:
    # Platform Identity
    PLATFORM_NAME = "SamzCloud"
    VERSION = "1.0.0"
    BUILD = "enterprise"
    
    # Deployment Mode
    DEPLOYMENT = os.getenv("DEPLOYMENT", "termux")  # "render" or "termux"
    
    # ============================================================
    # SAMZCLOUD'S OWN STORAGE WORLD
    # Everything lives inside this ONE directory.
    # This is NOT your phone's storage. NOT Render's default disk.
    # It's SamzCloud's self-contained filesystem.
    # ============================================================
    
    SAMZCLOUD_HOME = Path(os.getenv(
        "SAMZCLOUD_HOME",
        str(Path.home() / "samzcloud_data")
    ))
    
    # Virtual Disk (Projects, Files, Databases) — 128GB
    STORAGE_ROOT = SAMZCLOUD_HOME / "disk"
    STORAGE_MAX_SIZE_GB = int(os.getenv("STORAGE_MAX_GB", "128"))
    STORAGE_MAX_SIZE_BYTES = STORAGE_MAX_SIZE_GB * 1024**3
    
    # ROM (Read-Only Memory) — 84GB
    ROM_ROOT = SAMZCLOUD_HOME / "rom"
    ROM_MAX_SIZE_GB = int(os.getenv("ROM_MAX_GB", "84"))
    ROM_MAX_SIZE_BYTES = ROM_MAX_SIZE_GB * 1024**3
    
    # ===== VIRTUAL DISK SUBDIRECTORIES (Inside STORAGE_ROOT) =====
    STORAGE_VECTOR_DB = STORAGE_ROOT / "vectordb"
    STORAGE_FILES = STORAGE_ROOT / "files"
    STORAGE_PROJECTS = STORAGE_ROOT / "projects"
    STORAGE_CACHE = STORAGE_ROOT / "cache"
    STORAGE_LOGS = STORAGE_ROOT / "logs"
    STORAGE_DATABASE = STORAGE_ROOT / "database"
    STORAGE_BUILDS = STORAGE_ROOT / "builds"
    
    # ===== ROM SUBDIRECTORIES (Inside ROM_ROOT) =====
    # ROM_ALLOCATIONS defines how the 84GB is divided
    ROM_ALLOCATIONS = {
        "models": 30,      # ML models (PyTorch, Transformers weights)
        "packages": 20,    # System packages (pip packages)
        "knowledge": 20,   # Knowledge base (research data, documents)
        "system": 14,      # System files, backups
    }
    
    ROM_MODELS = ROM_ROOT / "models"
    ROM_PACKAGES = ROM_ROOT / "packages"
    ROM_KNOWLEDGE = ROM_ROOT / "knowledge"
    ROM_SYSTEM = ROM_ROOT / "system"
    ROM_BACKUPS = ROM_ROOT / "backups"
    ROM_INDICES = ROM_ROOT / "indices"
    
    # ===== API KEYS =====
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    
    # ===== AI CONFIG =====
    GROQ_MODEL = "mistral-8x7b-32768"
    GROQ_MODEL_FAST = "llama-3.1-8b-instant"
    GROQ_MAX_TOKENS = 32768
    
    # ===== GITHUB =====
    GITHUB_USERNAME = "samzthedesigner-hue"
    GITHUB_API_URL = "https://api.github.com"
    
    # ===== AUTH =====
    AUTH_DB_PATH = STORAGE_DATABASE / "auth.db"
    
    # ===== PORTS =====
    MAIN_PORT = int(os.getenv("PORT", "8000"))
    PROJECT_PORT_START = 8001
    PROJECT_PORT_END = 8100
    
    # ===== BUILD SETTINGS =====
    MAX_BUILD_TIME_SECONDS = int(os.getenv("MAX_BUILD_TIME", "600"))
    BUILD_LOG_RETENTION_DAYS = 30
    
    @classmethod
    def init_storage(cls):
        """Initialize SamzCloud's ENTIRE self-contained storage world"""
        # Create the main home directory
        cls.SAMZCLOUD_HOME.mkdir(parents=True, exist_ok=True)
        
        # Create Virtual Disk directories
        for attr in dir(cls):
            if attr.startswith("STORAGE_") and not attr.endswith(("_SIZE_GB", "_SIZE_BYTES", "_ROOT")):
                path = getattr(cls, attr)
                if isinstance(path, Path):
                    path.mkdir(parents=True, exist_ok=True)
        
        # Create ROM directories
        for attr in dir(cls):
            if attr.startswith("ROM_") and not attr.endswith(("_SIZE_GB", "_SIZE_BYTES", "_ROOT", "_ALLOCATIONS")):
                path = getattr(cls, attr)
                if isinstance(path, Path):
                    path.mkdir(parents=True, exist_ok=True)
        
        # Write allocation metadata
        rom_meta = cls.ROM_ROOT / "rom_allocations.json"
        if not rom_meta.exists():
            import json
            from datetime import datetime
            rom_meta.write_text(json.dumps({
                "created_at": datetime.now().isoformat(),
                "total_size_gb": cls.ROM_MAX_SIZE_GB,
                "allocations": cls.ROM_ALLOCATIONS,
                "purpose": "SamzCloud's internal ROM — stores models, packages, knowledge"
            }, indent=2))
    
    @classmethod
    def get_storage_info(cls):
        """Get complete storage information — all SELF-CONTAINED"""
        return {
            "storage_owner": "SamzCloud",
            "location": str(cls.SAMZCLOUD_HOME),
            "note": "All storage is built into SamzCloud. Host device storage is NOT used.",
            "virtual_disk": {
                "path": str(cls.STORAGE_ROOT),
                "max_gb": cls.STORAGE_MAX_SIZE_GB,
                "purpose": "Projects, files, databases, cache, builds"
            },
            "rom": {
                "path": str(cls.ROM_ROOT),
                "max_gb": cls.ROM_MAX_SIZE_GB,
                "purpose": "ML models, packages, knowledge base, system",
                "allocations": cls.ROM_ALLOCATIONS
            },
            "total_platform_storage_gb": cls.STORAGE_MAX_SIZE_GB + cls.ROM_MAX_SIZE_GB
        }
