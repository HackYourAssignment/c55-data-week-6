# Week 6 Assignment: Deploy to Azure

Take the containerised pipeline from Week 5 and ship it to Azure. The pipeline
writes raw JSON to Azure Blob Storage and structured rows to Azure Database
for PostgreSQL, then runs on a schedule from an Azure Container App Job.

The full assignment chapter (with all task instructions) lives in your
HackYourFuture Notion curriculum under Week 6.

## Project structure

```text
data-assignment-week-6/
├── .github/workflows/
│   └── grade-assignment.yml    Triggers the auto-grader on every PR
├── .devcontainer/
│   └── devcontainer.json       Codespaces dev container (Python + Azure CLI)
├── .hyf/
│   ├── test.sh                 The auto-grader (run locally with `bash .hyf/test.sh`)
│   └── grader_lib.sh           Shared helpers used by test.sh
├── docs/
│   └── execution_history.png   Task 5: portal screenshot you upload (PNG)
├── src/
│   └── pipeline.py             Task 3: blob upload + Postgres upsert
├── Dockerfile                  Task 4: container image for the job
├── requirements.txt            Task 2: pinned Python deps
├── AI_ASSIST.md                Task 7: LLM prompt + your review
└── README.md                   This file
```

## Where to start

| Step | File | Task in the chapter |
|---|---|---|
| 1 | `requirements.txt` | Pin `azure-storage-blob` and `psycopg2-binary` |
| 2 | `src/pipeline.py` | Implement `get_config`, `upload_raw_to_blob`, `write_to_postgres` (Tasks 1-3) |
| 3 | `Dockerfile` | Finish the cache-friendly image (Task 4) |
| 4 | Azure CLI | Deploy as a Container App Job (Task 4-5) |
| 5 | `docs/execution_history.png` | Add the Execution-history portal screenshot (Task 5) |
| 6 | `AI_ASSIST.md` | Fill in your AI prompt + review (Task 7) |

## Open in Codespaces

> Codespaces ships Python 3.11 + the Azure CLI. Sign in with your HackYourFuture
> Azure account targeting the HYF tenant:

```bash
az login --use-device-code --tenant 07a14c4e-d88c-42f7-83b3-13af7e57ff3d
```

## Run the pipeline locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in real connection strings, never commit them
set -a && source .env && set +a
python -m src.pipeline
```

## Verifying your deployment (Task 5)

After deploying the Container App Job and triggering a run, capture proof:

1. Open the Azure portal, find your Container App Job, open the **Execution
   history** blade.
2. Screenshot the most recent successful run.
3. Save the screenshot to `docs/`.
4. Replace this whole section with one called `## Verification` and embed
   your screenshot using a Markdown image link. The grader looks for the
   `## Verification` heading and a `![alt](docs/your-file.png)` reference
   pointing at the image you committed.

## Verification

 Job executed successfully in Azure Container Apps Jobs
 Blob created in Azure Storage container `raw/weather/2026-06-09.json`
 PostgreSQL table `weather_readings` contains expected rows
 Execution history saved in `docs/execution_history.txt`
 See docs/execution_history.png

## Check your score locally

```bash
bash .hyf/test.sh
cat .hyf/score.json
```

The grader reports a score out of 100. The passing threshold is 60.

## Scoring ladder

| Points | What the grader checks |
|---|---|
| 10 | Required files exist (Dockerfile, requirements.txt, src/pipeline.py, AI_ASSIST.md, docs/) |
| 10 | requirements.txt pins `azure-storage-blob` and `psycopg2-binary` |
| 10 | Dockerfile copies requirements before src (cache-friendly layer order) |
| 15 | Pipeline reads both env vars, wraps the Postgres connection so it is closed cleanly, and silences the Azure SDK logger |
| 15 | Pipeline uses an idempotent upsert (`ON CONFLICT ... DO UPDATE`) |
| 10 | Connection string uses the Azure-required SSL flag and the blob SDK client class |
| 10 | AI_ASSIST.md has all three sections and is filled in (>=1800 chars, no `TODO:`) |
| 10 | README has a `## Verification` heading and references an image in `docs/` |
| 10 | `docs/execution_history.png` exists and is non-trivial (real screenshot) |

## Submitting

1. Create a branch: `git switch -c week6/your-name`.
2. Commit your work.
3. Push and open a pull request against `main`.
4. Share the PR URL with your teacher.

## Instructor / maintainer notes

This repository is built from the canonical Week 6 chapter in the curriculum
repo (`Data Track/Week 6/week_6__8_assignment.md`). The auto-grader checks
code shape, not live Azure deployment, because the GitHub Actions runner has
no Azure credentials. To rebuild from a fresh scaffold, follow
`.agents/workflows/build_assignment_repo.md` in the curriculum repo.
