"""
Omni-cache runtime integration for AI Content Classifier.

Provides a lazy-initialized singleton wrapper around omni-cache so services can
use unified cache APIs while keeping graceful fallback when dependencies are not
installed.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any, Generic, Set, TypeVar

from ai_content_classifier.core.logger import LoggableMixin

T = TypeVar("T")


class OmniCacheRuntime(LoggableMixin):
    """Lightweight wrapper around an optional omni-cache manager."""

    def __init__(self) -> None:
        self.__init_logger__()
        self._manager: Any | None = None
        self._initialized = False
        self._lock = RLock()
        self._namespace_state_lock = RLock()
        self._namespace_keys: dict[tuple[str, str], Set[str]] = {}
        self._namespace_stats: dict[tuple[str, str], dict[str, int]] = {}

    def _initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return

            try:
                from omni_cache import CacheBackend, create_adapter, setup

                manager = setup(auto_discover=True, log_level="WARNING")

                # Ensure a memory adapter exists for deterministic local caching.
                try:
                    adapters = set(manager.list_adapters())
                except Exception:
                    adapters = set()

                if "memory" not in adapters:
                    memory_adapter = create_adapter(
                        CacheBackend.MEMORY,
                        {"name": "memory", "max_size": 10000, "default_ttl": 600},
                    )
                    manager.register_adapter("memory", memory_adapter)

                self._manager = manager
                self.logger.info("Omni-cache runtime initialized")
            except Exception as exc:
                self._manager = None
                self.logger.warning(
                    "Omni-cache unavailable, using local fallbacks: %s", exc
                )
            finally:
                self._initialized = True

    @property
    def manager(self) -> Any | None:
        """Return the global omni-cache manager if available."""
        self._initialize()
        return self._manager

    def is_available(self) -> bool:
        self._initialize()
        return self._manager is not None

    def get(self, key: str, default: Any = None, adapter: str = "memory") -> Any:
        mgr = self.manager
        if mgr is None:
            return default
        try:
            return mgr.get(key, default=default, adapter=adapter)
        except Exception:
            return default

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | float | None = None,
        adapter: str = "memory",
    ) -> bool:
        mgr = self.manager
        if mgr is None:
            return False
        try:
            return bool(mgr.set(key, value, ttl=ttl, adapter=adapter))
        except Exception:
            return False

    def delete(self, key: str, adapter: str = "memory") -> bool:
        mgr = self.manager
        if mgr is None:
            return False
        try:
            return bool(mgr.delete(key, adapter=adapter))
        except Exception:
            return False

    def clear(self, adapter: str = "memory") -> bool:
        mgr = self.manager
        if mgr is None:
            return False
        try:
            return bool(mgr.clear(adapter=adapter))
        except Exception:
            return False

    def memory_cache(
        self,
        namespace: str,
        *,
        default_ttl: int | float | None = None,
        adapter: str = "memory",
    ) -> "NamespacedMemoryCache":
        """Create a namespaced key/value cache on top of the memory adapter."""
        return NamespacedMemoryCache(
            runtime=self,
            namespace=namespace,
            default_ttl=default_ttl,
            adapter=adapter,
        )

    def register_smartpool_adapter(
        self,
        name: str,
        factory_function: Callable[..., Any],
        factory_validate_function: Callable[..., Any] | None = None,
        **extra_config: Any,
    ) -> bool:
        """
        Register a SmartPool-backed pool adapter in omni-cache.

        Useful for future object-pooling migrations while keeping cache + pool
        under one manager.
        """
        mgr = self.manager
        if mgr is None:
            return False

        try:
            from omni_cache import CacheBackend, create_adapter

            config = {
                "name": name,
                "factory_function": factory_function,
                "factory_validate_function": factory_validate_function,
                **extra_config,
            }
            adapter = create_adapter(CacheBackend.SMARTPOOL, config)
            return bool(mgr.register_adapter(name, adapter))
        except Exception as exc:
            self.logger.warning(
                "Failed to register smartpool adapter '%s': %s", name, exc
            )
            return False

    def get_namespace_state(
        self, namespace: str, adapter: str
    ) -> tuple[Set[str], dict[str, int], Any]:
        """Return shared bookkeeping objects for a namespace across wrapper instances."""
        cache_key = (adapter, namespace)
        with self._namespace_state_lock:
            keys = self._namespace_keys.setdefault(cache_key, set())
            stats = self._namespace_stats.setdefault(
                cache_key, {"hits": 0, "misses": 0}
            )
        return keys, stats, self._namespace_state_lock


class NamespacedMemoryCache:
    """Small namespaced helper around omni-cache's key/value adapter."""

    def __init__(
        self,
        *,
        runtime: OmniCacheRuntime,
        namespace: str,
        default_ttl: int | float | None = None,
        adapter: str = "memory",
    ) -> None:
        self._runtime = runtime
        self._namespace = namespace.strip(":")
        self._default_ttl = default_ttl
        self._adapter = adapter
        self._keys, self._stats, self._lock = runtime.get_namespace_state(
            self._namespace, self._adapter
        )

    def _full_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str, default: Any = None) -> Any:
        value = self._runtime.get(
            self._full_key(key), default=default, adapter=self._adapter
        )
        with self._lock:
            if value is default:
                self._stats["misses"] += 1
            else:
                self._stats["hits"] += 1
        return value

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        success = self._runtime.set(
            self._full_key(key),
            value,
            ttl=self._default_ttl if ttl is None else ttl,
            adapter=self._adapter,
        )
        if success:
            with self._lock:
                self._keys.add(key)
        return success

    def delete(self, key: str) -> bool:
        success = self._runtime.delete(self._full_key(key), adapter=self._adapter)
        with self._lock:
            self._keys.discard(key)
        return success

    def clear(self) -> None:
        with self._lock:
            keys: list[str] = list(self._keys)
            self._keys.clear()
            self._stats["hits"] = 0
            self._stats["misses"] = 0
        for key in keys:
            self._runtime.delete(self._full_key(key), adapter=self._adapter)

    def size(self) -> int:
        with self._lock:
            return len(self._keys)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            hits = self._stats["hits"]
            misses = self._stats["misses"]
            total = hits + misses
            return {
                "namespace": self._namespace,
                "entries": len(self._keys),
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / total if total else 0.0,
            }


