# Energy Market Updates

This repository is set up to watch committee and market websites for newly posted meeting materials, extract text from the new files, summarize them, and write dated markdown update reports.

The first source wired in is the PJM Market Implementation Committee page:

- [PJM MIC](https://www.pjm.com/committees-and-groups/committees/mic)

## Recommended Approach

For this project, Python plus GitHub Actions is a much better fit than Power Apps or Copilot Studio:

- The PJM MIC page is scrapeable with normal HTML parsing, so we do not need browser automation.
- GitHub Actions gives you a dependable daily schedule and a place to store lightweight state.
- API-based summarization is much easier to automate than a subscription-only chat product.

Recommended summarization path:

- Best enterprise option: Azure OpenAI, if your company already has access.
- Best straightforward option: OpenAI API.
- ChatGPT Plus / Pro / Enterprise chat access is not the same thing as API billing access.
- Claude could also work, but the repo currently ships with OpenAI/Azure OpenAI support first because it is the cleanest implementation path for unattended jobs.

## What This Repo Does Today

When the workflow runs, it will:

1. Scan the configured source pages.
2. Detect newly posted documents.
3. Download only the new files.
4. Extract text from supported formats.
5. Summarize the content with Azure OpenAI or OpenAI when credentials are configured.
6. Fall back to a local preview summary when no model credentials are present.
7. Write a dated markdown report to `reports/daily/`.
8. Persist lightweight seen-document state in `data/state/`.

On the very first run, the default behavior is to baseline the current PJM MIC document list without backfilling everything. That prevents the repo from treating years of existing materials as "new" on day one.

## Current File Support

- `pdf`
- `docx`
- `doc` via `antiword`
- `xlsx`
- `xls`

## Repo Layout

- `configs/sources.json`: source definitions and directories
- `src/energy_market_updates/`: application code
- `data/state/`: persisted seen-document state
- `reports/daily/`: generated dated markdown reports
- `.github/workflows/daily-update.yml`: scheduled GitHub Actions workflow

## Setup

### 1. Add GitHub Secrets

Add one of these sets:

OpenAI:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Azure OpenAI:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT`

### 2. Install Locally If You Want To Test By Hand

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install .
```

If you want legacy `.doc` extraction locally, install `antiword` and make sure it is on your `PATH`.

### 3. Run It

Normal run:

```powershell
python -m energy_market_updates.cli run --config configs/sources.json
```

Force the first run to process all currently listed docs instead of baselining them:

```powershell
python -m energy_market_updates.cli run --config configs/sources.json --backfill-initial
```

### 4. Trigger the GitHub Action

The workflow is configured to:

- run daily on a starter UTC schedule
- allow manual runs via `workflow_dispatch`
- optionally let you force initial backfill on a manual dispatch

## Next Good Additions

- Add email delivery through Microsoft Graph, Gmail, or SendGrid.
- Add more PJM committees by appending more source configs.
- Add non-PJM source adapters behind the same pipeline.
- Add issue tagging or topic extraction so summaries are easier to skim.
- Add tests around the scraper and state logic once a local Python environment is available.
