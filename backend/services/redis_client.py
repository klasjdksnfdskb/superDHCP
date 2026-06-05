"""
Redis 客户端 — 缓存 & 限流 & IP Bitmap

连接池管理 + 辅助方法
"""

import json
import logging
from typing import Optional, Any
import redis.asyncio as aioredis
from app_settings import settings

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.ConnectionPool] = None


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接 (连接池复用)"""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis():
    """关闭 Redis 连接池"""
    global _pool
    if _pool:
        await _pool.disconnect()
        _pool = None


async def cache_get(key: str) -> Optional[Any]:
    """从缓存读取 (自动 JSON 反序列化)"""
    r = await get_redis()
    val = await r.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """写入缓存 (自动 JSON 序列化, 默认 TTL 60s)"""
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))


async def cache_delete(key: str) -> None:
    """删除缓存"""
    r = await get_redis()
    await r.delete(key)


async def cache_invalidate(pattern: str) -> int:
    """按模式删除缓存 (如 cache_invalidate('dashboard:*'))"""
    r = await get_redis()
    keys = await r.keys(pattern)
    if keys:
        return await r.delete(*keys)
    return 0


async def rate_limit_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """
    令牌桶 / 滑动窗口限流检查
    返回 True = 允许通过, False = 已达上限
    """
    r = await get_redis()
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, window_seconds)
    return current <= max_requests
