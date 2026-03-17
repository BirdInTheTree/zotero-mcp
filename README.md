# zotero-mcp

Read+write MCP server for Zotero. The first MCP server with **full write support** for managing your Zotero library from AI assistants.

Existing Zotero MCP servers are read-only. This one lets you create items, manage collections, find and merge duplicates, and import BibTeX — all from within Claude Code, Claude Desktop, or any MCP-compatible client.

## Features

### Search & Read
| Tool | Description |
|------|-------------|
| `search_items` | Full-text search with collection, type, and tag filters |
| `get_item` | Detailed metadata or BibTeX export for a single item |
| `get_collections` | List all collections with hierarchy and item counts |
| `get_collection_items` | List items in a specific collection |
| `find_duplicates` | Find duplicates by title/DOI, or scan entire library |
| `get_tags` | List all tags with item counts |

### Write
| Tool | Description |
|------|-------------|
| `create_item` | Create item from field data |
| `create_item_from_doi` | Create item by DOI (auto-fills metadata via Zotero translator + CrossRef) |
| `import_bibtex` | Import BibTeX entries into a collection |
| `update_item` | Update item fields with version conflict protection |

### Collections
| Tool | Description |
|------|-------------|
| `create_collection` | Create a collection (with optional parent) |
| `add_to_collections` | Add an item to multiple collections at once |
| `remove_from_collection` | Remove item from collection (doesn't delete it) |

### Management
| Tool | Description |
|------|-------------|
| `merge_duplicates` | Merge duplicates: transfer metadata, tags, collections to keeper, trash rest |
| `delete_item` | Move to trash or permanently delete |

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repo
git clone https://github.com/BirdInTheTree/zotero-mcp.git
cd zotero-mcp
uv sync
```

## Usage

### Claude Code

```bash
claude mcp add zotero -- uv run --directory /path/to/zotero-mcp python -m zotero_mcp
```

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOTERO_LOCAL` | `true` | Use local Zotero desktop API (requires Zotero running) |
| `ZOTERO_API_KEY` | — | Zotero Web API key (required if not using local) |
| `ZOTERO_USER_ID` | — | Zotero user ID (required if not using local) |

### Local mode (default)

Connects to Zotero desktop app at `http://localhost:23119/api`. Faster, no rate limits. Requires Zotero to be running with the default local API enabled.

### Web API mode

Set `ZOTERO_LOCAL=false` and provide `ZOTERO_API_KEY` and `ZOTERO_USER_ID`. Works without the desktop app. Get your API key at https://www.zotero.org/settings/keys.

If local mode fails and Web API credentials are present, the server falls back to Web API automatically.

## Examples

Once connected, you can ask your AI assistant things like:

- "Search my Zotero for papers about narrative planning"
- "Create a new collection called 'Preprint References'"
- "Import this BibTeX into my collection"
- "Find duplicate items in my library and merge them"
- "Add this paper to both the Preprint and AwesomeList collections"
- "Look up DOI 10.1234/example and add it to my library"

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v
```

## License

MIT
