"""Lightweight, pure-HTTP/SSE Model Context Protocol (MCP) Client using official SDK.

Allows SpanInsight to connect to remote, online-hosted MCP servers (e.g. Google Slides,
Google Forms, Sheets) over standard HTTP and SSE protocols using standard JSON-RPC 2.0.

Does not require any heavy native subprocess libraries, making it fully portable and mobile-compatible.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for online MCP client errors."""

    pass


class OnlineMCPClient:
    """Pure-Python client for online-hosted MCP servers via SSE/HTTP transports using official SDK."""

    def __init__(
        self,
        server_name: str,
        sse_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        self.server_name = server_name
        self.sse_url = sse_url
        self.headers = headers or {}
        self.timeout = timeout
        self.session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()
        self._connected = False

    async def connect(self) -> bool:
        """Establish the Server-Sent Events stream and initialize ClientSession.

        Returns:
            bool: True if connection and session initialization succeeded, False otherwise.
        """
        if self._connected:
            return True

        logger.info(
            "Connecting to online MCP server '%s' via SSE URL: %s",
            self.server_name,
            self.sse_url,
        )
        try:
            # Enter the sse_client context to get streams
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(url=self.sse_url, headers=self.headers, timeout=self.timeout)
            )
            # Enter the ClientSession context
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            # Initialize the session
            await self.session.initialize()
            self._connected = True
            logger.info(
                "Successfully established official MCP session for '%s'",
                self.server_name,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to establish SSE connection to MCP server '%s': %s",
                self.server_name,
                e,
            )
            # Clean up the stack to avoid leaks on failure
            await self._exit_stack.aclose()
            self._exit_stack = AsyncExitStack()
            self._connected = False
            self.session = None
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        """Query the remote MCP server for the list of available tools.

        Returns:
            list[dict]: A list of tool definitions returned by the server.
        """
        if not self._connected and not await self.connect():
            raise MCPClientError("Cannot list tools: MCP server is not connected.")

        try:
            tools_result = await self.session.list_tools()
            # Convert official Tool objects to dict representation
            # and initialize "enabled": True for each tool
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "enabled": True,
                }
                for tool in tools_result.tools
            ]
        except Exception as e:
            logger.error("list_tools failed for server '%s': %s", self.server_name, e)
            raise MCPClientError(str(e))

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on the remote online MCP server.

        Args:
            tool_name: The name of the tool to execute.
            arguments: Dictionary of arguments to pass to the tool.

        Returns:
            dict: The result block containing content blocks.
        """
        if not self._connected and not await self.connect():
            raise MCPClientError("Cannot call tool: MCP server is not connected.")

        try:
            call_result = await self.session.call_tool(tool_name, arguments)
            # Serialize the result using model_dump
            return call_result.model_dump(by_alias=True, mode="json", exclude_none=True)
        except Exception as e:
            logger.error(
                "call_tool '%s' failed for server '%s': %s",
                tool_name,
                self.server_name,
                e,
            )
            raise MCPClientError(str(e))

    async def close(self) -> None:
        """Close the connection stack."""
        self._connected = False
        self.session = None
        await self._exit_stack.aclose()
        self._exit_stack = AsyncExitStack()
        logger.info("Online MCP client '%s' connection closed.", self.server_name)


class MCPConnectionManager:
    """Manages active online MCP client connections and execution."""

    def __init__(self):
        self.clients: dict[str, OnlineMCPClient] = {}

    async def get_client(
        self, name: str, url: str, headers: dict[str, str] | None = None
    ) -> OnlineMCPClient:
        """Get or create an OnlineMCPClient instance."""
        if name not in self.clients:
            self.clients[name] = OnlineMCPClient(name, url, headers=headers)
        elif self.clients[name].sse_url != url or self.clients[name].headers != headers:
            # SSE URL or headers changed, close and recreate
            await self.clients[name].close()
            self.clients[name] = OnlineMCPClient(name, url, headers=headers)
        return self.clients[name]

    async def connect_server(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Connect to a server and retrieve its list of tools.

        Returns:
            (success, tools_list)
        """
        try:
            client = await self.get_client(name, url, headers)
            connected = await client.connect()
            if not connected:
                return False, []

            tools = await client.list_tools()
            return True, tools
        except Exception as e:
            logger.error("connect_server failed for %s: %s", name, e)
            return False, []

    async def close_all(self):
        for client in list(self.clients.values()):
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()


mcp_manager = MCPConnectionManager()
