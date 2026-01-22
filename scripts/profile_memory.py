"""
Utility script to profile memory usage of the Phinan Finance Suite.
Usage: python scripts/profile_memory.py
"""
import os
import sys
import time
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phinan.core.memory import get_memory_snapshot, start_memory_tracing, stop_memory_tracing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def profile_startup():
    logger.info("Starting memory profile...")
    start_memory_tracing()
    
    snapshot_start = get_memory_snapshot()
    logger.info(f"Baseline Memory: {snapshot_start.current_mb:.2f} MB")
    
    # Simulate loading heavy modules
    logger.info("Simulating service loading...")
    from phinan.services import services
    
    # Access market data (triggers lazy load)
    _ = services.market_data
    snapshot_market = get_memory_snapshot()
    logger.info(f"After Market Data Service: {snapshot_market.current_mb:.2f} MB (Delta: {snapshot_market.current_mb - snapshot_start.current_mb:.2f} MB)")
    
    # Access LLM
    _ = services.llm
    snapshot_llm = get_memory_snapshot()
    logger.info(f"After LLM Service: {snapshot_llm.current_mb:.2f} MB (Delta: {snapshot_llm.current_mb - snapshot_market.current_mb:.2f} MB)")
    
    allocations = stop_memory_tracing()
    if allocations:
        logger.info("Top 5 Allocations:")
        for file, size in allocations[:5]:
            logger.info(f"  {file}: {size:.2f} MB")

if __name__ == "__main__":
    profile_startup()
