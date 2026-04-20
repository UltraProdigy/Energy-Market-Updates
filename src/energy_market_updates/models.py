from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SourceConfig:
    id: str
    type: str
    name: str
    page_url: str
    baseline_on_first_run: bool = True


@dataclass(slots=True)
class AppConfig:
    timezone: str
    download_directory: Path
    report_directory: Path
    state_directory: Path
    sources: list[SourceConfig]


@dataclass(slots=True)
class DiscoveredDocument:
    source_id: str
    source_name: str
    meeting_label: str
    meeting_title: str
    meeting_date: str | None
    published_on: str | None
    title: str
    url: str
    file_name: str
    extension: str
    fingerprint: str


@dataclass(slots=True)
class ProcessedDocument:
    document: DiscoveredDocument
    summary: str
    summary_mode: str
    download_path: Path | None
    content_sha256: str | None
    extracted_characters: int
    extraction_error: str | None = None
