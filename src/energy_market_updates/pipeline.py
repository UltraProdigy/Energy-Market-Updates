from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from energy_market_updates.extractors import ExtractionError, extract_text
from energy_market_updates.models import AppConfig, DiscoveredDocument, ProcessedDocument
from energy_market_updates.sources import SOURCE_REGISTRY
from energy_market_updates.summarizers import DocumentSummarizer


def run_pipeline(
    config: AppConfig,
    selected_sources: set[str] | None = None,
    backfill_initial: bool = False,
) -> dict[str, object]:
    config.download_directory.mkdir(parents=True, exist_ok=True)
    config.report_directory.mkdir(parents=True, exist_ok=True)
    config.state_directory.mkdir(parents=True, exist_ok=True)

    run_at = datetime.now(timezone.utc)
    session = requests.Session()
    summarizer = DocumentSummarizer()

    baseline_results: list[tuple[str, int]] = []
    processed_documents: list[ProcessedDocument] = []

    sources = [
        source for source in config.sources
        if not selected_sources or source.id in selected_sources
    ]

    for source in sources:
        state_path = config.state_directory / f"{source.id}.json"
        state = _load_state(state_path)
        existing_docs: dict[str, dict[str, object]] = state.get("documents", {})

        scraper_type = SOURCE_REGISTRY[source.type]
        scraper = scraper_type()
        discovered = scraper.fetch_documents(source, session)

        if not existing_docs and source.baseline_on_first_run and not backfill_initial:
            state["source"] = {"id": source.id, "name": source.name}
            state["baselined_at"] = run_at.isoformat()
            state["documents"] = {
                document.fingerprint: _state_document_record(document, content_sha256=None, summary_mode="baseline")
                for document in discovered
            }
            _save_state(state_path, state)
            baseline_results.append((source.id, len(discovered)))
            continue

        new_documents = [document for document in discovered if document.fingerprint not in existing_docs]
        for document in new_documents:
            processed = _process_document(
                session=session,
                summarizer=summarizer,
                download_root=config.download_directory,
                document=document,
            )
            processed_documents.append(processed)
            existing_docs[document.fingerprint] = _state_document_record(
                document=document,
                content_sha256=processed.content_sha256,
                summary_mode=processed.summary_mode,
            )

        if new_documents:
            state["source"] = {"id": source.id, "name": source.name}
            state["documents"] = existing_docs
            _save_state(state_path, state)

    report_path = None
    if processed_documents:
        report_path = _write_report(config, run_at, processed_documents)

    return {
        "baselines": baseline_results,
        "new_documents": processed_documents,
        "report_path": report_path,
    }


def _process_document(
    session: requests.Session,
    summarizer: DocumentSummarizer,
    download_root: Path,
    document: DiscoveredDocument,
) -> ProcessedDocument:
    download_path, content_sha256 = _download_document(session, download_root, document)

    try:
        text = extract_text(download_path)
        extraction_error = None
    except ExtractionError as exc:
        text = ""
        extraction_error = str(exc)

    if extraction_error:
        summary = f"Summary skipped because text extraction failed: {extraction_error}"
        summary_mode = "extraction_error"
        extracted_characters = 0
    else:
        summary, summary_mode = summarizer.summarize(document, text)
        extracted_characters = len(text)

    return ProcessedDocument(
        document=document,
        summary=summary,
        summary_mode=summary_mode,
        download_path=download_path,
        content_sha256=content_sha256,
        extracted_characters=extracted_characters,
        extraction_error=extraction_error,
    )


def _download_document(
    session: requests.Session,
    download_root: Path,
    document: DiscoveredDocument,
) -> tuple[Path, str]:
    source_dir = download_root / document.source_id
    source_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{document.fingerprint[:12]}-{document.file_name}"
    destination = source_dir / safe_name
    response = session.get(
        document.url,
        timeout=60,
        headers={"User-Agent": "energy-market-updates/0.1"},
    )
    response.raise_for_status()
    destination.write_bytes(response.content)
    content_sha256 = hashlib.sha256(response.content).hexdigest()
    return destination, content_sha256


def _write_report(
    config: AppConfig,
    run_at: datetime,
    processed_documents: list[ProcessedDocument],
) -> Path:
    zone = ZoneInfo(config.timezone)
    local_run_at = run_at.astimezone(zone)
    report_path = config.report_directory / f"{local_run_at.date().isoformat()}.md"

    lines = [
        f"# Energy Market Update - {local_run_at.date().isoformat()}",
        "",
        f"Generated: {local_run_at.isoformat()}",
        "",
        f"New documents found: {len(processed_documents)}",
        "",
    ]

    for item in processed_documents:
        document = item.document
        lines.extend(
            [
                f"## {document.source_name}",
                "",
                f"### {document.meeting_label}",
                "",
                f"#### {document.title}",
                "",
                f"- Published on: {document.published_on or 'Unknown'}",
                f"- File type: `{document.extension}`",
                f"- Source URL: {document.url}",
                f"- Summary mode: `{item.summary_mode}`",
                "",
                item.summary,
                "",
            ]
        )

    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return report_path


def _load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: dict[str, object]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _state_document_record(
    document: DiscoveredDocument,
    content_sha256: str | None,
    summary_mode: str,
) -> dict[str, object]:
    record = asdict(document)
    record["content_sha256"] = content_sha256
    record["summary_mode"] = summary_mode
    return record
