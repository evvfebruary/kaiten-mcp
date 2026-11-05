from copy import deepcopy

import pytest

from kaiten_mcp.checks.docs import ORIGIN, catalog, compare, normalize
from kaiten_mcp.checks.registry import CONTRACTS

HTML = """<nav>menu</nav><div class="native-scroll-container info">
<h2>List spaces GET</h2><p>https://example.kaiten.ru/api/latest/spaces</p>
<p>Query limit integer maximum 100 offset integer</p><p>Responses 200 Array of spaces</p>
<script>random-build</script></div>"""


def baseline():
    pages = {c.docs: normalize(HTML) for c in CONTRACTS.values()}
    return {"source": ORIGIN, "catalog": {p: "GET" for p in pages}, "pages": pages}


def test_normalize_ignores_navigation_and_build_noise():
    assert normalize(HTML) == normalize(
        HTML.replace("menu", "new menu").replace("random-build", "next-build")
    )


@pytest.mark.parametrize(
    "html",
    ["<html>maintenance</html>", '<div class="native-scroll-container info">incomplete</div>'],
)
def test_missing_content_is_not_success(html):
    with pytest.raises(ValueError):
        normalize(html)
    with pytest.raises(ValueError):
        catalog(html)


@pytest.mark.parametrize("change", ["parameter removed", "DEPRECATED", "maximum 50"])
def test_endpoint_change_is_reported(change):
    before = baseline()
    after = deepcopy(before)
    after["pages"][next(iter(after["pages"]))] += change
    result = compare(before, after)
    assert result["status"] == "docs_changed"
    assert change in str(result["changes"])


def test_new_unused_method_is_informational():
    before = baseline()
    after = deepcopy(before)
    after["catalog"]["/new/operation"] = "New GET"
    result = compare(before, after)
    assert result["status"] == "passed"
    assert result["new_methods"] == ["/new/operation"]


def test_incomplete_baseline_fails_closed():
    with pytest.raises(ValueError):
        compare({"pages": {}}, baseline())
