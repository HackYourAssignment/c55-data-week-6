#!/usr/bin/env bash
# Week 6 autograder: static analysis only. The pipeline targets Azure (Blob
# Storage, managed Postgres, Container App Jobs) which we cannot reach from a
# GitHub Actions runner without secrets. The grader therefore verifies code
# shape — env-var reads, the closing() pattern, the upsert SQL, Dockerfile
# layer order, the AI report, and a screenshot — instead of a live deployment.
#
# Total points: 100. Passing score: 60.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.hyf/grader_lib.sh
source "$SCRIPT_DIR/grader_lib.sh"

# Initialise score.json to 0/fail immediately so a mid-script crash leaves a
# meaningful artefact behind instead of a stale score.
cat > "$SCRIPT_DIR/score.json" <<'INIT'
{"score": 0, "pass": false, "passingScore": 60}
INIT

score=0
PASSING=60

# ── Level 1 (10 pts): required files exist ──────────────────────────────────
l1=0
required_files=(
  "Dockerfile"
  "requirements.txt"
  "src/pipeline.py"
  "AI_ASSIST.md"
  "README.md"
)
missing=0
for f in "${required_files[@]}"; do
  if [[ -f "$REPO_ROOT/$f" ]]; then
    pass "found $f"
  else
    fail "missing $f"
    ((missing += 1))
  fi
done
if [[ -d "$REPO_ROOT/docs" ]]; then
  pass "found docs/ directory"
else
  fail "missing docs/ directory (Task 5 screenshot lives here)"
  ((missing += 1))
fi
if [[ "$missing" -eq 0 ]]; then
  l1=10
fi
((score += l1))
pass "Level 1: required files ($l1/10 pts)"

# ── Level 2 (10 pts): pinned dependencies ───────────────────────────────────
l2=0
req="$REPO_ROOT/requirements.txt"
if [[ -f "$req" ]]; then
  # Pinned line for the blob SDK
  if grep -qE "^azure-storage-blob==" "$req"; then
    ((l2 += 5)); pass "requirements.txt pins azure-storage-blob"
  else
    fail "requirements.txt does not pin azure-storage-blob (expected line like 'azure-storage-blob==12.x.y')"
  fi
  # Pinned line for the Postgres driver. Require -binary explicitly: the
  # source psycopg2 needs libpq-dev + gcc, which python:3.11-slim does not
  # ship, so accepting bare psycopg2 here would give a student credit for
  # a requirements.txt that breaks `docker build`.
  if grep -qE "^psycopg2-binary==" "$req"; then
    ((l2 += 5)); pass "requirements.txt pins psycopg2-binary"
  else
    fail "requirements.txt does not pin psycopg2-binary (expected line like 'psycopg2-binary==2.x.y')"
  fi
fi
((score += l2))
pass "Level 2: pinned dependencies ($l2/10 pts)"

# ── Level 3 (10 pts): Dockerfile layer order ────────────────────────────────
l3=0
df="$REPO_ROOT/Dockerfile"
if [[ -f "$df" ]]; then
  if grep -qE "^FROM[[:space:]]+python:3\.11" "$df"; then
    ((l3 += 3)); pass "Dockerfile uses a python:3.11 base image"
  else
    fail "Dockerfile does not use a python:3.11 base image"
  fi
  req_line=$(grep -nE "^COPY[[:space:]].*requirements" "$df" | head -1 | cut -d: -f1 || echo 0)
  src_line=$(grep -nE "^COPY[[:space:]].*src" "$df" | head -1 | cut -d: -f1 || echo 9999)
  if [[ "$req_line" -gt 0 && "$src_line" -lt 9999 && "$req_line" -lt "$src_line" ]]; then
    ((l3 += 5)); pass "Dockerfile copies requirements before src/ (layer cache stays warm)"
  else
    fail "Dockerfile does not copy requirements.txt before src/ (cache-unfriendly)"
  fi
  if grep -qE "^CMD" "$df" && ! grep -qE 'CMD.*Task 4 still pending' "$df"; then
    ((l3 += 2)); pass "Dockerfile has a real CMD instruction"
  else
    fail "Dockerfile CMD is still the placeholder — replace it with the pipeline entry point"
  fi
fi
((score += l3))
pass "Level 3: Dockerfile ($l3/10 pts)"