class SmartPoolHandle(Generic[T]):
    """Thin runtime wrapper around a single omni-cache SmartPool adapter."""

    def __init__(
        self,
        *,
        runtime: OmniCacheRuntime,
        name: str,
        factory: Any,
        initial_size: int = 1,
        min_size: int = 0,
        max_size: int = 100,
        max_size_per_key: int = 20,
        max_age_seconds: int = 300,
        cleanup_interval: int = 60,
        enable_background_cleanup: bool = True,
        enable_performance_metrics: bool = True,
        enable_auto_tuning: bool = False,
        auto_tuning_interval: int = 60,
        auto_wrap_objects: bool = False,
        factory_args: tuple[Any, ...] | None = None,
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        self._runtime = runtime
        self._factory = factory
        self._name = name
        self._next_id = 1
        self._active_objects: dict[int, Any] = {}
        self._shut_down = False

        config: dict[str, Any] = {
            "name": name,
            "factory_function": self._factory.create,
            "factory_validate_function": getattr(self._factory, "validate", None),
            "initial_size": initial_size,
            "min_size": min_size,
            "max_size": max_size,
            "max_size_per_key": max_size_per_key,
            "max_age_seconds": max_age_seconds,
            "cleanup_interval": cleanup_interval,
            "enable_background_cleanup": enable_background_cleanup,
            "enable_performance_metrics": enable_performance_metrics,
            "enable_auto_tuning": enable_auto_tuning,
            "auto_tuning_interval": auto_tuning_interval,
            "auto_wrap_objects": auto_wrap_objects,
            "extra_config": {
                "reset_func": getattr(self._factory, "reset", None),
                "destroy_func": getattr(self._factory, "destroy", None),
                **(extra_config or {}),
            },
        }
        if factory_args:
            config["factory_args"] = factory_args

        if not self._runtime.register_smartpool_adapter(**config):
            raise RuntimeError(f"Unable to register SmartPool adapter '{name}'")

    def _get_manager(self) -> Any:
        manager = self._runtime.manager
        if manager is None:
            raise RuntimeError("omni-cache manager unavailable")
        return manager

    def _get_adapter(self) -> Any:
        adapter = self._get_manager().get_adapter(self._name)
        if adapter is None:
            raise RuntimeError(f"SmartPool adapter '{self._name}' not registered")
        return adapter

    @staticmethod
    def _unwrap_object(obj: Any) -> Any:
        return obj._obj if hasattr(obj, "_obj") else obj

    def acquire(self, *args: Any, **kwargs: Any) -> tuple[int, str, T]:
        if self._shut_down:
            raise RuntimeError("Pool is shut down")

        pooled_obj = self._get_adapter().get(*args, **kwargs)
        if pooled_obj is None:
            raise RuntimeError("No object available from pool")

        try:
            key = self._factory.get_key(*args, **kwargs)
        except Exception:
            key = "default_pool_key"

        obj_id = self._next_id
        self._next_id += 1
        self._active_objects[obj_id] = pooled_obj
        return obj_id, key, self._unwrap_object(pooled_obj)

    def release(self, obj_id: int, key: str, obj: T) -> None:
        _ = key
        if self._shut_down:
            return

        pooled_obj = self._active_objects.pop(obj_id, None)
        self._get_adapter().put(pooled_obj if pooled_obj is not None else obj)

    def clear(self) -> None:
        adapter = self._get_adapter()
        if hasattr(adapter, "clear"):
            adapter.clear()
        self._active_objects.clear()

    def shutdown(self) -> None:
        if self._shut_down:
            return

        self._active_objects.clear()
        self._get_manager().remove_adapter(self._name)
        self._shut_down = True

    def get_stats(self) -> dict[str, Any]:
        try:
            adapter = self._get_adapter()
            if hasattr(adapter, "get_detailed_smartpool_stats"):
                detailed = adapter.get_detailed_smartpool_stats()
                basic = (
                    detailed.get("basic_stats", {})
                    if isinstance(detailed, dict)
                    else {}
                )
                counters = basic.get("counters", {}) if isinstance(basic, dict) else {}
                pooled = basic.get(
                    "total_pooled_objects", basic.get("pooled_objects", 0)
                )
                active = basic.get(
                    "active_objects_count", basic.get("active_objects", 0)
                )
                return {
                    "hits": counters.get("hits", 0),
                    "misses": counters.get("misses", 0),
                    "creates": counters.get("creates", 0),
                    "reuses": counters.get("reuses", 0),
                    "evictions": counters.get("evictions", 0),
                    "expired": counters.get("expired", 0),
                    "corrupted": counters.get("corrupted", 0),
                    "validation_failures": counters.get("validation_failures", 0),
                    "reset_failures": counters.get("reset_failures", 0),
                    "pooled_objects": pooled,
                    "active_objects": active,
                    "total_memory_objects": int(pooled) + int(active),
                }
        except Exception:
            pass

        return {
            "hits": 0,
            "misses": 0,
            "creates": 0,
            "reuses": 0,
            "evictions": 0,
            "expired": 0,
            "corrupted": 0,
            "validation_failures": 0,
            "reset_failures": 0,
            "pooled_objects": 0,
            "active_objects": 0,
            "total_memory_objects": 0,
        }


_RUNTIME: OmniCacheRuntime | None = None
_RUNTIME_LOCK = RLock()


def get_cache_runtime() -> OmniCacheRuntime:
    """Return singleton runtime wrapper."""
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME

    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = OmniCacheRuntime()
        return _RUNTIME
