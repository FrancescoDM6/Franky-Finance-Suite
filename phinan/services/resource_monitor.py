"""Resource monitor for graceful degradation on constrained environments.

Tracks memory/CPU usage and gates heavyweight operations to prevent OOM kills
on Oracle Free Tier ARM instances.
"""

import logging
import os
import threading
from typing import Optional


logger = logging.getLogger(__name__)


# Feature resource requirements (relative weight)
FEATURE_REQUIREMENTS = {
    "local_sentiment": 0.3,   # FinBERT model ~1.5GB
    "local_llm": 0.4,         # Ollama model ~2-4GB
    "embeddings": 0.15,       # sentence-transformers ~500MB
    "volatility": 0.05,       # GARCH is lightweight
}

# Default thresholds
DEFAULT_MEMORY_THRESHOLD = 85  # Percent


class ResourceMonitor:
    """Monitor system resources and gate expensive operations.
    
    Usage:
        monitor = get_resource_monitor()
        
        if monitor.is_safe_to_run("local_sentiment"):
            # Load FinBERT and run
        else:
            # Fall back to cloud API
    """
    
    _instance: Optional["ResourceMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ResourceMonitor":
        """Thread-safe singleton with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._psutil = None
        self._memory_threshold = int(
            os.environ.get("MAX_MEMORY_THRESHOLD_PERCENT", DEFAULT_MEMORY_THRESHOLD)
        )
        self._disabled_features: set[str] = set()
        self._initialized = True
    
    def _get_psutil(self):
        """Lazy-load psutil."""
        if self._psutil is None:
            try:
                import psutil
                self._psutil = psutil
            except ImportError:
                logger.warning("psutil not installed. Resource monitoring disabled.")
                return None
        return self._psutil
    
    def get_memory_percent(self) -> float:
        """Get current memory usage as percentage."""
        psutil = self._get_psutil()
        if psutil is None:
            return 0.0  # Assume safe if can't check
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0
    
    def get_cpu_percent(self) -> float:
        """Get current CPU usage as percentage."""
        psutil = self._get_psutil()
        if psutil is None:
            return 0.0
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0
    
    def is_safe_to_run(self, feature: str) -> bool:
        """Check if it's safe to run a heavyweight feature.
        
        Args:
            feature: Feature name (e.g., "local_sentiment", "local_llm")
            
        Returns:
            True if resources are available, False if should skip/fallback
        """
        # Check if manually disabled
        if feature in self._disabled_features:
            return False
        
        # Check memory threshold
        current_memory = self.get_memory_percent()
        if current_memory >= self._memory_threshold:
            logger.warning(
                "Memory at %.1f%% (threshold: %s%%). Blocking %s.",
                current_memory,
                self._memory_threshold,
                feature,
            )
            return False
        
        # Check if feature would push us over
        feature_weight = FEATURE_REQUIREMENTS.get(feature, 0.1)
        projected_memory = current_memory + (feature_weight * 20)  # Rough estimate
        
        if projected_memory >= self._memory_threshold:
            logger.warning(
                "Projected memory %.1f%% would exceed threshold. Blocking %s.",
                projected_memory,
                feature,
            )
            return False
        
        return True
    
    def disable_feature(self, feature: str):
        """Manually disable a feature (e.g., after OOM recovery)."""
        self._disabled_features.add(feature)
        logger.info("Feature '%s' disabled by ResourceMonitor", feature)
    
    def enable_feature(self, feature: str):
        """Re-enable a previously disabled feature."""
        self._disabled_features.discard(feature)
    
    def get_status(self) -> dict:
        """Get current resource status."""
        return {
            "memory_percent": self.get_memory_percent(),
            "cpu_percent": self.get_cpu_percent(),
            "memory_threshold": self._memory_threshold,
            "disabled_features": list(self._disabled_features),
        }
    
    def health_check(self) -> bool:
        """Check if monitor is operational."""
        return self._get_psutil() is not None


def get_resource_monitor() -> ResourceMonitor:
    """Get singleton resource monitor instance."""
    return ResourceMonitor()
