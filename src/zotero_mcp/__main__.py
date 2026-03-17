"""Entry point for python -m zotero_mcp."""

import logging
import sys

# MCP uses stdout for protocol, logs go to stderr
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stderr,
)


def main():
    from zotero_mcp.server import mcp
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
