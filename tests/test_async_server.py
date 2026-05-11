"""
Async tests for the server-backed LatZero client.
"""

import pytest


pytestmark = pytest.mark.asyncio


class TestAsyncLatZero:
    async def test_async_connect_and_get_set(self, latzero_server, unique_pool_name):
        from latzero import AsyncLatZero

        client = AsyncLatZero(
            "latzero://async-client",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            await client.set("value", {"ok": True})
            assert await client.get("value") == {"ok": True}
        finally:
            await client.disconnect()
