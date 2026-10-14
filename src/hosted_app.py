"""Serve the video API and OAuth-protected MCP from one public origin."""

from contextlib import asynccontextmanager

from src.api import api, lifespan as api_lifespan
from src.remote_mcp import create_remote_mcp

remote_mcp = create_remote_mcp()
mcp_http = remote_mcp.http_app(path="/mcp")


@asynccontextmanager
async def hosted_lifespan(app):
    async with api_lifespan(app), mcp_http.router.lifespan_context(mcp_http):
        yield


api.router.lifespan_context = hosted_lifespan
api.mount("/", mcp_http)
app = api
