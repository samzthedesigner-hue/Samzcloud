"""
Code Whisperer - Cross-Repository Intelligence
Tracks dependencies across repos, detects breaking changes.
"""

import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

class CodeWhisperer:
    def __init__(self, storage_engine, groq_client):
        self.storage = storage_engine
        self.groq = groq_client
        self.repo_index = {}
    
    def index_repository(self, repo_name: str, files: List[Dict]) -> Dict:
        repo_data = {
            "name": repo_name,
            "files": {},
            "exports": {},
            "imports": {},
            "apis": {},
            "indexed_at": datetime.now().isoformat()
        }
        
        for file_info in files:
            path = file_info["path"]
            content = file_info["content"]
            language = file_info.get("language", "unknown")
            
            file_hash = hashlib.md5(content.encode()).hexdigest()
            exports = self._extract_exports(content, language)
            imports = self._extract_imports(content, language)
            
            repo_data["files"][path] = {"hash": file_hash, "size": len(content), "language": language}
            repo_data["exports"].update(exports)
            repo_data["imports"].update(imports)
        
        self.repo_index[repo_name] = repo_data
        self.storage.write_file(f"code_index/{repo_name}.json", json.dumps(repo_data))
        
        return {"indexed": repo_name, "files": len(repo_data["files"]), "exports": len(repo_data["exports"])}
    
    def find_cross_repo_bugs(self, changed_repo: str, changed_files: List[Dict]) -> Dict:
        changed_exports = set()
        for f in changed_files:
            exports = self._extract_exports(f["content"], f.get("language", "unknown"))
            changed_exports.update(exports.keys())
        
        affected = []
        for repo_name, repo_data in self.repo_index.items():
            if repo_name == changed_repo:
                continue
            
            repo_imports = set()
            for imports in repo_data["imports"].values():
                repo_imports.update(imports)
            
            broken = changed_exports.intersection(repo_imports)
            if broken:
                affected_files = []
                for fp, imps in repo_data["imports"].items():
                    if broken.intersection(imps):
                        affected_files.append(fp)
                
                affected.append({
                    "repo": repo_name,
                    "broken_exports": list(broken),
                    "affected_files": affected_files,
                    "severity": "high" if len(affected_files) > 3 else "medium"
                })
        
        return {"changed_repo": changed_repo, "affected_repos": affected, "total_affected": len(affected)}
    
    def _extract_exports(self, content: str, language: str) -> Dict:
        exports = {}
        lines = content.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("def "):
                name = line.split("def ")[1].split("(")[0]
                exports[name] = {"type": "function", "line": i+1}
            elif line.startswith("class "):
                name = line.split("class ")[1].split("(")[0].split(":")[0]
                exports[name] = {"type": "class", "line": i+1}
        return exports
    
    def _extract_imports(self, content: str, language: str) -> Dict:
        imports = defaultdict(list)
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("import "):
                module = line.split("import ")[1].split(" ")[0]
                imports["*"].append(module)
            elif line.startswith("from "):
                parts = line.split(" import ")
                if len(parts) == 2:
                    for name in parts[1].split(","):
                        imports[name.strip()].append(parts[0].replace("from ", ""))
        return dict(imports)
