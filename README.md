# LOKVAANI AI

*Preserve the past. Understand it. Build the future.*

A working Flask application that preserves the oral and traditional knowledge of Uttarakhand (Garhwali and Kumaoni stories, songs, recipes, customs). Contributors upload recordings or text, AI assists with transcription and organisation, Community Stewards verify, and only approved public records enter search and the "Ask LOKVAANI AI" assistant.

## 1. Quick start on Windows (PowerShell, Python 3.12)

```powershell
# 1. Project folder (unzip it, then:)
cd C:\path\to\lokvaani-ai

# 2. Virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
#    If PowerShell says "running scripts is disabled":
#    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned   (then retry the activate line)

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 4. Configuration (copying does NOT add any API credentials)
Copy-Item .env.example .env
#    Generate a secret and paste it after SECRET_KEY= in .env (optional in development):
python -c "import secrets; print(secrets.token_hex(32))"

# 5. Database
$env:FLASK_APP = "run.py"
flask db upgrade
flask seed-categories

# 6. First administrator (password is typed interactively, never stored in a file)
flask create-admin

# 7. Check which AI parts are ready (never calls paid APIs)
flask check-ai

# 8. Run
python run.py            # http://127.0.0.1:5000

# 9. Tests
pytest
```

**Troubleshooting**

| Problem | Fix |
|---|---|
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| FFmpeg missing (video upload fails with `FFMPEG_MISSING`) | `winget install Gyan.FFmpeg`, reopen PowerShell, run `ffmpeg -version`; or set `FFMPEG_PATH` in `.env` |
| Port 5000 in use | `$env:PORT = 5001; python run.py` |
| Whisper / embedding model download fails | First use downloads from huggingface.co (Whisper `small` is about 500 MB; the embedding model about 470 MB). Check internet/proxy, or use `WHISPER_MODEL_SIZE=base`. Search falls back to keywords and the job shows a clear error |
| No API key | Fine. Leave `OPENAI_API_KEY` empty. The app runs; chatbot is retrieval-only and translation/summary are skipped (and said to be skipped) |
| Changed `.env` | Restart `python run.py` |

Roles: register normally, then promote people in **Admin > Users and roles** (give someone *Community Steward*). Registering with "I want to contribute" creates a Contributor; a Public User can also become a Contributor from their profile. Nobody can reach Steward or Admin through any form.

## 2. Features

Landing page with real statistics, heritage exploration with keyword + semantic search and filters, record pages with media playback, contribution (text, audio, video, photos, documents), processing status with retry, contributor correction of transcripts, steward review queue, admin dashboard (users, roles, categories, audit, health), chatbot with citations, consent/withdraw/delete, CSRF, rate limits, secure uploads, custom error pages, responsive UI with original SVG artwork.

## 3. Architecture (for your mentor)

```
Browser ── Flask (blueprints: main, auth, contributions, search, chatbot, moderation, admin)
              │
              ├── SQLAlchemy models ── SQLite (dev) / PostgreSQL (deploy)
              ├── uploads/  (original media, random file names, access via /media/<id> only)
              └── services/
                    media.py          validation (extension, size, magic bytes), safe storage, FFmpeg
                    transcription.py  faster-whisper (local, free) or OpenAI Whisper; never invents text
                    translation.py    Hindi/English through an LLM (optional)
                    summarization.py  summary, tags, structured metadata as validated JSON (optional)
                    pipeline.py       background job: validate > extract audio > transcribe > translate > analyse
                    embeddings.py     Sentence Transformers (multilingual MiniLM)
                    retrieval.py      keyword SQL search, ChromaDB semantic search, index synchronisation
                    rag.py            retrieval-augmented answers with verified citations
```

**How the pieces work together**

