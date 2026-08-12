"""
SamzCloud Storage Engine
Self-contained 128GB Virtual Disk + 84GB ROM
Everything is INSIDE SamzCloud's own filesystem at SAMZCLOUD_HOME.
Host device storage is untouched.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from core.config import Config

class VirtualDisk:
    """
    128GB Virtual Disk — SamzCloud's OWN storage.
    Lives inside SAMZCLOUD_HOME/disk/
    NOT on your phone's /sdcard/
    NOT on Render's default disk
    """
    
    def __init__(self):
        self.root = Config.STORAGE_ROOT
        self.max_size = Config.STORAGE_MAX_SIZE_BYTES
        Config.init_storage()
        self.meta_file = self.root / "disk_meta.json"
        self._init_meta()
    
    def _init_meta(self):
        if not self.meta_file.exists():
            self.meta = {
                "created_at": datetime.now().isoformat(),
                "total_size_gb": Config.STORAGE_MAX_SIZE_GB,
                "owner": "SamzCloud",
                "type": "self_contained_virtual_disk",
                "files": {},
                "projects": {}
            }
            self._save_meta()
        else:
            self.meta = json.loads(self.meta_file.read_text())
    
    def _save_meta(self):
        self.meta_file.write_text(json.dumps(self.meta, indent=2))
    
    def get_usage(self):
        total_size = 0
        file_count = 0
        
        for path in self.root.rglob("*"):
            if path.is_file() and path != self.meta_file:
                total_size += path.stat().st_size
                file_count += 1
        
        return {
            "disk": "samzcloud_virtual_disk",
            "path": str(self.root),
            "used_bytes": total_size,
            "used_mb": round(total_size / (1024**2), 2),
            "used_gb": round(total_size / (1024**3), 3),
            "total_gb": Config.STORAGE_MAX_SIZE_GB,
            "free_gb": round(Config.STORAGE_MAX_SIZE_GB - total_size / (1024**3), 3),
            "percent_used": round((total_size / self.max_size) * 100, 1),
            "file_count": file_count
        }
    
    def has_space(self, required_bytes):
        usage = self.get_usage()
        return (usage["used_bytes"] + required_bytes) <= self.max_size
    
    def write_file(self, path_within, content, app_name=None):
        full_path = self.root / path_within
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        content_bytes = content.encode() if isinstance(content, str) else content
        
        if not self.has_space(len(content_bytes)):
            raise DiskFullError(f"SamzCloud virtual disk full. Need {len(content_bytes)} bytes.")
        
        full_path.write_bytes(content_bytes)
        
        rel_path = str(path_within)
        self.meta["files"][rel_path] = {
            "size": len(content_bytes),
            "modified": datetime.now().isoformat(),
            "app": app_name
        }
        self._save_meta()
        
        return str(full_path)
    
    def read_file(self, path_within):
        full_path = self.root / path_within
        if full_path.exists():
            return full_path.read_text()
        return None
    
    def read_bytes(self, path_within):
        full_path = self.root / path_within
        if full_path.exists():
            return full_path.read_bytes()
        return None
    
    def delete_file(self, path_within):
        full_path = self.root / path_within
        if full_path.exists():
            full_path.unlink()
            rel_path = str(path_within)
            self.meta["files"].pop(rel_path, None)
            self._save_meta()
            return True
        return False
    
    def list_files(self, directory=""):
        dir_path = self.root / directory
        if not dir_path.exists():
            return []
        return [
            {
                "name": f.name,
                "path": str(f.relative_to(self.root)),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            }
            for f in dir_path.iterdir() if f.is_file()
        ]
    
    def get_project_space(self, project_name):
        project_path = Config.STORAGE_PROJECTS / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        
        if project_name not in self.meta["projects"]:
            self.meta["projects"][project_name] = {
                "created": datetime.now().isoformat(),
                "size_limit_mb": 500,
                "builds": 0
            }
            self._save_meta()
        
        return project_path
    
    def record_build(self, project_name):
        if project_name in self.meta["projects"]:
            self.meta["projects"][project_name]["builds"] += 1
            self.meta["projects"][project_name]["last_build"] = datetime.now().isoformat()
            self._save_meta()


class ROM:
    """
    84GB Read-Only Memory — SamzCloud's internal ROM.
    Lives inside SAMZCLOUD_HOME/rom/
    Stores models, packages, knowledge base.
    """
    
    def __init__(self):
        self.root = Config.ROM_ROOT
        self.max_size = Config.ROM_MAX_SIZE_BYTES
        self.meta_file = self.root / "rom_meta.json"
        self._init_meta()
    
    def _init_meta(self):
        if not self.meta_file.exists():
            self.meta = {
                "created_at": datetime.now().isoformat(),
                "total_size_gb": Config.ROM_MAX_SIZE_GB,
                "owner": "SamzCloud",
                "type": "self_contained_rom",
                "allocations": {}
            }
            
            for name, gb in Config.ROM_ALLOCATIONS.items():
                self.meta["allocations"][name] = {
                    "max_gb": gb,
                    "used_gb": 0
                }
            
            self._save_meta()
        else:
            self.meta = json.loads(self.meta_file.read_text())
    
    def _save_meta(self):
        self.meta_file.write_text(json.dumps(self.meta, indent=2))
    
    def get_usage(self):
        total_size = sum(
            f.stat().st_size for f in self.root.rglob("*")
            if f.is_file() and f != self.meta_file
        )
        
        return {
            "disk": "samzcloud_rom",
            "path": str(self.root),
            "used_bytes": total_size,
            "used_gb": round(total_size / (1024**3), 3),
            "total_gb": Config.ROM_MAX_SIZE_GB,
            "free_gb": round(Config.ROM_MAX_SIZE_GB - total_size / (1024**3), 3),
            "allocations": self.meta["allocations"]
        }
    
    def store_model(self, name, data_bytes):
        """Store ML model in SamzCloud's ROM (not on host device)"""
        path = Config.ROM_MODELS / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data_bytes)
        
        size_gb = len(data_bytes) / (1024**3)
        if "models" in self.meta["allocations"]:
            self.meta["allocations"]["models"]["used_gb"] += size_gb
        self._save_meta()
        
        return str(path)
    
    def store_knowledge(self, name, data):
        """Store knowledge base entry"""
        path = Config.ROM_KNOWLEDGE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(data, str):
            path.write_text(data)
        else:
            path.write_bytes(data)
        
        return str(path)
    
    def read_knowledge(self, name):
        path = Config.ROM_KNOWLEDGE / name
        if path.exists():
            return path.read_text()
        return None
    
    def get_model_path(self, name):
        path = Config.ROM_MODELS / name
        if path.exists():
            return str(path)
        return None


class DiskFullError(Exception):
    pass
