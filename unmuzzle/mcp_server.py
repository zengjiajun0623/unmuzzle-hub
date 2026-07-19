"""MCP server: expose unmuzzle to any MCP-capable agent.

Install:  pip install 'unmuzzle[mcp]'
Run:      unmuzzle-mcp            (stdio transport)

Claude Code:  claude mcp add unmuzzle -- unmuzzle-mcp
"""
from __future__ import annotations

import json
from typing import List, Optional

from . import api


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit("MCP support needs: pip install 'unmuzzle[mcp]'")

    mcp = FastMCP("unmuzzle")

    @mcp.tool()
    def list_models(tag: Optional[str] = None, index: Optional[str] = None) -> str:
        """List open-weight models in the unmuzzle index. Optionally filter by tag."""
        return json.dumps(api.list_models(tag=tag, index=index))

    @mcp.tool()
    def model_info(name: str, index: Optional[str] = None) -> str:
        """Show files, sizes, sha256, mirrors, and signature status for a model (org/name)."""
        return json.dumps(api.model_info(name, index=index))

    @mcp.tool()
    def get_model(
        name: str,
        dest: Optional[str] = None,
        method: str = "auto",
        require_signature: bool = True,
        index: Optional[str] = None,
    ) -> str:
        """Download a model, verify sha256 + signature, and install it into the
        Hugging Face cache (default) or a plain directory (dest). method is
        auto, http, or torrent."""
        return json.dumps(api.get(name, dest=dest, method=method,
                                  require_signature=require_signature, index=index))

    @mcp.tool()
    def publish_model(
        directory: str,
        name: str,
        http_bases: Optional[List[str]] = None,
        magnet: Optional[str] = None,
        torrent_url: Optional[str] = None,
        description: str = "",
        base_model: str = "",
        license: str = "",
        tags: Optional[List[str]] = None,
        sign_key: Optional[str] = None,
        index_dir: str = "index",
    ) -> str:
        """Hash a local model directory, sign the manifest, and add it to a
        local index. Upload the files to the mirror(s) yourself first or right
        after; the entry records where they live."""
        return json.dumps(api.publish(directory, name, http_bases=http_bases,
                                      magnet=magnet, torrent_url=torrent_url,
                                      description=description,
                                      base_model=base_model, license=license,
                                      tags=tags, sign_key=sign_key, index_dir=index_dir))

    @mcp.tool()
    def verify_model(name: str, index: Optional[str] = None) -> str:
        """Re-hash an installed model against the signed index manifest."""
        return json.dumps(api.verify(name, index=index))

    mcp.run()


if __name__ == "__main__":
    main()
