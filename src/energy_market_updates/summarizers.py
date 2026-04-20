from __future__ import annotations

import os
import re

from openai import AzureOpenAI, OpenAI

from energy_market_updates.models import DiscoveredDocument


class DocumentSummarizer:
    def __init__(self) -> None:
        self.mode = "local_preview"
        self.client = None
        self.model = None

        azure_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

        if all([azure_key, azure_endpoint, azure_api_version, azure_deployment]):
            self.client = AzureOpenAI(
                api_key=azure_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_api_version,
            )
            self.model = azure_deployment
            self.mode = "azure_openai"
            return

        openai_key = os.getenv("OPENAI_API_KEY")
        openai_model = os.getenv("OPENAI_MODEL")
        if openai_key and openai_model:
            self.client = OpenAI(api_key=openai_key)
            self.model = openai_model
            self.mode = "openai"

    def summarize(self, document: DiscoveredDocument, text: str) -> tuple[str, str]:
        if len(text.strip()) < 80:
            return (
                "Not enough extractable text was available to produce a meaningful summary.",
                "insufficient_text",
            )

        if self.client and self.model:
            try:
                summary = self._summarize_with_model(document, text)
                return summary, self.mode
            except Exception:
                pass

        return _local_preview_summary(text), "local_preview"

    def _summarize_with_model(self, document: DiscoveredDocument, text: str) -> str:
        excerpt = text[:20000]
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize PJM committee materials for an energy-market stakeholder. "
                        "Focus on market design changes, proposal differences, decisions, manual revisions, "
                        "deadlines, votes, and action items. If a file is mostly an agenda or logistics, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Source: {document.source_name}\n"
                        f"Meeting: {document.meeting_label}\n"
                        f"Document title: {document.title}\n"
                        f"Published on: {document.published_on or 'Unknown'}\n\n"
                        "Summarize this in 3 to 6 concise bullet points.\n\n"
                        f"{excerpt}"
                    ),
                },
            ],
        )
        return (response.choices[0].message.content or "").strip()


def _local_preview_summary(text: str) -> str:
    cleaned = re.sub(r"\r\n?", "\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    candidates = []
    for chunk in re.split(r"\n\n+|\n", cleaned):
        line = chunk.strip(" -\t")
        if len(line.split()) >= 7:
            candidates.append(line)
        if len(candidates) == 4:
            break

    if not candidates:
        snippet = cleaned.strip()
        if len(snippet) > 320:
            snippet = f"{snippet[:317]}..."
        return f"Local preview summary: {snippet}"

    bullets = "\n".join(f"- {line[:280]}" for line in candidates)
    return (
        "Local preview summary because no OpenAI or Azure OpenAI credentials were configured:\n"
        f"{bullets}"
    )
