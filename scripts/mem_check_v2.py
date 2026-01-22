import os
import sys
import psutil

print(f"{'PID':<10} {'Memory (MB)':<15} {'Command Line'}")
print("-" * 60)

for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
    try:
        cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
        if "python" in proc.info['name'].lower() or "node" in proc.info['name'].lower():
            if "phinan" in cmdline.lower() or "reflex" in cmdline.lower() or "uvicorn" in cmdline.lower() or "next" in cmdline.lower():
                mem_mb = proc.info['memory_info'].rss / 1024 / 1024
                print(f"{proc.info['pid']:<10} {mem_mb:<15.2f} {cmdline[:100]}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
