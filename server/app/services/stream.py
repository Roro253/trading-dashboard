from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from typing import Any, AsyncIterator, Dict, Set

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
_CHANNEL_PREFIX = "stream:"


class StreamBroker:
    """Publish/subscribe abstraction backed by Redis when available, otherwise in-memory queues."""

    def __init__(self) -> None:
        settings = get_settings()
        self._redis_url = str(getattr(settings, "redis_url", "")) or ""
        self._redis: Redis | None = None
        self._lock = asyncio.Lock()
        self._subscribers: Dict[str, Set[asyncio.Queue[str]]] = defaultdict(set)

    async def publish(self, ticker: str, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload)
        key = ticker.upper()

        if await self._publish_redis(key, message):
            return

        await self._publish_local(key, message)

    @asynccontextmanager
    async def subscribe(self, ticker: str) -> AsyncIterator[asyncio.Queue[str]]:
        key = ticker.upper()

        if self._redis_url:
            try:
                redis = await self._get_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(self._channel(key))
                queue: asyncio.Queue[str] = asyncio.Queue()
                listener = asyncio.create_task(self._redis_listener(pubsub, queue, key))
                try:
                    yield queue
                    return
                finally:
                    listener.cancel()
                    with suppress(asyncio.CancelledError):
                        await listener
                    await pubsub.unsubscribe(self._channel(key))
                    await pubsub.close()
            except RedisError as exc:
                logger.warning("stream.redis.subscribe_failed", channel=key, error=str(exc))
                await self._teardown_redis()

        queue = asyncio.Queue[str]()
        async with self._lock:
            self._subscribers[key].add(queue)

        try:
            yield queue
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(key)
                if subscribers:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(key, None)

    async def _publish_redis(self, key: str, message: str) -> bool:
        if not self._redis_url:
            return False
        try:
            redis = await self._get_redis()
            await redis.publish(self._channel(key), message)
            return True
        except RedisError as exc:
            logger.warning("stream.redis.publish_failed", channel=key, error=str(exc))
            await self._teardown_redis()
            return False

    async def _publish_local(self, key: str, message: str) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(key, ()))
        for queue in queues:
            await queue.put(message)

    async def _redis_listener(self, pubsub: PubSub, queue: asyncio.Queue[str], key: str) -> None:
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await queue.put(str(data))
        except asyncio.CancelledError:
            raise
        except RedisError as exc:
            logger.warning("stream.redis.listener_error", channel=key, error=str(exc))

    async def _get_redis(self) -> Redis:
        if self._redis is None and self._redis_url:
            self._redis = Redis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)
        if self._redis is None:
            raise RedisError("Redis URL not configured")
        return self._redis

    async def _teardown_redis(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except RedisError as exc:  # pragma: no cover - defensive cleanup
                logger.warning("stream.redis.close_failed", error=str(exc))
            finally:
                self._redis = None
        self._redis_url = ""

    @staticmethod
    def _channel(key: str) -> str:
        return f"{_CHANNEL_PREFIX}{key}"


_BROKER: StreamBroker | None = None


def get_stream_broker() -> StreamBroker:
    global _BROKER
    if _BROKER is None:
        _BROKER = StreamBroker()
    return _BROKER
