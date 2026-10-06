# replace-for-ms-document-intelligence

Extract structured data from PDF documents **without a cloud OCR/form service** such as
Microsoft Azure Document Intelligence. Instead, the pipeline combines:

- **[Docling](https://github.com/docling-project/docling-serve)** (open source, runs locally in Docker) to turn the PDF into Markdown while keeping table structure, and
- **one LLM call** ([PydanticAI](https://ai.pydantic.dev/) with any OpenAI-compatible model) to fill a typed Pydantic schema,

followed by deterministic Python for business rules and CSV export.

The included example targets **reinsurance treaty balance statements** (statements of account
sent by brokers), but the design is generic: swap the schema, the prompts and the CSV mapping
to handle any other document type.

---

## How it works

```
 PDF ──► [1] Docling ──► Markdown ──► [2] LLM + schema ──► JSON ──► [3] transform ──► [4] CSV
        pdf_to_markdown.py           extract.py                     transform.py        to_csv.py
                                     brokers.py + prompts/
```

| Step | File | What it does | LLM? |
|------|------|--------------|------|
| 1 | `pdf_to_markdown.py` | Sends the PDF to the Docling server and returns Markdown. Table structure is preserved, which lets the LLM tell columns like *100% Amounts* and *Your Share* apart. OCR is off by default (text PDFs). | No |
| 2 | `extract.py` | Detects the broker, builds the system prompt, and makes **exactly one** PydanticAI call with the whole schema as `output_type`. PydanticAI validates the answer and retries on validation errors. | Yes |
| 3 | `transform.py` | Optional business rules: masking (`2.5%` → `x%`), main-class building, sign detection so rows add up to the section balance, special handling for outstanding-loss rows. | No |
| 4 | `to_csv.py` | Flattens the nested sections into one CSV row per statement row and writes a `;`-separated CSV (German number/date format by default). | No |

`main.py` runs all steps for every PDF and logs timing, token usage and estimated cost.

### Why one schema + one prompt per broker?

The **output is always the same**, so there is a single schema (`schema.AccountStatement`).
What differs between brokers is only the **layout**: where each field sits on the page.
That knowledge lives in a small text prompt per broker. Adding a broker therefore never
touches the schema or the CSV code.

Broker detection is **deterministic**: each broker declares signature strings (name,
email domain, a title only it uses) and the one with the most hits in the Markdown wins.

---

## Project structure

```
.
├── .devcontainer/
│   ├── devcontainer.json          # VS Code devcontainer (app + docling)
│   ├── docker-compose.yml         # app container + docling-serve sidecar
│   ├── Dockerfile                 # Python 3.12 dev image with a venv
│   ├── .devcontainer.env.example  # Docling settings  -> copy to .devcontainer.env
│   └── .devcontainer.env          # (git-ignored)
└── src/
    ├── main.py                    # run the whole pipeline
    ├── settings.py                # all configuration (pydantic-settings)
    ├── pdf_to_markdown.py         # step 1
    ├── extract.py                 # step 2
    ├── brokers.py                 # broker registry, detection, prompt loading
    ├── schema.py                  # the output schema
    ├── transform.py               # step 3 (your business rules)
    ├── to_csv.py                  # step 4
    ├── pricing.py                 # token prices -> cost estimate
    ├── prompts/
    │   ├── _base.txt              # rules shared by every broker
    │   └── broker1.txt            # example broker layout
    ├── credentials.env.example    # LLM settings -> copy to credentials.env
    ├── credentials.env            # (git-ignored)
    ├── requirements.txt
    └── data/                      # contents are git-ignored
        ├── input/pdf/             # put your PDFs here
        ├── output/_md/            # step 1 results
        ├── output/_json/          # step 2 results
        ├── output/_csv/           # step 4 results
        ├── logs/                  # metrics_log.csv
        └── cache/
```

---

## Getting started

### Requirements

- Docker Desktop (Compose 2.24+)
- VS Code with the *Dev Containers* extension
- An API key for an OpenAI-compatible LLM endpoint (OpenAI, Azure OpenAI, a LiteLLM proxy, Ollama, vLLM, ...)

### 1. Configure

```bash
cp .devcontainer/.devcontainer.env.example .devcontainer/.devcontainer.env
cp src/credentials.env.example src/credentials.env
```

`.devcontainer/.devcontainer.env` — Docling:

| Variable | Default | Notes |
|----------|---------|-------|
| `DOCLING_BASE_URL` | `http://docling:5001` | Service name inside the compose network |
| `DOCLING_API_KEY` | *(empty)* | Only if your Docling server requires a key |

`src/credentials.env` — LLM:

| Variable | Required | Notes |
|----------|----------|-------|
| `LLM_MODEL` | yes | Model / deployment name as your endpoint exposes it |
| `LLM_API_KEY` | yes | |
| `LLM_BASE_URL` | no | Leave empty for api.openai.com |

Real environment variables always override values from these files.

### 2. Open the devcontainer

Open the folder in VS Code → **Reopen in Container**. This starts:

- `app` — the Python dev container (dependencies from `src/requirements.txt`)
- `docling` — `quay.io/docling-project/docling-serve-cpu`, models pre-baked

The first build downloads the Docling image (a few GB). Docling is also reachable from your
machine at <http://localhost:5001/docs> (API) and <http://localhost:5001/ui> (web UI).

### 3. Run

```bash
cd src
python main.py                 # all PDFs in data/input/pdf
python main.py path/to/a.pdf   # one or more specific files
```

Example output:

```
statement_01.pdf: docling 14.2s | llm 9.8s | total 24.1s | tokens 5210 (cached 3840)+890=6100 | ~$0.0123
Done: 1 ok, 0 failed.
```

A failing PDF is reported and skipped; the exit code is `1` if any file failed.

---

## Outputs

For `data/input/pdf/<name>.pdf`:

| File | Content |
|------|---------|
| `data/output/_md/<name>.md` | Docling Markdown (useful to debug the prompt) |
| `data/output/_json/<name>.json` | Validated `AccountStatement` |
| `data/output/_csv/<name>.csv` | Final rows |
| `data/logs/metrics_log.csv` | One row per PDF: timings, tokens (incl. cached), cost, row count |

### CSV columns

`BROKER, CEDENT, TREATY, CONTRACT_REFERENCE, SHARE_PERCENT, ACCOUNTING_PERIOD_END,
ACCOUNTING_YEAR, UW_YEAR, OCC_YEAR, DOCUMENT_REFERENCE, MAIN_CLASS, ACCOUNT_CLASS,
CURRENCY, AMOUNT`

- Delimiter `;`, UTF-8 with BOM (opens correctly in Excel).
- Numbers use a decimal comma (`1234,50`), dates `DD.MM.YYYY` — change the defaults of
  `format_value()` in `to_csv.py` for another locale.
- Summary rows (*Due to you*, *Balance*) and zero amounts are not written.

To match your own target system, edit `COLUMNS` and the row dict in `statement_to_rows()`.

---

## The schema

`schema.py` mirrors the document: a statement has header fields plus **one or more sections**,
each with its own title, currency, rows and balance.

```
AccountStatement
├── broker_name, statement_date, treaty_name, line_of_business
├── contract_reference, document_reference, account_id, share_percent
├── cedent: Party (name, reference)
├── period: StatementPeriod (accounting_start/end, coverage_start/end)
└── sections: [StatementSection]
    ├── title, currency, balance
    └── rows: [StatementRow] (category, printed_label, amount_total, amount_share)
```

- Amounts are **signed** (`CR` → positive, `DR` → negative) and rounded to 2 decimals (`Money` type).
- Dates are ISO (`YYYY-MM-DD`) in the JSON; display formats are applied only in the CSV.
- Every row must have at least one amount, otherwise validation fails and the LLM retries.

---

## Customising

### Add a broker

1. Copy `src/prompts/broker1.txt` to `src/prompts/<broker>.txt` and describe where each
   field sits on that broker's layout.
2. Add an entry to `BROKERS` in `src/brokers.py`:

   ```python
   Broker(
       key="broker2",
       name="Broker 2",
       signatures=("broker2", "broker2.example.com"),
       prompt_file="broker2.txt",
   ),
   ```

No schema or CSV changes are needed.

### Add a business rule

Add a pure function to `transform.py` and call it from `statement_to_rows()` in `to_csv.py`.
Included examples:

| Function | Purpose |
|----------|---------|
| `mask_percent` | `'Brokerage at 2.5%'` → `'Brokerage at x%'` |
| `mask_year_in_ref` | Replace the 2-digit year in a reference with `__` |
| `main_class` | Line of business + section title |
| `is_summary_row` | Detect *Balance* / *Due to you* rows |
| `apply_outstanding_loss_logic` | Outstanding-loss rows are negative; add `stat` for prior-year periods |
| `detect_signs` | Pick the unique sign combination so rows sum to the section balance |

### Use another document type

Replace `schema.py`, the prompts and `to_csv.py`. Steps 1 and 2 (`pdf_to_markdown.py`,
`extract.py`) work unchanged with any schema.

---

## Cost and performance

- **Cost estimate:** fill in your model's prices (USD per 1M tokens) in `src/pricing.py`.
  Unknown models are counted as 0. If you use a proxy that tracks spend, treat its numbers
  as the source of truth.
- **Prompt caching:** one agent is built per broker and reused, and each request sends a
  per-broker `prompt_cache_key`. The shared system prompt is therefore served from the
  provider's cache on repeated runs — check `cached_tokens` in the metrics log.
- **Docling on CPU** is the slowest step for long PDFs. Limits (timeout 600 s, 200 pages,
  100 MB) are set in `.devcontainer/docker-compose.yml`; a memory cap of 6 GB protects the host.

---

## Docling options

`pdf_to_markdown()` uses: Markdown output, OCR **off**, table structure **on** in
`accurate` mode, images as placeholders. Override per call:

```python
pdf_to_markdown("scan.pdf", do_ocr="true")
```

The image is `quay.io/docling-project/docling-serve-cpu:latest`; pin a release tag in
`docker-compose.yml` for reproducible builds.
