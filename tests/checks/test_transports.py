"""Real process, HTTP and JSON-RPC framing checks against a local fake Kaiten."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from kaiten_mcp.checks.registry import CONTRACTS


@pytest.fixture
def fake_kaiten():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get("Authorization"))
            body = json.dumps([{"id": 1, "title": "Transport"}]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_stdio_process(fake_kaiten, mode):
    base, received = fake_kaiten
    env = {**os.environ, "KAITEN_BASE_URL": base, "KAITEN_API_TOKEN": "stdio-user"}
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "kaiten_mcp"], env=env)
    async with Client(parameters, mode=mode, read_timeout_seconds=10) as client:
        assert {t.name for t in (await client.list_tools()).tools} == set(CONTRACTS)
        result = await client.call_tool("list_spaces", {})
        assert not result.is_error
        assert result.structured_content["items"][0]["id"] == 1
        assert (await client.call_tool("create_task", {})).is_error
        if mode == "legacy":
            assert client.session.initialize_result is not None
            assert client.session.initialize_result.protocol_version == "2025-11-25"
    assert received == ["Bearer stdio-user"]


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_http_process_isolates_tokens(fake_kaiten, mode):
    base, received = fake_kaiten
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "KAITEN_BASE_URL": base, "KAITEN_API_TOKEN": "must-not-fallback"}
    process = subprocess.Popen(
        [sys.executable, "-m", "kaiten_mcp", "--transport", "streamable-http", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f"http://127.0.0.1:{port}"
    try:
        async with asyncio.timeout(15), httpx.AsyncClient() as http:
            while True:
                if process.poll() is not None:
                    raise AssertionError("HTTP server exited before becoming ready")
                try:
                    if (await http.get(origin + "/healthz")).status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.05)

        async def call(token):
            headers = {"Authorization": "Bearer " + token} if token else {}
            async with httpx2.AsyncClient(headers=headers) as http:
                transport = streamable_http_client(origin + "/mcp", http_client=http)
                async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                    assert {t.name for t in (await client.list_tools()).tools} == set(CONTRACTS)
                    return await client.call_tool("list_spaces", {})

        a, b = await asyncio.gather(call("user-a"), call("user-b"))
        assert not a.is_error and not b.is_error
        assert (await call(None)).is_error
        assert sorted(received) == ["Bearer user-a", "Bearer user-b"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
