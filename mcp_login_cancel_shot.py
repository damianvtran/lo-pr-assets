"""Capture the /mcp login cancellation receipt over a populated transcript.

Run from the worktree root:

    env -u NO_COLOR TERM=xterm-256color .venv/bin/python \
        /tmp/mcp_login_cancel_shot.py OUT.svg [COLSxROWS]

The fake manager's grant ends the way a closed browser tab now ends it:
McpLoginCancelledError. The frame should show the "logging in…" line AND the
cancel receipt answering it. On main (before the fix) the grant instead hangs
forever, so the same script shows the receipt region empty — that pair is the
before/after evidence.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.cwd()))

from local_operator.mcp.config import MCPAuthConfig, MCPHttpServerConfig  # noqa: E402
from local_operator.tui.app import OperatorApp  # noqa: E402
from local_operator.tui.widgets.assistant import AssistantBlock  # noqa: E402
from local_operator.tui.widgets.editor import Editor  # noqa: E402
from local_operator.tui.widgets.transcript import UserBlock  # noqa: E402
from tests.unit.tui.test_app_pilot import (  # noqa: E402
    FakeMcpManager,
    McpSession,
    McpStartupOutcome,
    _factory,
)

MODE = sys.argv[2] if len(sys.argv) > 2 else "after"


class CancelGrantManager(FakeMcpManager):
    async def connect_configured_server(self, name: str, *, timeout_ms: Any = None) -> Any:
        if MODE == "before":
            # The pre-fix behavior for a closed tab: the grant parks on the
            # idle clock and the transcript's "logging in…" is never answered.
            await asyncio.Event().wait()
        else:
            from local_operator.mcp.auth import McpLoginCancelledError

            raise McpLoginCancelledError(
                "no redirect arrived within 10 minutes — the login was probably "
                "cancelled (browser tab closed, or the authorization left "
                "unfinished). Run /mcp login again to retry."
            )


async def main() -> None:
    out = sys.argv[1]
    configs = {
        "linear": MCPHttpServerConfig(
            url="https://mcp.linear.app/mcp", auth=MCPAuthConfig(type="oauth")
        )
    }
    manager = CancelGrantManager(["linear"], ["linear"])
    manager._configs = configs
    session = McpSession(manager=manager, startup=McpStartupOutcome())
    app = OperatorApp(lambda: _factory(session))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.query_one(Editor).cursor_blink = False
        for turn in range(1, 4):
            app._append_block(UserBlock(f"Turn {turn}: check the audit rows"))
            prose = AssistantBlock()
            prose.update_text(f"Answer {turn}: rows verified, nothing stale.")
            app._append_block(prose)
        await pilot.pause()

        from unittest.mock import patch

        with patch(
            "local_operator.mcp.config.load_all_mcp_configs",
            return_value=(configs, {}),
        ):
            app._cmd_mcp("login linear", lambda msg: app._system_notice(msg, "info"))
        for _ in range(12):
            await pilot.pause()
        app.save_screenshot(out)


asyncio.run(main())
