"""
SamzCloud Deploy Engine
Auto-deploys projects from GitHub with full logging.
API keys required for deployment.
"""

import subprocess
import json
import time
import signal
import os
import threading
from pathlib import Path
from datetime import datetime
from core.config import Config
from core.auth_engine import AuthEngine

class DeployEngine:
    """Auto-deploy engine with GitHub integration and logging"""
    
    def __init__(self, auth_engine: AuthEngine, storage):
        self.auth = auth_engine
        self.storage = storage
        self.base_dir = Config.STORAGE_PROJECTS
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.running = {}
        self.build_logs = {}
        self.config_file = Config.STORAGE_ROOT / "deploy_config.json"
        self.config = self._load_config()
        
        # Restore apps
        for name in self.config.get("apps", {}):
            try:
                self.start_app(name)
            except:
                pass
        
        # Auto-update thread
        threading.Thread(target=self._auto_update_loop, daemon=True).start()
    
    def _load_config(self):
        if self.config_file.exists():
            return json.loads(self.config_file.read_text())
        return {"apps": {}}
    
    def _save_config(self):
        self.config_file.write_text(json.dumps(self.config, indent=2))
    
    def add_app(self, name, github_url, api_key, branch="main",
                build_cmd=None, start_cmd=None, env_vars=None):
        """Register a new app for deployment. Requires API key."""
        
        # Validate API key
        validation = self.auth.validate_api_key(api_key)
        if not validation:
            raise PermissionError("Invalid or revoked API key")
        
        # Assign port
        port = 8001
        used_ports = [a.get("port", 0) for a in self.config.get("apps", {}).values()]
        while port in used_ports:
            port += 1
        
        self.config["apps"][name] = {
            "github_url": github_url,
            "branch": branch,
            "build_cmd": build_cmd or "pip install -r requirements.txt",
            "start_cmd": start_cmd or "python app.py",
            "port": port,
            "env_vars": env_vars or {},
            "status": "registered",
            "last_deploy": None,
            "created_by": validation.get("project", "unknown"),
            "created_at": datetime.now().isoformat()
        }
        self._save_config()
        
        # Log
        self.auth.log_deploy(
            api_key[:11], name, github_url, "register", "success"
        )
        
        return self.config["apps"][name]
    
    def deploy_app(self, name, api_key=None):
        """Deploy an app: pull from GitHub, build, start. With full logging."""
        app = self.config["apps"].get(name)
        if not app:
            return {"error": f"App '{name}' not found"}
        
        if api_key:
            validation = self.auth.validate_api_key(api_key)
            if not validation:
                raise PermissionError("Invalid API key")
        
        app_dir = self.base_dir / name
        build_log_lines = []
        
        def log(line):
            build_log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
        
        try:
            # Step 1: Clone or Pull
            log(f"Starting deployment for {name}")
            log(f"GitHub URL: {app['github_url']}")
            
            if app_dir.exists():
                log("Repository exists. Pulling latest changes...")
                result = subprocess.run(
                    ["git", "pull", "origin", app["branch"]],
                    cwd=app_dir, capture_output=True, text=True, timeout=120
                )
                log(result.stdout)
                if result.stderr:
                    log(f"Git: {result.stderr}")
            else:
                log("Cloning repository...")
                result = subprocess.run(
                    ["git", "clone", "-b", app["branch"], app["github_url"], str(app_dir)],
                    capture_output=True, text=True, timeout=300
                )
                log(result.stdout)
                if result.stderr:
                    log(f"Git: {result.stderr}")
            
            # Step 2: Build
            log("Running build command...")
            log(f"Command: {app['build_cmd']}")
            
            env = {**os.environ, **app.get("env_vars", {}), "PORT": str(app["port"])}
            
            build_result = subprocess.run(
                app["build_cmd"].split(),
                cwd=app_dir,
                capture_output=True,
                text=True,
                env=env,
                timeout=Config.MAX_BUILD_TIME_SECONDS
            )
            
            log("BUILD OUTPUT:")
            log(build_result.stdout[-2000:])
            
            if build_result.returncode != 0:
                log(f"BUILD FAILED: {build_result.stderr[-1000:]}")
                self.auth.log_deploy(
                    api_key[:11] if api_key else "system", name,
                    app["github_url"], "build", "failed",
                    build_result.stderr[-500:]
                )
                return {
                    "error": "Build failed",
                    "log": build_log_lines,
                    "build_stderr": build_result.stderr[-500:]
                }
            
            log("Build successful!")
            
            # Step 3: Stop old instance
            self.stop_app(name)
            log("Stopped previous instance (if any)")
            
            # Step 4: Start new instance
            self.start_app(name)
            log(f"Started on port {app['port']}")
            
            # Save
            app["status"] = "running"
            app["last_deploy"] = datetime.now().isoformat()
            self._save_config()
            
            # Record build in storage
            self.storage.record_build(name)
            
            # Save build log
            log_path = Config.STORAGE_BUILDS / f"{name}_{int(time.time())}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("\n".join(build_log_lines))
            
            # Auth log
            self.auth.log_deploy(
                api_key[:11] if api_key else "system", name,
                app["github_url"], "deploy", "success",
                "\n".join(build_log_lines[-20:])
            )
            
            return {
                "status": "deployed",
                "port": app["port"],
                "name": name,
                "log": build_log_lines,
                "build_log_path": str(log_path)
            }
            
        except subprocess.TimeoutExpired:
            log("DEPLOYMENT TIMEOUT")
            self.auth.log_deploy(
                api_key[:11] if api_key else "system", name,
                app["github_url"], "deploy", "timeout"
            )
            return {"error": "Deployment timed out", "log": build_log_lines}
            
        except Exception as e:
            log(f"ERROR: {str(e)}")
            app["status"] = "failed"
            self._save_config()
            self.auth.log_deploy(
                api_key[:11] if api_key else "system", name,
                app["github_url"], "deploy", "error", str(e)
            )
            return {"error": str(e), "log": build_log_lines}
    
    def start_app(self, name):
        app = self.config["apps"].get(name)
        if not app:
            return
        
        app_dir = self.base_dir / name
        if not app_dir.exists():
            return
        
        log_file = open(Config.STORAGE_LOGS / f"{name}.log", "a")
        env = {**os.environ, **app.get("env_vars", {}), "PORT": str(app["port"])}
        
        process = subprocess.Popen(
            app["start_cmd"].split(),
            cwd=app_dir,
            stdout=log_file,
            stderr=log_file,
            env=env,
            preexec_fn=os.setsid
        )
        
        self.running[name] = {"process": process, "log_file": log_file}
        app["status"] = "running"
        app["pid"] = process.pid
        self._save_config()
    
    def stop_app(self, name):
        if name in self.running:
            info = self.running[name]
            try:
                os.killpg(os.getpgid(info["process"].pid), signal.SIGTERM)
                info["process"].wait(timeout=5)
            except:
                try:
                    os.killpg(os.getpgid(info["process"].pid), signal.SIGKILL)
                except:
                    pass
            info["log_file"].close()
            del self.running[name]
    
    def get_app_logs(self, name, lines=100):
        """Get live logs for a running app"""
        log_path = Config.STORAGE_LOGS / f"{name}.log"
        if log_path.exists():
            content = log_path.read_text()
            log_lines = content.split("\n")
            return log_lines[-lines:]
        return []
    
    def get_build_logs(self, name):
        """Get stored build logs"""
        builds_dir = Config.STORAGE_BUILDS
        logs = []
        for f in sorted(builds_dir.glob(f"{name}_*.log"), reverse=True)[:10]:
            logs.append({
                "file": f.name,
                "content": f.read_text()[-2000:],
                "timestamp": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return logs
    
    def list_apps(self):
        result = {}
        for name, app in self.config.get("apps", {}).items():
            is_running = name in self.running
            if is_running:
                is_running = self.running[name]["process"].poll() is None
            
            result[name] = {
                "port": app["port"],
                "status": "running" if is_running else app.get("status", "stopped"),
                "last_deploy": app.get("last_deploy"),
                "github": app["github_url"],
                "branch": app.get("branch", "main")
            }
        return result
    
    def _auto_update_loop(self):
        """Check for GitHub updates every 5 minutes"""
        while True:
            time.sleep(300)
            for name in self.config.get("apps", {}):
                try:
                    app_dir = self.base_dir / name
                    if not app_dir.exists():
                        continue
                    
                    subprocess.run(["git", "fetch", "origin"],
                                   cwd=app_dir, capture_output=True, timeout=30)
                    result = subprocess.run(
                        ["git", "status", "-uno"],
                        cwd=app_dir, capture_output=True, text=True, timeout=10
                    )
                    
                    if "Your branch is behind" in result.stdout:
                        print(f"[AutoDeploy] Updating {name}...")
                        self.deploy_app(name)
                except Exception as e:
                    print(f"[AutoDeploy] Error checking {name}: {e}")
