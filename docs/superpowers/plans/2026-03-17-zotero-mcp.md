# Zotero MCP Server Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read+write MCP server for Zotero using pyzotero and FastMCP, deployable via stdio for Claude Code.

**Architecture:** Stdio MCP server with two layers: `client.py` wraps pyzotero with a clean interface supporting local/web API modes; `server.py` exposes 17 tools via FastMCP decorators. Entry point via `python -m zotero_mcp`.

**Tech Stack:** Python 3.11+, fastmcp>=2.3.0, pyzotero>=1.5.0, pytest

**Spec:** `docs/superpowers/specs/2026-03-17-zotero-mcp-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package config, dependencies, entry point |
| `.gitignore` | Python/IDE ignores |
| `src/zotero_mcp/__init__.py` | Package marker, version |
| `src/zotero_mcp/__main__.py` | `python -m zotero_mcp` entry point |
| `src/zotero_mcp/client.py` | Pyzotero wrapper: connection, all Zotero operations |
| `src/zotero_mcp/server.py` | FastMCP server: tool definitions, JSON serialization |
| `tests/conftest.py` | Shared fixtures (mock client) |
| `tests/test_client.py` | Unit tests for client.py |
| `tests/test_server.py` | Integration tests for server tools |

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/zotero_mcp/__init__.py`
- Create: `src/zotero_mcp/__main__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "zotero-mcp-rw"
version = "0.1.0"
description = "Read+write MCP server for Zotero"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.3.0",
    "pyzotero>=1.5.0",
]

[project.scripts]
zotero-mcp = "zotero_mcp.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/zotero_mcp"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.env
```

- [ ] **Step 3: Create src/zotero_mcp/__init__.py**

```python
"""Zotero MCP Server — read+write access to Zotero via Model Context Protocol."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create placeholder __main__.py**

```python
"""Entry point for python -m zotero_mcp."""


def main():
    from zotero_mcp.server import mcp
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Install in dev mode and verify import**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && uv sync --dev`
Then: `uv run python -c "import zotero_mcp; print(zotero_mcp.__version__)"`
Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/ docs/
git commit -m "feat: scaffold project with pyproject.toml and entry point"
```

---

### Task 2: Zotero client — connection and read operations

**Files:**
- Create: `src/zotero_mcp/client.py`
- Create: `tests/conftest.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write tests for client initialization and connection**

```python
# tests/test_client.py
import pytest
from unittest.mock import patch, MagicMock
from zotero_mcp.client import ZoteroClient


def test_client_init_web_api():
    """Web API client initializes with key and user_id."""
    with patch("zotero_mcp.client.zotero.Zotero") as mock_zot:
        client = ZoteroClient(
            api_key="test-key",
            user_id="12345",
            local=False,
        )
        mock_zot.assert_called_once_with("12345", "user", "test-key")


def test_client_init_local():
    """Local client initializes without API key."""
    with patch("zotero_mcp.client.zotero.Zotero") as mock_zot:
        client = ZoteroClient(local=True)
        mock_zot.assert_called_once()


def test_search_items_basic():
    """search_items returns formatted results."""
    client = ZoteroClient.__new__(ZoteroClient)
    client.zot = MagicMock()
    client.zot.items.return_value = [
        {
            "key": "ABC123",
            "data": {
                "key": "ABC123",
                "itemType": "journalArticle",
                "title": "Test Paper",
                "creators": [{"firstName": "John", "lastName": "Doe", "creatorType": "author"}],
                "date": "2024",
                "collections": ["COL1"],
                "tags": [{"tag": "test"}],
            },
        }
    ]
    results = client.search_items("test")
    assert len(results) == 1
    assert results[0]["key"] == "ABC123"
    assert results[0]["title"] == "Test Paper"


def test_get_collections():
    """get_collections returns flat list with parent info."""
    client = ZoteroClient.__new__(ZoteroClient)
    client.zot = MagicMock()
    client.zot.collections.return_value = [
        {
            "key": "COL1",
            "data": {
                "key": "COL1",
                "name": "My Collection",
                "parentCollection": False,
            },
            "meta": {"numItems": 10},
        }
    ]
    results = client.get_collections()
    assert len(results) == 1
    assert results[0]["name"] == "My Collection"
    assert results[0]["num_items"] == 10


