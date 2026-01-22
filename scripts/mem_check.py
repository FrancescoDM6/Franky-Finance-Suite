import os
import sys
import gc

# Add current directory to path
sys.path.append(os.getcwd())

from phinan.core.memory import get_memory_snapshot
from phinan.services.resource_monitor import get_resource_monitor
from phinan.config.settings import settings

print("--- App Memory Snapshot ---")
try:
    snap = get_memory_snapshot()
    print(f"Current MB: {snap.current_mb}")
    print(f"Peak MB: {snap.peak_mb}")
    print(f"GC Objects: {snap.gc_objects}")
except Exception as e:
    print(f"Error getting snapshot: {e}")

print("\n--- Resource Monitor Status ---")
try:
    mon = get_resource_monitor()
    print(mon.get_status())
except Exception as e:
    print(f"Error getting status: {e}")

print("\n--- Database ---")
try:
    db_path = os.path.expanduser(settings.database.path)
    print(f"DB Path: {db_path}")
    if os.path.exists(db_path):
        print(f"DB Size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB")
    else:
        print("DB file not found at path")
except Exception as e:
    print(f"Error checking DB: {e}")

print("\n--- Configuration Settings (Memory Impact) ---")
print(f"Enable Sentiment: {settings.ai_services.enable_sentiment}")
print(f"Enable Volatility: {settings.ai_services.enable_volatility}")
print(f"Enable Embeddings: {settings.ai_services.enable_embeddings}")
print(f"Market Data Cache TTL: {settings.market_data.cache_ttl_minutes} mins")

import psutil
print("\n--- Process Tree ---")
current_process = psutil.Process()
print(f"Main Process: {current_process.name()} (PID: {current_process.pid}) - {current_process.memory_info().rss / 1024 / 1024:.2f} MB")
for child in current_process.children(recursive=True):
    try:
        print(f"Child Process: {child.name()} (PID: {child.pid}) - {child.memory_info().rss / 1024 / 1024:.2f} MB")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

