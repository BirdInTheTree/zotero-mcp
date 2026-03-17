"""Tests for ZoteroClient."""

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


def test_normalize_title():
    """Title normalization strips punctuation and lowercases."""
    assert ZoteroClient._normalize_title("Hello, World!") == "hello world"
    assert ZoteroClient._normalize_title("  Test  Paper  ") == "test paper"


def test_parse_bibtex():
    """BibTeX parser handles common entry types."""
    bib = """@article{test2024,
  author = {Doe, John and Smith, Jane},
  title = {Test Paper},
  journal = {Test Journal},
  year = {2024},
  volume = {1},
  pages = {1--10},
}
"""
    entries = ZoteroClient._parse_bibtex(bib)
    assert len(entries) == 1
    assert entries[0]["itemType"] == "journalArticle"
    assert entries[0]["title"] == "Test Paper"
    assert len(entries[0]["creators"]) == 2
    assert entries[0]["creators"][0]["lastName"] == "Doe"
    assert entries[0]["creators"][1]["lastName"] == "Smith"


def test_format_item_summary():
    """Item summary extracts key fields."""
    item = {
        "data": {
            "key": "XYZ",
            "title": "My Paper",
            "itemType": "journalArticle",
            "creators": [
                {"firstName": "Alice", "lastName": "Bob", "creatorType": "author"},
            ],
            "date": "2025",
            "collections": ["C1", "C2"],
            "tags": [{"tag": "ai"}, {"tag": "narrative"}],
        }
    }
    summary = ZoteroClient._format_item_summary(item)
    assert summary["key"] == "XYZ"
    assert summary["creators"] == "Alice Bob"
    assert summary["tags"] == ["ai", "narrative"]