def test_get_item_json():
    """get_item returns full metadata."""
    client = ZoteroClient.__new__(ZoteroClient)
    client.zot = MagicMock()
    client.zot.item.return_value = {
        "key": "ABC123",
        "data": {
            "key": "ABC123",
            "itemType": "journalArticle",
            "title": "Test",
            "creators": [],
            "date": "2024",
            "DOI": "10.1234/test",
        },
    }
    result = client.get_item("ABC123")
    assert result["title"] == "Test"
    assert result["DOI"] == "10.1234/test"


def test_get_tags():
    """get_tags returns tag list with counts."""
    client = ZoteroClient.__new__(ZoteroClient)
    client.zot = MagicMock()
    client.zot.tags.return_value = [
        {"tag": "logic", "meta": {"numItems": 5}},
        {"tag": "narrative", "meta": {"numItems": 3}},
    ]
    results = client.get_tags()
    assert len(results) == 2
    assert results[0]["tag"] == "logic"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && uv run pytest tests/test_client.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement client.py — connection + read operations**

```python
# src/zotero_mcp/client.py
"""Pyzotero wrapper for Zotero MCP server."""

import logging
import re
import sys
from collections import defaultdict

from pyzotero import zotero

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Thin wrapper around pyzotero with clean interface for MCP tools."""

    def __init__(
        self,
        api_key: str = "",
        user_id: str = "",
        local: bool = True,
        library_type: str = "user",
    ):
        if local:
            # Local API: no key needed, library_id can be anything
            self.zot = zotero.Zotero(user_id or "0", library_type)
            self.zot.endpoint = "http://localhost:23119/api"
            logger.info("Connected to local Zotero desktop API")
        else:
            if not api_key or not user_id:
                raise ValueError("api_key and user_id required for Web API mode")
            self.zot = zotero.Zotero(user_id, library_type, api_key)
            logger.info("Connected to Zotero Web API")

    # -- Read operations --

    def search_items(
        self,
        query: str,
        collection_key: str = "",
        item_type: str = "",
        tag: str = "",
        limit: int = 25,
    ) -> list[dict]:
        """Full-text search with optional filters."""
        kwargs = {"q": query, "limit": limit, "itemType": "-attachment || note"}
        if item_type:
            kwargs["itemType"] = item_type
        if tag:
            kwargs["tag"] = tag

        if collection_key:
            items = self.zot.collection_items(collection_key, **kwargs)
        else:
            items = self.zot.items(**kwargs)

        return [self._format_item_summary(item) for item in items]

    def get_item(self, item_key: str, fmt: str = "json") -> dict | str:
        """Get full metadata for a single item."""
        if fmt == "bibtex":
            return self.zot.item(item_key, format="bibtex")
        item = self.zot.item(item_key)
        return item.get("data", item)

    def get_collections(self) -> list[dict]:
        """List all collections with parent info and item counts."""
        collections = self.zot.collections()
        return [
            {
                "key": c["data"]["key"],
                "name": c["data"]["name"],
                "parent_key": c["data"].get("parentCollection") or "",
                "num_items": c.get("meta", {}).get("numItems", 0),
            }
            for c in collections
        ]

    def get_collection_items(self, collection_key: str, limit: int = 100) -> list[dict]:
        """Get items in a specific collection."""
        items = self.zot.collection_items(
            collection_key, limit=limit, itemType="-attachment || note"
        )
        return [self._format_item_summary(item) for item in items]

    def get_tags(self, query: str = "", limit: int = 100) -> list[dict]:
        """List tags, optionally filtered by query."""
        if query:
            tags = self.zot.tags(q=query, limit=limit)
        else:
            tags = self.zot.tags(limit=limit)
        return [
            {
                "tag": t.get("tag", t) if isinstance(t, dict) else str(t),
                "num_items": t.get("meta", {}).get("numItems", 0) if isinstance(t, dict) else 0,
            }
            for t in tags
        ]

    def find_duplicates(
        self,
        title: str = "",
        doi: str = "",
        collection_key: str = "",
        scan_all: bool = False,
    ) -> list[list[dict]]:
        """Find duplicate items by title/DOI or scan entire library."""
        if scan_all:
            return self._scan_duplicates(collection_key)

        if not title and not doi:
            return []

        results = []
        if doi:
            items = self.zot.items(q=doi, limit=50)
            items = [i for i in items if i["data"].get("DOI", "").strip() == doi.strip()]
            if len(items) > 1:
                results.append([self._format_item_summary(i) for i in items])
        if title:
            items = self.zot.items(q=title, limit=50)
            norm = self._normalize_title(title)
            matches = [
                i for i in items
                if self._normalize_title(i["data"].get("title", "")) == norm
            ]
            if len(matches) > 1:
                group = [self._format_item_summary(i) for i in matches]
                # Avoid duplicating a group already found via DOI
                if not results or {i["key"] for i in group} != {i["key"] for i in results[0]}:
                    results.append(group)
        return results

    def _scan_duplicates(self, collection_key: str = "") -> list[list[dict]]:
        """Scan library or collection for all duplicate groups."""
        if collection_key:
            items = self.zot.everything(
                self.zot.collection_items(collection_key, itemType="-attachment || note")
            )
        else:
            items = self.zot.everything(
                self.zot.items(itemType="-attachment || note")
            )

        by_title: dict[str, list] = defaultdict(list)
        for item in items:
            title = item["data"].get("title", "")
            if title:
                norm = self._normalize_title(title)
                by_title[norm].append(item)

        return [
            [self._format_item_summary(i) for i in group]
            for group in by_title.values()
            if len(group) > 1
        ]

    # -- Write operations --

    def create_item(
        self,
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
        """Create a new Zotero item. Returns the item key."""
        template = self.zot.item_template(item_type)
        template["title"] = title
        template["creators"] = creators
        if date:
            template["date"] = date
        if doi:
            template["DOI"] = doi
        if url:
            template["url"] = url
        if abstract:
            template["abstractNote"] = abstract
        if publication:
            # Map to correct field based on item type
            pub_field = {
                "journalArticle": "publicationTitle",
                "conferencePaper": "conferenceName",
                "bookSection": "bookTitle",
            }.get(item_type, "publicationTitle")
            template[pub_field] = publication
        if collections:
            template["collections"] = collections
        if tags:
            template["tags"] = [{"tag": t} for t in tags]

        resp = self.zot.create_items([template])
        created = resp.get("successful", resp.get("success", {}))
        if created:
            key = list(created.values())[0] if isinstance(created, dict) else created[0]
            if isinstance(key, dict):
                return key.get("key", key.get("data", {}).get("key", ""))
            return str(key)
        raise RuntimeError(f"Failed to create item: {resp.get('failed', resp)}")

    def create_item_from_doi(
        self,
        doi: str,
        collections: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create item from DOI using Zotero translator. Returns {key, title}."""
        import json
        import urllib.request

        # Try Zotero translator first
        metadata = None
        try:
            req = urllib.request.Request(
                "https://translate.zotero.org/search",
                data=doi.encode(),
                headers={"Content-Type": "text/plain"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                items = json.loads(resp.read())
                if items:
                    metadata = items[0]
        except Exception as e:
            logger.warning(f"Zotero translator failed: {e}, trying CrossRef")

        # Fallback to CrossRef
        if not metadata:
            try:
                url = f"https://api.crossref.org/works/{doi}"
                req = urllib.request.Request(url, headers={"User-Agent": "ZoteroMCP/0.1"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())["message"]
                    metadata = self._crossref_to_zotero(data)
            except Exception as e:
                raise RuntimeError(f"Could not resolve DOI {doi}: {e}")

        if not metadata:
            raise RuntimeError(f"No metadata found for DOI {doi}")

        # Ensure correct item type
        item_type = metadata.get("itemType", "journalArticle")
        if collections:
            metadata["collections"] = collections
        if tags:
            metadata["tags"] = [{"tag": t} for t in tags]

        resp = self.zot.create_items([metadata])
        created = resp.get("successful", resp.get("success", {}))
        if created:
            val = list(created.values())[0] if isinstance(created, dict) else created[0]
            key = val.get("key", val.get("data", {}).get("key", "")) if isinstance(val, dict) else str(val)
            return {"key": key, "title": metadata.get("title", "")}
        raise RuntimeError(f"Failed to create item: {resp.get('failed', resp)}")

    def import_bibtex(self, bibtex: str, collection_key: str = "") -> list[str]:
        """Import BibTeX entries. Returns list of created item keys."""
        # pyzotero can't directly import bibtex, so we parse and create
        entries = self._parse_bibtex(bibtex)
        keys = []
        for entry in entries:
            if collection_key:
                entry["collections"] = [collection_key]
            resp = self.zot.create_items([entry])
            created = resp.get("successful", resp.get("success", {}))
            if created:
                val = list(created.values())[0] if isinstance(created, dict) else created[0]
                key = val.get("key", val.get("data", {}).get("key", "")) if isinstance(val, dict) else str(val)
                keys.append(key)
        return keys

    def update_item(self, item_key: str, fields: dict) -> dict:
        """Update item fields with version check. Returns {key, version}."""
        item = self.zot.item(item_key)
        for field, value in fields.items():
            item["data"][field] = value
        self.zot.update_item(item)
        return {"key": item_key, "version": item["data"].get("version", 0)}

    # -- Collection operations --

    def create_collection(self, name: str, parent_key: str = "") -> str:
        """Create a collection. Returns collection key."""
        payload = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key
        resp = self.zot.create_collections([payload])
        created = resp.get("successful", resp.get("success", {}))
        if created:
            val = list(created.values())[0] if isinstance(created, dict) else created[0]
            return val.get("key", val.get("data", {}).get("key", "")) if isinstance(val, dict) else str(val)
        raise RuntimeError(f"Failed to create collection: {resp.get('failed', resp)}")

    def add_to_collections(self, item_key: str, collection_keys: list[str]) -> list[str]:
        """Add item to one or more collections. Returns updated collection list."""
        item = self.zot.item(item_key)
        existing = set(item["data"].get("collections", []))
        existing.update(collection_keys)
        item["data"]["collections"] = list(existing)
        self.zot.update_item(item)
        return item["data"]["collections"]

    def remove_from_collection(self, item_key: str, collection_key: str) -> bool:
        """Remove item from a collection. Returns True on success."""
        item = self.zot.item(item_key)
        cols = item["data"].get("collections", [])
        if collection_key in cols:
            cols.remove(collection_key)
            item["data"]["collections"] = cols
            self.zot.update_item(item)
        return True

    # -- Management operations --

    def merge_duplicates(self, keep_key: str, remove_keys: list[str]) -> dict:
        """Merge duplicates into keeper: transfer fields, tags, collections, trash rest."""
        keeper = self.zot.item(keep_key)
        removed_titles = []

        for rk in remove_keys:
            dup = self.zot.item(rk)
            dup_data = dup["data"]
            removed_titles.append(dup_data.get("title", rk))

            # Fill empty fields from duplicate
            for field, value in dup_data.items():
                if field in ("key", "version", "dateAdded", "dateModified"):
                    continue
                keeper_val = keeper["data"].get(field)
                if not keeper_val and value:
                    keeper["data"][field] = value

            # Merge tags
            existing_tags = {t["tag"] for t in keeper["data"].get("tags", [])}
            for t in dup_data.get("tags", []):
                if t["tag"] not in existing_tags:
                    keeper["data"].setdefault("tags", []).append(t)
                    existing_tags.add(t["tag"])

            # Merge collections
            existing_cols = set(keeper["data"].get("collections", []))
            for col in dup_data.get("collections", []):
                if col not in existing_cols:
                    keeper["data"].setdefault("collections", []).append(col)
                    existing_cols.add(col)

            # Trash the duplicate
            self.zot.trash_items([dup])

        self.zot.update_item(keeper)
        return {
            "kept": keep_key,
            "removed": remove_keys,
            "removed_titles": removed_titles,
            "keeper_title": keeper["data"].get("title", ""),
        }

    def delete_item(self, item_key: str, permanent: bool = False) -> dict:
        """Move item to trash or permanently delete."""
        item = self.zot.item(item_key)
        title = item["data"].get("title", item_key)
        if permanent:
            self.zot.delete_item(item)
        else:
            self.zot.trash_items([item])
        return {"key": item_key, "title": title, "permanent": permanent}

    # -- Helpers --

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for duplicate comparison."""
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title

    @staticmethod
    def _format_item_summary(item: dict) -> dict:
        """Extract key fields from a Zotero item for display."""
        data = item.get("data", item)
        creators = data.get("creators", [])
        author_str = "; ".join(
            f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
            for c in creators[:3]
        )
        if len(creators) > 3:
            author_str += " et al."
        return {
            "key": data.get("key", ""),
            "title": data.get("title", ""),
            "creators": author_str,
            "date": data.get("date", ""),
            "item_type": data.get("itemType", ""),
            "collections": data.get("collections", []),
            "tags": [t["tag"] for t in data.get("tags", [])],
        }

    @staticmethod
    def _crossref_to_zotero(cr: dict) -> dict:
        """Convert CrossRef metadata to Zotero item format."""
        creators = []
        for a in cr.get("author", []):
            creators.append({
                "creatorType": "author",
                "firstName": a.get("given", ""),
                "lastName": a.get("family", ""),
            })
        item_type = "journalArticle"
        if cr.get("type") == "proceedings-article":
            item_type = "conferencePaper"
        elif cr.get("type") == "book":
            item_type = "book"

        date_parts = cr.get("published", {}).get("date-parts", [[]])
        date = "-".join(str(p) for p in date_parts[0]) if date_parts[0] else ""

        return {
            "itemType": item_type,
            "title": cr.get("title", [""])[0] if isinstance(cr.get("title"), list) else cr.get("title", ""),
            "creators": creators,
            "date": date,
            "DOI": cr.get("DOI", ""),
            "url": cr.get("URL", ""),
            "abstractNote": cr.get("abstract", ""),
            "publicationTitle": cr.get("container-title", [""])[0] if isinstance(cr.get("container-title"), list) else cr.get("container-title", ""),
        }

    @staticmethod
    def _parse_bibtex(bibtex: str) -> list[dict]:
        """Parse BibTeX string into Zotero item dicts."""
        entries = []
        # Simple regex-based parser for common BibTeX entries
        pattern = r"@(\w+)\{([^,]*),(.*?)\n\}"
        for match in re.finditer(pattern, bibtex, re.DOTALL):
            bib_type = match.group(1).lower()
            body = match.group(3)

            # Map BibTeX types to Zotero types
            type_map = {
                "article": "journalArticle",
                "inproceedings": "conferencePaper",
                "conference": "conferencePaper",
                "book": "book",
                "incollection": "bookSection",
                "phdthesis": "thesis",
                "mastersthesis": "thesis",
                "misc": "document",
                "techreport": "report",
            }
            item_type = type_map.get(bib_type, "document")

            # Parse fields
            fields = {}
            for fmatch in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}", body, re.DOTALL):
                fields[fmatch.group(1).lower()] = fmatch.group(2).strip()

            # Build creators
            creators = []
            if "author" in fields:
                for author in re.split(r"\s+and\s+", fields["author"]):
                    parts = [p.strip() for p in author.split(",", 1)]
                    if len(parts) == 2:
                        creators.append({
                            "creatorType": "author",
                            "firstName": parts[1],
                            "lastName": parts[0],
                        })
                    else:
                        name_parts = parts[0].rsplit(" ", 1)
                        creators.append({
                            "creatorType": "author",
                            "firstName": name_parts[0] if len(name_parts) > 1 else "",
                            "lastName": name_parts[-1],
                        })

            item = {
                "itemType": item_type,
                "title": fields.get("title", ""),
                "creators": creators,
                "date": fields.get("year", ""),
                "DOI": fields.get("doi", ""),
                "url": fields.get("url", ""),
                "abstractNote": fields.get("abstract", ""),
            }

            # Publication field depends on type
            if item_type == "journalArticle":
                item["publicationTitle"] = fields.get("journal", "")
                item["volume"] = fields.get("volume", "")
                item["pages"] = fields.get("pages", "")
            elif item_type == "conferencePaper":
                item["conferenceName"] = fields.get("booktitle", "")
            elif item_type == "bookSection":
                item["bookTitle"] = fields.get("booktitle", "")
            elif item_type == "book":
                item["publisher"] = fields.get("publisher", "")

            entries.append(item)

        return entries
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && uv run pytest tests/test_client.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/zotero_mcp/client.py tests/
git commit -m "feat: add ZoteroClient with read+write operations"
```