# ── Level 4 (15 pts): pipeline shape (env vars, closing, Azure logger) ──────
l4=0
py="$REPO_ROOT/src/pipeline.py"
if [[ -f "$py" ]]; then
  # 4a: reads both env vars. Check each var name independently rather than
  # counting matching lines: a one-line tuple read or a dict comprehension
  # would otherwise false-fail a correct submission.
  if grep -qE "POSTGRES_URL" "$py" && grep -qE "AZURE_STORAGE_CONNECTION_STRING" "$py"; then
    ((l4 += 5)); pass "pipeline.py reads POSTGRES_URL and AZURE_STORAGE_CONNECTION_STRING from env"
  else
    fail "pipeline.py does not read both POSTGRES_URL and AZURE_STORAGE_CONNECTION_STRING from os.environ"
  fi
  # 4b: closing() pattern from contextlib (Chapter 4 deliverable)
  if grep -qE "from contextlib import closing" "$py" && grep -qE "with closing\(" "$py"; then
    ((l4 += 5)); pass "pipeline.py uses contextlib.closing() to wrap the Postgres connection"
  else
    fail "pipeline.py does not use 'from contextlib import closing' + 'with closing(...)' (Chapter 4 pattern)"
  fi
  # 4c: silences Azure SDK logger noise (Chapter 5 deliverable)
  if grep -qE 'logging\.getLogger\(.azure.\)\.setLevel' "$py"; then
    ((l4 += 5)); pass "pipeline.py silences the azure SDK logger"
  else
    fail "pipeline.py does not silence the azure SDK logger (logging.getLogger(\"azure\").setLevel(...))"
  fi
  # Final stub guard
  if grep -q "raise NotImplementedError" "$py"; then
    warn "pipeline.py still contains 'raise NotImplementedError' — finish the stubs before submitting"
  fi
fi
((score += l4))
pass "Level 4: pipeline shape ($l4/15 pts)"

# ── Level 5 (15 pts): idempotent upsert ─────────────────────────────────────
l5=0
if [[ -f "$py" ]]; then
  # Match the SQL keyword pair in one line (covers single-line or formatted SQL)
  # plus a fallback that allows them to be on separate lines.
  if grep -ciE "ON CONFLICT" "$py" >/dev/null && grep -ciE "DO UPDATE" "$py" >/dev/null; then
    ((l5 += 10)); pass "pipeline.py uses an upsert (ON CONFLICT ... DO UPDATE)"
  else
    fail "pipeline.py does not use ON CONFLICT ... DO UPDATE (idempotent upsert)"
  fi
  # Reward parameterised SQL with %s placeholders (Postgres) — never f-strings.
  # Use Python (not grep) because the placeholders typically live on a
  # different line from the execute( call inside multi-line SQL strings.
  if python3 - "$py" <<'PYCHECK' >/dev/null 2>&1
import re, sys
src = open(sys.argv[1]).read()
# Find every cur.execute(...) / cursor.execute(...) call and check for %s
# placeholders inside the call expression (parentheses, possibly multi-line).
hits = re.findall(r"\bexecute\s*\(((?:[^()]|\([^()]*\))*)\)", src, re.DOTALL)
ok = any("%s" in chunk for chunk in hits)
sys.exit(0 if ok else 1)
PYCHECK
  then
    ((l5 += 5)); pass "pipeline.py uses %s placeholders in execute() (parameterised SQL)"
  else
    fail "pipeline.py does not use %s placeholders for parameterised SQL"
  fi
fi
((score += l5))
pass "Level 5: idempotent upsert ($l5/15 pts)"

# ── Level 6 (10 pts): connection string + SDK use ───────────────────────────
l6=0
# sslmode=require somewhere visible: .env.example or pipeline default. The
# point is to show the student knows Azure Postgres needs SSL.
if grep -rqE "sslmode=require" "$REPO_ROOT" --include="*.py" --include=".env.example" --include="*.md" --exclude-dir=".git" 2>/dev/null; then
  ((l6 += 5)); pass "connection string includes sslmode=require"
else
  fail "no mention of sslmode=require in the repo — Azure Postgres rejects connections without it"
fi
# Uses the Azure Blob SDK (not raw HTTP or az CLI shellouts)
if [[ -f "$py" ]] && grep -qE "BlobServiceClient|from azure\.storage\.blob" "$py"; then
  ((l6 += 5)); pass "pipeline.py uses the azure-storage-blob SDK (BlobServiceClient)"
else
  fail "pipeline.py does not use the azure-storage-blob SDK (BlobServiceClient)"
