"""
SamzCloud Authentication Engine
API Key generation, proof-of-work CAPTCHA, rate limiting.
API keys used for: deploying projects, accessing SamzCloud services.
"""

import sqlite3
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from enum import Enum
from core.config import Config

class KeyType(Enum):
    FULL_ACCESS = "full_access"
    READ_ONLY = "read_only"
    DEPLOY_ONLY = "deploy_only"
    PROJECT_SPECIFIC = "project_specific"
    TEMPORARY = "temporary"

class AuthEngine:
    def __init__(self):
        self.db_path = Config.AUTH_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._active_challenges = {}
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                key_prefix TEXT NOT NULL,
                name TEXT,
                type TEXT NOT NULL,
                project_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used TIMESTAMP,
                use_count INTEGER DEFAULT 0,
                revoked INTEGER DEFAULT 0,
                revoked_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deploy_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_prefix TEXT,
                project_name TEXT,
                github_url TEXT,
                action TEXT,
                status TEXT,
                log_output TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                identifier TEXT PRIMARY KEY,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP,
                last_request TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ===== PROOF-OF-WORK CAPTCHA (No External API) =====
    
    def create_challenge(self, difficulty=4):
        """Create a proof-of-work challenge. No API key needed."""
        challenge = secrets.token_hex(16)
        challenge_id = secrets.token_hex(8)
        
        self._active_challenges[challenge_id] = {
            "challenge": challenge,
            "difficulty": difficulty,
            "created_at": time.time(),
            "solved": False
        }
        
        self._clean_old_challenges()
        
        return {
            "challenge_id": challenge_id,
            "challenge": challenge,
            "difficulty": difficulty,
            "target": "0" * difficulty,
            "hint": f"Find nonce where SHA256('{challenge}' + nonce) starts with {'0' * difficulty}"
        }
    
    def verify_challenge(self, challenge_id, nonce):
        """Verify proof-of-work solution"""
        if challenge_id not in self._active_challenges:
            return False
        
        data = self._active_challenges[challenge_id]
        
        if data["solved"]:
            return False
        
        hash_input = f"{data['challenge']}{nonce}"
        hash_output = hashlib.sha256(hash_input.encode()).hexdigest()
        
        if hash_output.startswith("0" * data["difficulty"]):
            data["solved"] = True
            return True
        
        return False
    
    def _clean_old_challenges(self):
        now = time.time()
        expired = [cid for cid, d in self._active_challenges.items() 
                   if now - d["created_at"] > 300]
        for cid in expired:
            del self._active_challenges[cid]
    
    # ===== API KEY MANAGEMENT =====
    
    def generate_api_key(self, challenge_id=None, nonce=None,
                         name=None, key_type=KeyType.FULL_ACCESS,
                         project_name=None, expires_in_days=None):
        """Generate API key with CAPTCHA verification"""
        
        if challenge_id and nonce:
            if not self.verify_challenge(challenge_id, nonce):
                raise PermissionError("CAPTCHA verification failed")
        else:
            raise PermissionError("CAPTCHA required. Get challenge from /auth/challenge")
        
        raw_key = f"sk_{secrets.token_hex(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:11]
        
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        key_id = f"key_{secrets.token_hex(8)}"
        
        cursor.execute("""
            INSERT INTO api_keys (id, key_hash, key_prefix, name, type, project_name, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (key_id, key_hash, key_prefix, name, key_type.value, project_name, expires_at))
        
        conn.commit()
        conn.close()
        
        return {
            "id": key_id,
            "api_key": raw_key,
            "prefix": key_prefix,
            "name": name,
            "type": key_type.value,
            "expires_at": expires_at,
            "warning": "Save this key now. It will not be shown again."
        }
    
    def list_api_keys(self):
        """List all API keys (no full keys exposed)"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, key_prefix, name, type, project_name,
                   created_at, expires_at, last_used, use_count, revoked
            FROM api_keys ORDER BY created_at DESC
        """)
        
        keys = []
        for row in cursor.fetchall():
            keys.append({
                "id": row[0],
                "prefix": row[1],
                "name": row[2],
                "type": row[3],
                "project": row[4],
                "created": row[5],
                "expires": row[6],
                "last_used": row[7],
                "use_count": row[8],
                "revoked": bool(row[9])
            })
        
        conn.close()
        return keys
    
    def revoke_api_key(self, key_id):
        """Revoke an API key"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT revoked, key_prefix FROM api_keys WHERE id = ?", (key_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {"error": "Key not found"}
        
        if result[0] == 1:
            conn.close()
            return {"error": "Already revoked", "prefix": result[1]}
        
        cursor.execute("""
            UPDATE api_keys SET revoked = 1, revoked_at = ? WHERE id = ?
        """, (datetime.now().isoformat(), key_id))
        
        conn.commit()
        conn.close()
        
        return {"revoked": True, "prefix": result[1], "message": f"Key {result[1]} revoked"}
    
    def validate_api_key(self, api_key):
        """Validate an API key on each request"""
        if not api_key or not api_key.startswith("sk_"):
            return False
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, type, project_name, expires_at, revoked, use_count
            FROM api_keys WHERE key_hash = ?
        """, (key_hash,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        key_id, key_type, project_name, expires_at, revoked, use_count = result
        
        if revoked:
            conn.close()
            return False
        
        if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
            conn.close()
            return False
        
        cursor.execute("""
            UPDATE api_keys SET last_used = ?, use_count = ? WHERE id = ?
        """, (datetime.now().isoformat(), use_count + 1, key_id))
        
        conn.commit()
        conn.close()
        
        return {"valid": True, "type": key_type, "project": project_name}
    
    def check_rate_limit(self, identifier, max_requests=100, window_seconds=60):
        """Rate limiting"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now()
        
        cursor.execute(
            "SELECT request_count, window_start FROM rate_limits WHERE identifier = ?",
            (identifier,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.execute(
                "INSERT INTO rate_limits VALUES (?, 1, ?, ?)",
                (identifier, now.isoformat(), now.isoformat())
            )
            conn.commit()
            conn.close()
            return True
        
        count, window_start = result
        window_start = datetime.fromisoformat(window_start)
        
        if (now - window_start).total_seconds() > window_seconds:
            cursor.execute(
                "UPDATE rate_limits SET request_count = 1, window_start = ?, last_request = ? WHERE identifier = ?",
                (now.isoformat(), now.isoformat(), identifier)
            )
            conn.commit()
            conn.close()
            return True
        
        if count >= max_requests:
            conn.close()
            return False
        
        cursor.execute(
            "UPDATE rate_limits SET request_count = ?, last_request = ? WHERE identifier = ?",
            (count + 1, now.isoformat(), identifier)
        )
        conn.commit()
        conn.close()
        return True
    
    def log_deploy(self, api_key_prefix, project_name, github_url, action, status, log_output=""):
        """Log deployment activity"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO deploy_logs (api_key_prefix, project_name, github_url, action, status, log_output)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (api_key_prefix, project_name, github_url, action, status, log_output[:10000]))
        
        conn.commit()
        conn.close()
    
    def get_deploy_logs(self, project_name=None, limit=50):
        """Get deployment logs"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if project_name:
            cursor.execute(
                "SELECT * FROM deploy_logs WHERE project_name = ? ORDER BY created_at DESC LIMIT ?",
                (project_name, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM deploy_logs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "api_key_prefix": row[1],
                "project_name": row[2],
                "github_url": row[3],
                "action": row[4],
                "status": row[5],
                "log_output": row[6][:500] if row[6] else "",
                "created_at": row[7]
            })
        
        conn.close()
        return logs
