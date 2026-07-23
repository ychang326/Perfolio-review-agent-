"""Force-inject authenticated user_id into MCP tool calls."""
from typing import Callable, Awaitable
from langchain_mcp_adapters.interceptors import (
    ToolCallInterceptor,
    MCPToolCallRequest,
    MCPToolCallResult,
)


class UserIdInjector(ToolCallInterceptor):
    """Interceptor: force-inject user_id into MCP tool args before the call."""

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]],
    ) -> MCPToolCallResult:
        user_id = None
        if hasattr(request.runtime, "config"):
            config = request.runtime.config
            user_id = config.get("configurable", {}).get("user_id")

        if user_id:
            new_args = dict(request.args)
            new_args["user_id"] = user_id
            print(f"🔒 [Security] Injected user_id={user_id} into tool {request.name}")
            new_request = request.override(args=new_args)
            return await handler(new_request)

        return await handler(request)