fi
((score += l6))
pass "Level 6: connection + SDK ($l6/10 pts)"

# ── Level 7 (10 pts): AI_ASSIST.md filled in ────────────────────────────────
l7=0
ai="$REPO_ROOT/AI_ASSIST.md"
if [[ -f "$ai" ]]; then
  chars=$(wc -c < "$ai" | tr -d ' ')
  has_prompt=$(grep -c "## The prompt" "$ai" || true)
  has_code=$(grep -c "## The code" "$ai" || true)
  has_changed=$(grep -c "## What I changed" "$ai" || true)
  has_todo=$(grep -cE "^TODO:|^TODO " "$ai" || true)

  sections_ok=false
  filled_in=false
  if [[ "$has_prompt" -ge 1 && "$has_code" -ge 1 && "$has_changed" -ge 1 ]]; then
    sections_ok=true
  fi
  if [[ "$sections_ok" = true && "$chars" -ge 1800 && "$has_todo" -eq 0 ]]; then
    filled_in=true
  fi
  # All-or-nothing: scaffolds that ship the section headers do not earn points
  # without real content.
  if [[ "$filled_in" = true ]]; then
    l7=10
    pass "AI_ASSIST.md has all three sections and is filled in (${chars} chars)"
  else
    if [[ "$sections_ok" = true ]]; then
      fail "AI_ASSIST.md has section headers but is not filled in (${chars} chars, ${has_todo} TODO line(s); target 1800+ chars, 0 TODOs)"
    else
      fail "AI_ASSIST.md is missing one of the three required sections"
    fi
  fi
fi
((score += l7))
pass "Level 7: AI report ($l7/10 pts)"

# ── Level 8 (10 pts): README verification section + image link ──────────────
l8=0
rm="$REPO_ROOT/README.md"
if [[ -f "$rm" ]]; then
  heading_ok=false
  image_ok=false
  if grep -qE "^##[[:space:]]+Verification[[:space:]]*$" "$rm"; then
    heading_ok=true
  fi
  if grep -qE '!\[[^]]*\]\(docs/[^)]+\.(png|jpg|jpeg|gif)\)' "$rm"; then
    image_ok=true
  fi
  # All-or-nothing: the heading without an embedded image is just a template,
  # so the scaffold cannot drift past 0/10 by accident.
  if [[ "$heading_ok" = true && "$image_ok" = true ]]; then
    l8=10
    pass "README.md has '## Verification' heading and embeds a docs/ image"
  else
    if [[ "$heading_ok" = false ]]; then
      fail "README.md is missing the '## Verification' heading (Task 5)"
    fi
    if [[ "$image_ok" = false ]]; then
      fail "README.md does not embed a docs/ image with ![...](docs/...png)"
    fi
  fi
fi
((score += l8))
pass "Level 8: README verification ($l8/10 pts)"

# ── Level 9 (10 pts): Execution-history screenshot present ──────────────────
l9=0
shot=""
for candidate in "$REPO_ROOT/docs/execution_history.png" \
                 "$REPO_ROOT/docs/execution_history.jpg" \
                 "$REPO_ROOT/docs/execution_history.jpeg"; do
  if [[ -s "$candidate" ]]; then
    shot="$candidate"
    break
  fi
done
if [[ -n "$shot" ]]; then
  size=$(wc -c < "$shot" | tr -d ' ')
  if [[ "$size" -gt 5000 ]]; then
    if [[ "$shot" == *.png ]]; then
      ((l9 += 10)); pass "execution-history screenshot present at $(basename "$shot") (${size} bytes)"
    else
      ((l9 += 5)); warn "execution-history screenshot present at $(basename "$shot") but should be .png (partial credit, ${size} bytes)"
    fi
  else
    fail "execution-history screenshot at $(basename "$shot") looks too small to be a real screenshot (${size} bytes)"
  fi
else
  fail "docs/execution_history.png not found (Task 5 deliverable)"
fi
((score += l9))
pass "Level 9: execution screenshot ($l9/10 pts)"

# ── Code hygiene warnings (no points; just feedback) ────────────────────────
check_no_print_statements "$REPO_ROOT/src" "src/" || true
check_gitignore_python "$REPO_ROOT/.gitignore" || true

# ── Final result ────────────────────────────────────────────────────────────
print_results "Week 6 Autograder"
write_score "$score" "$PASSING" "$SCRIPT_DIR/score.json"

