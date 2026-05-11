"""
Integration tests for the server-backed LatZero client.
"""

import time

import pytest


class TestLatZeroServerMode:
    """End-to-end tests against the local latzero-server."""

    def test_connect_and_basic_buffer_ops(self, latzero_server, unique_pool_name):
        from latzero import LatZero

        client = LatZero(
            "latzero://client-one",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            client.set("alpha", {"value": 1}, persistent=True)
            assert client.get("alpha") == {"value": 1}
            assert client.exists("alpha")
            assert "alpha" in client.keys()
        finally:
            client.disconnect()

    def test_auth_pool_rejects_wrong_token(self, latzero_server, unique_pool_name):
        from latzero import AuthenticationError, LatZero

        owner = LatZero(
            "latzero://owner",
            pool=unique_pool_name,
            auth_token="secret",
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            with pytest.raises(AuthenticationError):
                intruder = LatZero(
                    "latzero://intruder",
                    pool=unique_pool_name,
                    auth_token="wrong",
                    host=latzero_server["host"],
                    port=latzero_server["port"],
                )
                intruder.disconnect()
        finally:
            owner.disconnect()

    def test_switch_pool_changes_namespace(self, latzero_server, unique_pool_name):
        from latzero import LatZero

        other_pool = unique_pool_name + "_two"
        client = LatZero(
            "latzero://switcher",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            client.set("value", 10)
            client.switch_pool(other_pool)
            assert client.get("value") is None
            client.set("value", 20)
            assert client.get("value") == 20
            client.switch_pool(unique_pool_name)
            assert client.get("value") == 10
        finally:
            client.disconnect()

    def test_buffer_subscriptions_receive_updates(self, latzero_server, unique_pool_name):
        from latzero import LatZero

        received = []
        subscriber = LatZero(
            "latzero://subscriber",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        writer = LatZero(
            "latzero://writer",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            subscriber.on("on_buffer_update", lambda payload: received.append(payload))
            subscriber.subscribe_buffer("shared")
            writer.set("shared", {"hello": "world"})
            deadline = time.time() + 2
            while not received and time.time() < deadline:
                time.sleep(0.05)
            assert received
            assert received[0]["key"] == "shared"
        finally:
            writer.disconnect()
            subscriber.disconnect()

    def test_targeted_app_call(self, latzero_server, unique_pool_name):
        from latzero import LatZero

        callee = LatZero(
            "latzero://app-two",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        caller = LatZero(
            "latzero://app-one",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        try:
            @callee.on_event("math:add")
            def add(x: int, y: int):
                return x + y

            result = caller.call_app("app-two", "math:add", x=7, y=5)
            assert result == 12
        finally:
            caller.disconnect()
            callee.disconnect()

    def test_response_to_third_app(self, latzero_server, unique_pool_name):
        from latzero import LatZero

        app1 = LatZero(
            "latzero://app-one",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        app2 = LatZero(
            "latzero://app-two",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        app3 = LatZero(
            "latzero://app-three",
            pool=unique_pool_name,
            host=latzero_server["host"],
            port=latzero_server["port"],
        )
        received = []
        try:
            @app2.on_event("relay:data")
            def relay(value: int):
                return {"tripled": value * 3}

            app3.on("on_app_result", lambda payload: received.append(payload))
            request_id = app1.call_app("app-two", "relay:data", response_to="app-three", value=3)

            deadline = time.time() + 2
            while not received and time.time() < deadline:
                time.sleep(0.05)

            assert request_id
            assert received
            assert received[0]["value"] == {"tripled": 9}
            assert received[0]["response_to"] == "app-three"
        finally:
            app3.disconnect()
            app2.disconnect()
            app1.disconnect()