---

### Task 3: MCP server — tool definitions

**Files:**
- Create: `src/zotero_mcp/server.py`
- Modify: `src/zotero_mcp/__main__.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write tests for server tool wiring**

```python
# tests/test_server.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_client():
    """Mock ZoteroClient for server tests."""
    with patch("zotero_mcp.server._get_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


def test_server_has_all_tools():
    """Server exposes all 17 tools."""
    from zotero_mcp.server import mcp
    tools = mcp._tool_manager._tools
    expected = {
        "search_items", "get_item", "get_collections", "get_collection_items",
        "find_duplicates", "get_tags",
        "create_item", "create_item_from_doi", "import_bibtex", "update_item",
        "create_collection", "add_to_collections", "remove_from_collection",
        "merge_duplicates", "delete_item",
    }
    actual = set(tools.keys())
    missing = expected - actual
    assert not missing, f"Missing tools: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && uv run pytest tests/test_server.py -v`
Expected: FAIL (server module not found or tools not registered)

- [ ] **Step 3: Implement server.py**

```python
# src/zotero_mcp/server.py
"""MCP server exposing Zotero tools via FastMCP."""

import json
import logging
import os
import sys

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
```

- [ ] **Step 4: Update __main__.py**

```python
"""Entry point for python -m zotero_mcp."""

import logging
import os
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
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/zotero_mcp/server.py src/zotero_mcp/__main__.py tests/test_server.py
git commit -m "feat: add MCP server with 15 read+write tools"
```

---

### Task 4: Integration test with live Zotero

**Files:**
- None (manual verification)

- [ ] **Step 1: Verify Zotero desktop is running**

Run: `curl -s http://localhost:23119/api/users/0/items/top?limit=1 | head -c 200`
Expected: JSON response with items (confirms local API works)

- [ ] **Step 2: Test server starts and lists tools**

Run: `cd /Users/nvashko/Projects/1-projects/zotero-mcp && echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | uv run python -m zotero_mcp 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"result\"][\"tools\"])} tools'); [print(f'  - {t[\"name\"]}') for t in d['result']['tools']]"`
Expected: 15 tools listed

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "docs: add design spec and implementation plan"
```

---

### Task 5: Register MCP server with Claude Code

**Files:**
- Modify: `~/.claude/settings.local.json` (or via `claude mcp add`)

- [ ] **Step 1: Add MCP server to Claude Code**

Run: `claude mcp add zotero -- uv run --directory /Users/nvashko/Projects/1-projects/zotero-mcp python -m zotero_mcp`

Or manually add to settings with env vars:
```json
{
  "mcpServers": {
    "zotero": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/nvashko/Projects/1-projects/zotero-mcp", "python", "-m", "zotero_mcp"],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

- [ ] **Step 2: Verify in new Claude Code session**

Start new session and confirm Zotero tools appear in tool list.
Test: `search_items("narrative")` should return results.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: ready for Claude Code integration"
```
