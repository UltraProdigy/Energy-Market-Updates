from __future__ import annotations

import json
from pathlib import Path

from energy_market_updates.models import AppConfig, SourceConfig


def load_config(path: Path, project_root: Path) -> AppConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    sources = [
        SourceConfig(
            id=item["id"],
            type=item["type"],
            name=item["name"],
            page_url=item["page_url"],
            baseline_on_first_run=item.get("baseline_on_first_run", True),
        )
        for item in raw["sources"]
    ]

    return AppConfig(
        timezone=raw.get("timezone", "America/New_York"),
        download_directory=(project_root / raw.get("download_directory", "var/downloads")).resolve(),
        report_directory=(project_root / raw.get("report_directory", "reports/daily")).resolve(),
        state_directory=(project_root / raw.get("state_directory", "data/state")).resolve(),
        sources=sources,
    )
