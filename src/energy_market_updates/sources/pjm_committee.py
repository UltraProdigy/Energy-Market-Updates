from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from energy_market_updates.models import DiscoveredDocument, SourceConfig

MEETING_HEADING_RE = re.compile(r"(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\s*-\s*(?P<title>.+)")


class PjmCommitteeSource:
    def fetch_documents(self, source: SourceConfig, session: requests.Session) -> list[DiscoveredDocument]:
        response = session.get(
            source.page_url,
            timeout=30,
            headers={"User-Agent": "energy-market-updates/0.1"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        documents: list[DiscoveredDocument] = []
        seen_urls: set[str] = set()

        for row in soup.select("tr.meetingMaterial"):
            link_cell = row.find_all("td")
            if not link_cell:
                continue

            primary_link = link_cell[-1].find("a", href=True)
            if primary_link is None:
                continue

            href = primary_link.get("href", "").strip()
            if not href:
                continue

            url = urljoin(source.page_url, href)
            if url in seen_urls:
                continue

            extension = Path(unquote(urlparse(url).path)).suffix.lower().lstrip(".")
            if extension not in {"pdf", "doc", "docx", "xls", "xlsx", "txt", "csv"}:
                continue

            meeting_label, meeting_title, meeting_date = _find_meeting_context(row)
            published_on = _extract_published_on(row)
            title = _extract_link_text(primary_link)
            file_name = unquote(Path(urlparse(url).path).name)
            fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()

            documents.append(
                DiscoveredDocument(
                    source_id=source.id,
                    source_name=source.name,
                    meeting_label=meeting_label,
                    meeting_title=meeting_title,
                    meeting_date=meeting_date,
                    published_on=published_on,
                    title=title,
                    url=url,
                    file_name=file_name,
                    extension=extension,
                    fingerprint=fingerprint,
                )
            )
            seen_urls.add(url)

        return documents


def _find_meeting_context(row: Tag) -> tuple[str, str, str | None]:
    heading = row.find_previous(_is_meeting_heading)
    if heading is None:
        return "Unknown meeting", "Unknown meeting", None

    text = _normalize_whitespace(heading.get_text(" ", strip=True))
    match = MEETING_HEADING_RE.fullmatch(text)
    if not match:
        return text, text, None

    meeting_date = _to_iso_date(match.group("date"))
    meeting_title = match.group("title").strip()
    return text, meeting_title, meeting_date


def _is_meeting_heading(tag: Tag) -> bool:
    if tag.name not in {"div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "a"}:
        return False
    text = _normalize_whitespace(tag.get_text(" ", strip=True))
    return bool(MEETING_HEADING_RE.fullmatch(text))


def _extract_published_on(row: Tag) -> str | None:
    date_span = row.find("span", id=re.compile(r"_date$"))
    if date_span is None:
        return None
    return _to_iso_date(_normalize_whitespace(date_span.get_text(" ", strip=True)))


def _extract_link_text(anchor: Tag) -> str:
    direct_text = "".join(
        str(node)
        for node in anchor.contents
        if isinstance(node, NavigableString)
    )
    title = _normalize_whitespace(direct_text)
    if title:
        return title

    fallback = _normalize_whitespace(anchor.get_text(" ", strip=True))
    return re.sub(r"\s+(PDF|DOCX?|XLSX?|CSV|TXT)$", "", fallback, flags=re.IGNORECASE).strip()


def _normalize_whitespace(value: str) -> str:
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _to_iso_date(value: str) -> str | None:
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    if not match:
        return None
    month, day, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"
