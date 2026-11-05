"""Explicit live invocation requires the complete isolated-board configuration."""

import pytest

from kaiten_mcp.checks.live import LiveConfig, run_live

pytestmark = pytest.mark.live


async def test_live_all_tools():
    result = await run_live(LiveConfig.from_env())
    assert result["status"] == "passed", result
    assert result["cleanup"]["status"] == "passed", result
    assert all(row["status"] == "passed" for row in result["tools"]), result
