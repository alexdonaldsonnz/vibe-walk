from collections.abc import AsyncIterator

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)


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

    async def send_prompt(self, prompt: str) -> AsyncIterator[str]:
        if not self._client:
            raise RuntimeError("Session not started")
        await self._client.query(prompt)
        seen_by_block: dict[int, int] = {}
        async for msg in self._client.receive_response():
            if isinstance(msg, AssistantMessage):
                for i, block in enumerate(msg.content):
                    if isinstance(block, TextBlock) and block.text:
                        prev = seen_by_block.get(i, 0)
                        delta = block.text[prev:]
                        if delta:
                            yield delta
                            seen_by_block[i] = len(block.text)

    async def stop(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
