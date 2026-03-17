"""MCP server exposing Zotero tools via FastMCP."""

import json
import logging
import os

from fastmcp import FastMCP

from zotero_mcp.client import ZoteroClient

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "zotero",
    instructions=(
        "Zotero MCP server with read+write access. "
        "Use these tools to search, create, update, and organize "
        "items and collections in a Zotero library."
    ),
)

_client: ZoteroClient | None = None


def _get_client() -> ZoteroClient:
    """Lazy-initialize the Zotero client."""
    global _client
    if _client is not None:
        return _client

    local = os.environ.get("ZOTERO_LOCAL", "true").lower() == "true"
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    user_id = os.environ.get("ZOTERO_USER_ID", "")

    if local:
        try:
            _client = ZoteroClient(local=True, user_id=user_id)
            return _client
        except Exception as e:
            if api_key and user_id:
                logger.warning(f"Local API failed ({e}), falling back to Web API")
            else:
                raise RuntimeError(
                    f"Local Zotero API unavailable ({e}) and no Web API credentials set. "
                    "Set ZOTERO_API_KEY and ZOTERO_USER_ID, or start Zotero desktop."
                ) from e

    _client = ZoteroClient(api_key=api_key, user_id=user_id, local=False)
    return _client


# -- Search & Read --


@mcp.tool(description="Search items in Zotero library with optional filters")
def search_items(
    query: str,
    collection_key: str = "",
    item_type: str = "",
    tag: str = "",
    limit: int = 25,
) -> str:
    """Search for items by keyword with optional collection, type, and tag filters."""
    results = _get_client().search_items(query, collection_key, item_type, tag, limit)
    return json.dumps(results, ensure_ascii=False)


@mcp.tool(description="Get detailed metadata for a single Zotero item")
def get_item(item_key: str, format: str = "json") -> str:
    """Get full metadata or BibTeX for one item by its key."""
    result = _get_client().get_item(item_key, fmt=format)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(description="List all collections in the Zotero library")
def get_collections() -> str:
    """Returns flat list of collections with key, name, parent, and item count."""
    results = _get_client().get_collections()
    return json.dumps(results, ensure_ascii=False)


@mcp.tool(description="List items in a specific Zotero collection")
def get_collection_items(collection_key: str, limit: int = 100) -> str:
    """Get items within a collection by its key."""
    results = _get_client().get_collection_items(collection_key, limit)
    return json.dumps(results, ensure_ascii=False)


@mcp.tool(description="Find duplicate items by title or DOI, or scan entire library")
def find_duplicates(
    title: str = "",
    doi: str = "",
    collection_key: str = "",
    scan_all: bool = False,
) -> str:
    """Find potential duplicates. Use scan_all=True to scan the whole library."""
    results = _get_client().find_duplicates(title, doi, collection_key, scan_all)
    return json.dumps(results, ensure_ascii=False)


@mcp.tool(description="List tags in the Zotero library")
def get_tags(query: str = "", limit: int = 100) -> str:
    """List all tags, optionally filtered by a search query."""
    results = _get_client().get_tags(query, limit)
    return json.dumps(results, ensure_ascii=False)


# -- Write --


@mcp.tool(description="Create a new item in Zotero")
def create_item(
    item_type: str,
    title: str,
    creators: list[dict],
    date: str = "",
    doi: str = "",
    url: str = "",
    abstract: str = "",
    publication: str = "",
    collections: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Create a Zotero item. creators format: [{"type":"author","firstName":"...","lastName":"..."}]"""
    key = _get_client().create_item(
        item_type, title, creators, date, doi, url, abstract, publication,
        collections, tags,
    )
    return json.dumps({"key": key}, ensure_ascii=False)


@mcp.tool(description="Create a Zotero item from a DOI (auto-fills metadata)")
def create_item_from_doi(
    doi: str,
    collections: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Look up DOI metadata and create item automatically."""
    result = _get_client().create_item_from_doi(doi, collections, tags)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(description="Import BibTeX entries into Zotero")
def import_bibtex(bibtex: str, collection_key: str = "") -> str:
    """Parse BibTeX string and create items in Zotero."""
    keys = _get_client().import_bibtex(bibtex, collection_key)
    return json.dumps({"created_keys": keys, "count": len(keys)}, ensure_ascii=False)


@mcp.tool(description="Update fields on an existing Zotero item")
def update_item(item_key: str, fields: dict) -> str:
    """Update item metadata. Uses read-modify-write with version check."""
    result = _get_client().update_item(item_key, fields)
    return json.dumps(result, ensure_ascii=False)


# -- Collections --


@mcp.tool(description="Create a new Zotero collection")
def create_collection(name: str, parent_key: str = "") -> str:
    """Create a collection, optionally under a parent collection."""
    key = _get_client().create_collection(name, parent_key)
    return json.dumps({"key": key}, ensure_ascii=False)


@mcp.tool(description="Add a Zotero item to one or more collections")
def add_to_collections(item_key: str, collection_keys: list[str]) -> str:
    """Add an item to multiple collections at once."""
    cols = _get_client().add_to_collections(item_key, collection_keys)
    return json.dumps({"item_key": item_key, "collections": cols}, ensure_ascii=False)


@mcp.tool(description="Remove a Zotero item from a collection (does not delete the item)")
def remove_from_collection(item_key: str, collection_key: str) -> str:
    """Remove item from a collection without deleting it."""
    _get_client().remove_from_collection(item_key, collection_key)
    return json.dumps({"item_key": item_key, "removed_from": collection_key}, ensure_ascii=False)


# -- Management --


@mcp.tool(description="Merge duplicate Zotero items: transfer metadata, tags, collections to keeper, trash rest")
def merge_duplicates(keep_key: str, remove_keys: list[str]) -> str:
    """Merge duplicates into one item. Fills empty fields from duplicates."""
    result = _get_client().merge_duplicates(keep_key, remove_keys)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(description="Delete a Zotero item (move to trash or permanently delete)")
def delete_item(item_key: str, permanent: bool = False) -> str:
    """Move item to trash. Set permanent=True for permanent deletion."""
    result = _get_client().delete_item(item_key, permanent)
    return json.dumps(result, ensure_ascii=False)
