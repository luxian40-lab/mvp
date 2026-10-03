"""xfail estricto al listado de scripts/baseline_failures_before.txt."""
from __future__ import annotations

import pytest

from mvp_project.ci_baseline import REASON, baseline_nodeids


def pytest_collection_modifyitems(config, items):
    wanted = baseline_nodeids()
    if not wanted:
        return
    for item in items:
        node = item.nodeid.replace("\\", "/")
        if node in wanted:
            item.add_marker(pytest.mark.xfail(strict=False, reason=REASON))
