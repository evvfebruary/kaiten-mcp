"""Every registered tool must execute through the MCP client and match its contract."""

import json
from pathlib import Path

import jsonschema
import pytest
import respx
from mcp import Client

from kaiten_mcp.checks.registry import CONTRACTS, READ_TOOLS
from kaiten_mcp.server import create_server


async def test_catalog_snapshot():
    async with Client(create_server()) as client:
        tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == sorted(CONTRACTS)
    actual = [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]
    expected = json.loads(Path("tests/checks/tool_schemas.json").read_text())
    assert actual == expected
    for tool in tools:
        assert tool.output_schema
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint == (tool.name in READ_TOOLS)
        assert "ctx" not in tool.input_schema["properties"]


@pytest.mark.parametrize("name", sorted(CONTRACTS))
@respx.mock
async def test_tool_contract(name, api_token):
    contract = CONTRACTS[name]
    route = respx.request(
        contract.method, "https://test-tenant.kaiten.ru/api/v1" + contract.path
    ).respond(200, json=contract.response)
    async with Client(create_server()) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        result = await client.call_tool(name, contract.arguments)
    assert not result.is_error
    assert result.structured_content is not None
    jsonschema.validate(result.structured_content, tools[name].output_schema)
    assert result.content  # Text fallback remains available.
    assert route.call_count == 1
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer " + api_token
    assert request.url.params["broken_api"] == "false"
    for key, value in (contract.query or {}).items():
        assert request.url.params[key] == value
    if contract.body is not None:
        assert json.loads(request.content) == contract.body


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
@respx.mock
async def test_errors_are_tool_errors(status, api_token):
    from kaiten_mcp.config import get_settings

    get_settings().max_retries = 0
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").respond(status, json={"message": "no"})
    async with Client(create_server()) as client:
        result = await client.call_tool("list_spaces", {})
    assert result.is_error
    assert api_token not in str(result)


@respx.mock
async def test_invalid_arguments_do_not_call_kaiten(api_token):
    async with Client(create_server()) as client:
        result = await client.call_tool("create_task", {"board_id": "invalid"})
    assert result.is_error
    assert not respx.calls
