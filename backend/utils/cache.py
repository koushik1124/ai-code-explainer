import hashlib
import json
import time
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache with TTL (Time To Live).
    
    Features:
    - Automatic expiration of old entries
    - Thread-safe operations
    - Configurable size and TTL
    - Memory efficient with automatic eviction
    """
    
    def __init__(self, max_size: int = 128, ttl_seconds: int = 3600):
        """
        Initialize the LRU cache.
        
        Args:
            max_size: Maximum number of entries (default: 128)
            ttl_seconds: Time to live for each entry in seconds (default: 3600 = 1 hour)
        """
        if max_size < 1:
            raise ValueError("max_size must be at least 1")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.store: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self._lock = threading.RLock()  # ✅ Thread safety
        self._hits = 0  # ✅ Cache statistics
        self._misses = 0
    
    def _evict_expired(self):
        """
        Remove expired entries from the cache.
        Must be called while holding the lock.
        """
        now = time.time()
        keys_to_delete = [
            k for k, (ts, _) in self.store.items() 
            if now - ts > self.ttl
        ]
        for k in keys_to_delete:
            del self.store[k]
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found and not expired, None otherwise
        """
        with self._lock:
            self._evict_expired()
            
            if key not in self.store:
                self._misses += 1
                return None
            
            ts, value = self.store.pop(key)
            
            # Check if expired (double-check)
            if time.time() - ts > self.ttl:
                self._misses += 1
                return None
            
            # Move to end = recently used
            self.store[key] = (ts, value)
            self._hits += 1
            return value
    
    def set(self, key: str, value: Dict[str, Any]):
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable dict)
        """
        with self._lock:
            self._evict_expired()
            
            # Remove if exists (will be re-added at end)
            if key in self.store:
                self.store.pop(key)
            
            # Evict least recently used if at capacity
            elif len(self.store) >= self.max_size:
                self.store.popitem(last=False)
            
            # Add new entry
            self.store[key] = (time.time(), value)
    
    def clear(self):
        """
        Clear all entries from the cache.
        """
        with self._lock:
            self.store.clear()
            self._hits = 0
            self._misses = 0
    
    def size(self) -> int:
        """
        Get the current number of entries in the cache.
        """
        with self._lock:
            return len(self.store)
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_rate_percent": round(hit_rate, 2),
                "current_size": len(self.store),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
            }
    
    def delete(self, key: str) -> bool:
        """
        Delete a specific entry from the cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was found and deleted, False otherwise
        """
        with self._lock:
            if key in self.store:
                del self.store[key]
                return True
            return False


def make_cache_key(prefix: str, payload: Dict[str, Any]) -> str:
    """
    Create a stable hash key based on payload.
    
    Args:
        prefix: Key prefix (e.g., "explain", "test", "refactor")
        payload: Dictionary to hash (must be JSON-serializable)
        
    Returns:
        Cache key string in format "prefix:hash"
        
    Example:
        >>> make_cache_key("explain", {"code": "def foo(): pass", "language": "python"})
        'explain:a1b2c3d4...'
    """
    try:
        # Create canonical JSON representation
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        
        # Generate SHA-256 hash
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        
        return f"{prefix}:{digest}"
    
    except (TypeError, ValueError) as e:
        # If payload is not JSON-serializable, create a fallback key
        fallback = f"{prefix}:error_{hash(str(payload))}"
        print(f"Warning: Could not create cache key for {prefix}: {e}. Using fallback: {fallback}")
        return fallback


def sanitize_cache_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ NEW: Sanitize payload before caching to ensure consistency.
    
    Removes keys that shouldn't affect caching (like request_id, timestamps).
    
    Args:
        payload: Original payload
        
    Returns:
        Sanitized payload suitable for cache key generation
    """
    # Keys to exclude from cache key generation
    exclude_keys = {"request_id", "timestamp", "user_id", "session_id"}
    
    return {
        k: v for k, v in payload.items() 
        if k not in exclude_keys
    }