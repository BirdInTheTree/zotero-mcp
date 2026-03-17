"""Pyzotero wrapper for Zotero MCP server."""

import logging
import re
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

        metadata = None
        # Try Zotero translator first
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
                cr_url = f"https://api.crossref.org/works/{doi}"
                req = urllib.request.Request(cr_url, headers={"User-Agent": "ZoteroMCP/0.1"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())["message"]
                    metadata = self._crossref_to_zotero(data)
            except Exception as e:
                raise RuntimeError(f"Could not resolve DOI {doi}: {e}")

        if not metadata:
            raise RuntimeError(f"No metadata found for DOI {doi}")

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
        pattern = r"@(\w+)\{([^,]*),(.*?)\n\}"
        for match in re.finditer(pattern, bibtex, re.DOTALL):
            bib_type = match.group(1).lower()
            body = match.group(3)

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

            fields = {}
            for fmatch in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}", body, re.DOTALL):
                fields[fmatch.group(1).lower()] = fmatch.group(2).strip()

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
