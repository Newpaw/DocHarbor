# DocHarbor

DocHarbor is a local-first single-user web application for finding, inspecting, ingesting, and exporting technical documentation into LLM-friendly Markdown packages.

## What the app actually does

DocHarbor is not a generic web scraper. Its workflow is:

1. You enter a software name, a direct docs URL, or both.
2. If you entered only a software name and configured Brave Search, the app looks for likely official documentation candidates.
3. You inspect the selected source and can override the detected type or strategy.
4. The app fetches the source, crawls within the allowed scope, extracts useful content, converts it to Markdown, and stores the result as a job.
5. You can reopen jobs later, filter them by tag, download artifacts again, or delete jobs you no longer need.

## What it supports

- software-name discovery through Brave Search when `BRAVE_SEARCH_API_KEY` is configured
- direct URL inspection and ingestion
- deterministic source-type detection for docs sites, single pages, PDFs, Markdown, and plain text
- breadth-first multi-page crawling with depth and page limits
- HTML extraction and Markdown conversion with per-page storage
- compiled Markdown export, manifest JSON, and optional ZIP packaging
- SQLite-backed job history, pages, and event logs
- job tags for organizing runs, filtering history, and revisiting related collections
- server-rendered FastAPI UI and JSON API

## Stack

- Python 3.12+
- `uv` for dependency management
- FastAPI
- Jinja2 templates
- SQLAlchemy + SQLite
- `httpx`, `BeautifulSoup`, `markdownify`, `pypdf`

## Configuration

Copy `.env.example` to `.env` and set any optional integrations you want:

```bash
cp .env.example .env
```

Key settings:

- `BRAVE_SEARCH_API_KEY`: enables search-based discovery
- `OPENAI_API_KEY`: enables optional ambiguous-source classification fallback
- `DATABASE_URL`: defaults to `sqlite:///data/app.db`
- `EXPORT_ROOT`: defaults to `data/jobs`
- `DEFAULT_MAX_DEPTH`, `DEFAULT_MAX_PAGES`: crawl defaults

If Brave or OpenAI keys are missing, the app still runs. Discovery falls back to direct URL only, and LLM assistance stays disabled.

## How Brave Search is used

`BRAVE_SEARCH_API_KEY` is used only for source discovery when you start from a software name such as `FastAPI`, `ElevenLabs`, or `OpenAI API`.

The app does not use Brave Search for:

- page crawling
- HTML fetching
- content extraction
- Markdown conversion
- export generation

To stay reasonable on the Brave free tier, discovery:

- uses a very small query budget
- prefers `official docs` style searches first
- requests a small result count
- caches repeated identical queries inside the running app
- degrades gracefully on rate limits

If Brave returns a rate limit response, the UI shows a clear message instead of a raw exception. If partial results were already found, the app keeps those results and shows them.

## How OpenAI is used

`OPENAI_API_KEY` is optional. The app currently uses it only as a fallback when deterministic inspection is uncertain.

OpenAI is not used for:

- normal crawling
- deterministic URL filtering
- downloading HTML or PDFs
- Markdown conversion
- manifest creation
- ZIP packaging

If the OpenAI client is unavailable or the key is missing, DocHarbor stays functional and continues with deterministic logic.

## Tags, filtering, and cleanup

Each job can be tagged with one or more comma-separated tags such as `voice`, `api`, `rag`, or `python`.

You can:

- assign tags when creating a job
- edit tags later on the job detail page
- filter the history page by a tag
- click a tag pill to see related jobs
- delete a job and its stored artifacts from the UI

## Local run

Install with `uv`:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

## Docker Compose

```bash
docker compose up --build
```

Persistent data is stored under [`data/`](/home/jnovopacky/project/scraper_v2/data).

## Tests

```bash
uv run pytest
```

## Project layout

- [`app/main.py`](/home/jnovopacky/project/scraper_v2/app/main.py): FastAPI entrypoint
- [`app/routes/ui.py`](/home/jnovopacky/project/scraper_v2/app/routes/ui.py): server-rendered UI flow
- [`app/routes/api.py`](/home/jnovopacky/project/scraper_v2/app/routes/api.py): JSON endpoints
- [`app/services/`](/home/jnovopacky/project/scraper_v2/app/services): discovery, inspection, crawl, extraction, export
- [`app/templates/`](/home/jnovopacky/project/scraper_v2/app/templates): browser UI
- [`tests/`](/home/jnovopacky/project/scraper_v2/tests): unit coverage for core heuristics and exports