1. *Transcription.* A recording is validated (extension, size, real file signature) and stored under a random name. Video goes through FFmpeg to mono 16 kHz audio. Whisper produces a transcript, stored as `original_text` and never overwritten; human corrections go to `edited_text`. Garhwali and Kumaoni have no dedicated Whisper model, so Hindi is used as the closest hint, and the UI warns that these transcripts are drafts.
2. *Translation and summary.* If an LLM provider is configured, the transcript is translated to Hindi and English and summarised, with tags and metadata returned as JSON that is validated. Without a provider, these steps are skipped and the job says so. Nothing is fabricated.
3. *Verification.* The contributor corrects the output and submits. A Community Steward listens, edits and decides. Every decision writes a `Review` row and an `AuditLog` row. Status flow: Draft, Processing, Pending Review, Needs Revision, Approved or Rejected (enforced by a state machine in `models.py`). AI never sets "verified".
4. *Semantic search.* `retrieval.sync_record()` is the single gate: a record is chunked, embedded and stored in ChromaDB **only while** it is Approved + public + consented. Any edit, rejection, withdrawal or deletion removes its vectors, and chat answers that cited it are redacted. Searches filter on `is_public` in the vector store and then re-check every hit against the database, so a stale vector can never surface a non-public record. If embeddings are unavailable, keyword search is used and labelled.
5. *RAG and citations.* A question retrieves passages from public records only. They are placed in numbered `<source>` blocks, flagged as untrusted data, and the LLM must cite `[n]` or answer `INSUFFICIENT_EVIDENCE`. The server drops citations that do not exist, rejects answers with no valid citation, and builds the displayed sources (title, link, excerpt, verifier) from stored database text, never from model output. With no LLM configured, the same retrieval is returned and labelled "Retrieval only".

## 4. Configuration and optional integrations

| Feature | Needs | Without it |
|---|---|---|
| Transcription | `TRANSCRIPTION_PROVIDER=faster_whisper` (free, local) or `openai` + `OPENAI_API_KEY` | Job fails with `TRANSCRIPTION_NOT_CONFIGURED`; contributor can type the transcript |
| Translation, summaries, tags | `TRANSLATION_PROVIDER=openai` / `LLM_PROVIDER=openai` + key | Skipped with a warning |
| Chatbot answers | `LLM_PROVIDER=openai` + key (any OpenAI-compatible `OPENAI_BASE_URL` works) | Retrieval-only mode |
| Semantic search | `sentence-transformers` + model download | Keyword search |
| Video | FFmpeg | `FFMPEG_MISSING` error |

After changing embedding settings or restoring a database, run `flask reindex`.

**Testing real integrations manually** (the automated suite mocks them): set the provider variables, run `flask check-ai`, upload a short Hindi recording, and confirm the transcript appears in *Review and correct*; approve a record as a steward and run `flask reindex`, then check Admin > Health shows "In sync: yes" and ask the chatbot about it.

## 5. Security notes

CSRF on every form and on the chat endpoint; scrypt password hashing and a password policy; server-side role checks on every protected route; Contributors can only touch their own records (404 otherwise); upload validation and random stored names with path-traversal checks; media served only through an access-controlled route; rate limits on login, registration, contact, search, chat and uploads; strict CSP with no inline scripts; production sessions use secure cookies and a required `SECRET_KEY`; stack traces never reach users; secrets live only in `.env` (git-ignored).

For production use PostgreSQL (`DATABASE_URL`), `APP_ENV=production`, HTTPS, a real WSGI server (for example `waitress`), and a shared rate-limit store (`RATELIMIT_STORAGE_URI=redis://...`).

## 6. Known limitations

* Garhwali, Kumaoni and Jaunsari are not supported by any mainstream speech model; transcripts are drafts and need fluent reviewers. The same holds for LLM translation quality.
* Background jobs run in an in-process thread pool: a server restart can leave a job stuck in Processing (use *Retry processing* after the record shows Draft, or reset the job). Use Celery/RQ for heavy production load.
* Files are stored on local disk; migrate to object storage for deployment.
* No email sending (no password-reset email yet); administrators can disable accounts but not reset passwords from the UI.
* Contributors cannot replace the media file of an existing record; delete and recreate instead.
* Original recordings of public records are playable by anyone; the consent text says so, but there is no separate "transcript only" option yet.
* Not built (out of scope for this version): knowledge-risk scoring, product/livelihood layer, expert-verification tiers.
* Illustrations are original SVG artwork; no photographs are bundled. Add licensed photographs in `app/static/images/` and credit them in the footer.

## 7. Verified results (from the build environment)

See the "Test results" section in the delivery message. Last full run: `pytest` — 75 passed.
