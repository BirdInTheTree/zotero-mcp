"""Tests for MCP server tool registration."""

import asyncio


def test_server_has_all_tools():
    """Server exposes all 15 tools."""
    from zotero_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    expected = {
        "search_items", "get_item", "get_collections", "get_collection_items",
        "find_duplicates", "get_tags",
        "create_item", "create_item_from_doi", "import_bibtex", "update_item",
        "create_collection", "add_to_collections", "remove_from_collection",
        "merge_duplicates", "delete_item",
    }
    actual = {t.name for t in tools}
    missing = expected - actual
    assert not missing, f"Missing tools: {missing}"
    assert len(tools) == 15
