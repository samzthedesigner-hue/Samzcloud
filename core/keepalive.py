"""
SamzCloud Keepalive
Prevents Render sleep and Termux kill.
"""

import threading
import time
import requests

def keepalive_render():
    """Ping every 10 minutes to prevent Render free tier sleep"""
    while True:
        time.sleep(600)
        try:
            requests.get("https://samzcloud.onrender.com/health", timeout=10)
        except:
            pass

def keepalive_termux():
    """Write heartbeat to prevent Android from killing Termux"""
    while True:
        time.sleep(60)
        try:
            with open("/data/data/com.termux/files/home/samzcloud_storage/logs/heartbeat.log", "a") as f:
                f.write(f"{time.time()}\n")
        except:
            pass

def start_keepalive():
    from core.config import Config
    if Config.DEPLOYMENT == "render":
        threading.Thread(target=keepalive_render, daemon=True).start()
    else:
        threading.Thread(target=keepalive_termux, daemon=True).start()
