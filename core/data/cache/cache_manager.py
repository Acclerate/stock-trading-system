"""Thin cache wrapper for v2 modules."""

from data.cache_manager import CacheManager


class V2CacheManager:
    """Delegate cache operations to the existing repository cache layer."""

    @staticmethod
    def initialize() -> None:
        CacheManager.initialize()

    @staticmethod
    def clear_expired_cache() -> None:
        CacheManager.clear_expired_cache()

    @staticmethod
    def clear_all_cache() -> None:
        CacheManager.clear_all_cache()

    @staticmethod
    def get_cache_stats() -> dict:
        return CacheManager.get_cache_stats()
