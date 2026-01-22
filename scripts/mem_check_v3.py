import psutil

print(f"{'PID':<10} {'Memory (MB)':<15} {'Name':<15} {'Command Line'}")
print("-" * 80)

for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
    try:
        name = proc.info['name'].lower()
        if "python" in name or "node" in name:
            mem_mb = proc.info['memory_info'].rss / 1024 / 1024
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            print(f"{proc.info['pid']:<10} {mem_mb:<15.2f} {proc.info['name']:<15} {cmdline[:100]}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
