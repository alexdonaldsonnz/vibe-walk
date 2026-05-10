from collections.abc import AsyncIterator
from typing import Any

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_code_sdk._internal.message_parser import MessageParseError


def _summarize(name: str, inp: dict[str, Any]) -> str:
    match name:
        case "Bash":
            cmd = inp.get("command", "")
            return cmd.split("\n")[0][:120]
        case "Read":
            return inp.get("file_path", "")
        case "Write":
            return inp.get("file_path", "")
        case "Edit" | "MultiEdit":
            return inp.get("file_path", "")
        case "Glob":
            pat = inp.get("pattern", "")
            path = inp.get("path", "")
            return f"{pat}  {path}".strip() if path else pat
        case "Grep":
            pat = inp.get("pattern", "")
            path = inp.get("path", "")
            return f"{pat}  {path}".strip() if path else pat
        case "WebFetch":
            return inp.get("url", "")[:80]
        case "WebSearch":
            return inp.get("query", "")[:80]
        case "Agent":
            return inp.get("description", inp.get("prompt", ""))[:80]
        case _:
            return ""


class ClaudeSession:
    def __init__(self, cwd: str, permission_mode: str = "bypassPermissions"):
        self._cwd = cwd
        self._permission_mode = permission_mode
        self._client: ClaudeSDKClient | None = None

    async def start(self) -> None:
        options = ClaudeCodeOptions(
            permission_mode=self._permission_mode,  # type: ignore[arg-type]
            cwd=self._cwd,
            include_partial_messages=True,
        )
        self._client = ClaudeSDKClient(options)
        await self._client.connect()

    async def send_prompt(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        if not self._client:
            raise RuntimeError("Session not started")
        await self._client.query(prompt)
        seen_by_block: dict[int, int] = {}
        # pending: tool_id -> (name, input) — waiting for non-empty input before emitting
        pending_tools: dict[str, tuple[str, dict[str, Any]]] = {}
        emitted_tools: set[str] = set()
        try:
            async for msg in self._client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for i, block in enumerate(msg.content):
                        if isinstance(block, ToolUseBlock):
                            if block.id not in emitted_tools:
                                pending_tools[block.id] = (block.name, block.input)
                                if block.input:
                                    emitted_tools.add(block.id)
                                    del pending_tools[block.id]
                                    yield {
                                        "kind": "step",
                                        "tool": block.name,
                                        "summary": _summarize(block.name, block.input),
                                    }
                        elif isinstance(block, TextBlock) and block.text:
                            # Flush any pending tools before the first text
                            for tid, (tname, tinput) in list(pending_tools.items()):
                                emitted_tools.add(tid)
                                del pending_tools[tid]
                                yield {
                                    "kind": "step",
                                    "tool": tname,
                                    "summary": _summarize(tname, tinput),
                                }
                            prev = seen_by_block.get(i, 0)
                            delta = block.text[prev:]
                            if delta:
                                yield {"kind": "text", "text": delta}
                                seen_by_block[i] = len(block.text)
        except MessageParseError as e:
            if "rate_limit_event" in str(e):
                raise RuntimeError("Claude is rate limited — please wait a moment and try again") from None
            raise
        # Flush any tools that never got non-empty input
        for tid, (tname, tinput) in pending_tools.items():
            yield {"kind": "step", "tool": tname, "summary": _summarize(tname, tinput)}

    async def stop(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
