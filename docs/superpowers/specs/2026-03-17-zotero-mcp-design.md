# Zotero MCP Server — Design Spec

## Problem

Existing Zotero MCP servers (54yyyu/zotero-mcp, kujenga/zotero-mcp, gyger/mcp-pyzotero) are read-only.
Researchers and developers need write operations — creating items, managing collections,
deduplicating libraries — from within AI assistants.

## Solution

A Python MCP server wrapping `pyzotero` that provides full read+write access to Zotero
via the Model Context Protocol. Supports both local desktop API and Zotero Web API.

## Architecture

### Transport

Stdio. Claude Code spawns the process and communicates via stdin/stdout.
No HTTP server needed — simpler, no port management, works out of the box.

### Zotero Connection

Two modes, selected via environment variables:

- **Local** (default): connects to Zotero desktop app at `http://localhost:23119/api`.
  Faster, no rate limits, requires desktop app running.
- **Web API**: connects to `api.zotero.org` with API key.
  Works without desktop app, subject to rate limits.

Detection at startup: if `ZOTERO_LOCAL=true` (default), try connecting to local API.
If local connection fails and Web API credentials are present, fall back to Web API
with a warning logged to stderr. Mode is set once at startup — restart server to switch.

### Dependencies

- `fastmcp>=2.3.0` — MCP server framework
- `pyzotero>=1.5.0` — Zotero API client

### Project Structure

```
zotero-mcp/
├── pyproject.toml
├── .gitignore
├── LICENSE                  # MIT
├── README.md
├── src/zotero_mcp/
│   ├── __init__.py
│   ├── __main__.py          # entry point for python -m zotero_mcp
│   ├── server.py            # FastMCP tools (~350 lines)
│   └── client.py            # pyzotero wrapper (~150 lines)
└── tests/
    └── test_server.py
```

## Tools

### Search & Read (7 tools)

#### `search_items`
Full-text search across the library with optional filters.

- **Params:** `query: str`, `collection_key: str = ""`, `item_type: str = ""`,
  `tag: str = ""`, `limit: int = 25`
- **Returns:** list of items (key, title, creators, date, collections, tags)

#### `get_item`
Detailed metadata for a single item.

- **Params:** `item_key: str`, `format: str = "json"` (json | bibtex)
- **Returns:** full item metadata or BibTeX string

#### `get_collections`
List all collections as a flat list with parent info.

- **Params:** none
- **Returns:** list of collections (key, name, parent_key, num_items)

#### `get_collection_items`
Items within a specific collection.

- **Params:** `collection_key: str`, `limit: int = 100`
- **Returns:** list of items (key, title, creators, date)

#### `find_duplicates`
Search for potential duplicate items by title or DOI, or scan entire library.

- **Params:** `title: str = ""`, `doi: str = ""`, `collection_key: str = ""`,
  `scan_all: bool = False`
- **Returns:** groups of potential duplicates with keys and titles
- **Note:** when `scan_all=True`, scans the full library (or a collection if
  `collection_key` is set) and returns all duplicate groups. Uses title
  normalization (lowercase, strip punctuation) for matching.

#### `get_tags`
List all tags in the library, optionally filtered.

- **Params:** `query: str = ""`, `limit: int = 100`
- **Returns:** list of tags with item counts

### Write (4 tools)

#### `create_item`
Create a new Zotero item from field data.

- **Params:** `item_type: str` (journalArticle, book, conferencePaper, etc.),
  `title: str`, `creators: list[dict]`, `date: str = ""`, `doi: str = ""`,
  `url: str = ""`, `abstract: str = ""`, `publication: str = ""`,
  `collections: list[str] = []`, `tags: list[str] = []`
- **Returns:** created item key
- **Note:** `creators` format: `[{"type": "author", "firstName": "...", "lastName": "..."}]`

#### `create_item_from_doi`
Create item by looking up DOI metadata automatically.

- **Params:** `doi: str`, `collections: list[str] = []`, `tags: list[str] = []`
- **Returns:** created item key and resolved title
- **Mechanism:** POST DOI to `https://translate.zotero.org/search` to get
  structured metadata, then create item via pyzotero. Falls back to
  CrossRef API (`api.crossref.org/works/{doi}`) if translator is unavailable.

#### `import_bibtex`
Import one or more BibTeX entries into the library.

- **Params:** `bibtex: str`, `collection_key: str = ""`
- **Returns:** list of created item keys
- **Note:** parses BibTeX, maps fields to Zotero item types, creates items

#### `update_item`
Update fields on an existing item.

- **Params:** `item_key: str`, `fields: dict`
- **Returns:** updated item key and new version number
- **Note:** `fields` is a flat dict of Zotero field names and values.
  Implementation reads the item first (to get current `version`), applies
  changes, then writes with version check to prevent concurrent overwrites.

### Collections (3 tools)

#### `create_collection`
Create a new collection.

- **Params:** `name: str`, `parent_key: str = ""`
- **Returns:** created collection key

#### `add_to_collections`
Add an item to one or more collections.

- **Params:** `item_key: str`, `collection_keys: list[str]`
- **Returns:** success confirmation with list of collections

#### `remove_from_collection`
Remove an item from a collection (does not delete the item).

- **Params:** `item_key: str`, `collection_key: str`
- **Returns:** success confirmation

### Management (2 tools)

#### `merge_duplicates`
Merge duplicate items: transfer metadata, tags and collection memberships from
duplicates to the keeper, then trash the duplicates.

- **Params:** `keep_key: str`, `remove_keys: list[str]`
- **Returns:** summary of what was transferred and removed
- **Logic:**
  1. Read all items (keep + remove)
  2. For each empty field on keep, fill from first duplicate that has it
  3. Union all tags → apply to keep
  4. Union all collections → apply to keep
  5. Move remove items to trash

#### `delete_item`
Move an item to trash or permanently delete it.

- **Params:** `item_key: str`, `permanent: bool = False`
- **Returns:** confirmation with item title
- **Note:** `permanent=False` (default) moves to Zotero trash.
  `permanent=True` permanently deletes — use with caution.

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOTERO_LOCAL` | `true` | Use local Zotero desktop API |
| `ZOTERO_API_KEY` | — | Web API key (required if not local) |
| `ZOTERO_USER_ID` | — | Web API user ID (required if not local) |
| `ZOTERO_LIBRARY_TYPE` | `user` | `user` only in v1 (group support planned for v2) |

## Claude Code Integration

```bash
claude mcp add zotero -- \
  uv run --directory /Users/nvashko/Projects/1-projects/zotero-mcp \
  python -m zotero_mcp
```

Or in `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/zotero-mcp", "python", "-m", "zotero_mcp"],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

## Open Source Plan

- License: MIT
- Repo: `BirdInTheTree/zotero-mcp`
- Differentiator: first Zotero MCP server with full write support
- PyPI package: `zotero-mcp-rw` (to avoid collision with existing `zotero-mcp`)

## Out of Scope (v1)

- Semantic/vector search (54yyyu already does this well)
- PDF full-text extraction
- Batch operations beyond import_bibtex
- Group library support (user library only for now)
