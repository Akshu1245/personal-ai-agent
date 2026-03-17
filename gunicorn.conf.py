"""
JARVIS Gunicorn Production Config

Author: Rashi AI — Built for Akshay
"""

import os
import multiprocessing

# ── Binding ───────────────────────────────
bind = "0.0.0.0:5000"
backlog = 512

# ── Workers ───────────────────────────────
# Socket.IO with eventlet requires exactly 1 worker
# (unless Redis message queue is used for multi-worker pub/sub)
workers = 1
worker_class = "eventlet"
worker_connections = 1000
timeout = 120
keepalive = 5

# ── Logging ───────────────────────────────
loglevel = "info"
accesslog = "logs/access.log"
errorlog = "logs/error.log"
capture_output = True
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sms'

# ── Process naming ────────────────────────
proc_name = "jarvis"

# ── Hooks ─────────────────────────────────
def on_starting(server):
    os.makedirs("logs", exist_ok=True)
    print("🚀 JARVIS production server starting...")

def post_fork(server, worker):
    print(f"⚡ Worker spawned (pid: {worker.pid})")

def worker_exit(server, worker):
    print(f"Worker exited (pid: {worker.pid})")
