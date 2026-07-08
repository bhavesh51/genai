# Project 8 — Educational Content Generator & Adaptive Tutor

Production-grade FastAPI service for curriculum ingestion, lesson generation, quiz generation, adaptive mastery tracking, and Socratic tutoring.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| LLM | `meta-llama/Meta-Llama-3-8B-Instruct` via OpenAI-compatible endpoint |
| Embeddings | `sentence-transformers/all-mpnet-base-v2` |
| Vector DB | Milvus |
| Cache / Session Store | Redis |
| Mastery Model | Bayesian Knowledge Tracing (BKT) |
| Container Base | UBI9 Python 3.11 |
| Deploy | OpenShift Route + Kustomize |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/content/generate` | Generate adaptive lesson content for a learner/topic |
| POST | `/api/v1/content/ingest` | Embed and ingest curriculum chunk into Milvus |
| POST | `/api/v1/quiz/generate` | Generate quiz and cache it in Redis |
| POST | `/api/v1/quiz/submit` | Grade quiz, update mastery, return new difficulty |
| POST | `/api/v1/tutor/message` | Send learner message to Socratic tutor |
| DELETE | `/api/v1/tutor/session/{session_id}` | Clear tutor conversation history |
| GET | `/api/v1/mastery/{learner_id}` | Get all topic mastery values for learner |
| GET | `/api/v1/mastery/{learner_id}/{topic}` | Get mastery and difficulty for one topic |
| GET | `/health` | Liveness endpoint |
| GET | `/ready` | Readiness endpoint |

## Bayesian Knowledge Tracing (BKT)

BKT models the probability that a learner has mastered a skill or topic.

- `p_init`: initial mastery probability
- `p_learn`: probability of learning after an interaction
- `p_forget`: probability of forgetting
- `p_guess`: probability of guessing correctly without mastery
- `p_slip`: probability of answering incorrectly despite mastery

After each quiz answer, the service updates learner mastery using the standard BKT posterior update and transition step. The resulting mastery maps to difficulty bands:

- `beginner` for mastery `< 0.3`
- `intermediate` for mastery `< 0.7`
- `advanced` otherwise

## Quick Start

```bash
cd projects/08-educational-content-generator
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8080
```

## Example cURL Commands

### Ingest curriculum content

```bash
curl -X POST http://localhost:8080/api/v1/content/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "chunk_id": "algebra-001",
    "subject": "math",
    "topic": "linear equations",
    "text": "A linear equation is an equation in which the highest power of the variable is one."
  }'
```

### Generate lesson content

```bash
curl -X POST http://localhost:8080/api/v1/content/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "linear equations",
    "learner_id": "learner-123",
    "subject": "math"
  }'
```

### Generate quiz

```bash
curl -X POST http://localhost:8080/api/v1/quiz/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "linear equations",
    "learner_id": "learner-123",
    "num_questions": 5
  }'
```

### Submit quiz answers

```bash
curl -X POST http://localhost:8080/api/v1/quiz/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "quiz_id": "replace-with-quiz-id",
    "learner_id": "learner-123",
    "answers": [1, 0, 2, 3, 1]
  }'
```

### Chat with tutor

```bash
curl -X POST http://localhost:8080/api/v1/tutor/message \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "session-001",
    "learner_id": "learner-123",
    "topic": "linear equations",
    "message": "I do not understand how to isolate x."
  }'
```

### Check mastery

```bash
curl http://localhost:8080/api/v1/mastery/learner-123/linear%20equations
```

## Deployment

```bash
oc apply -k deploy/kustomize/overlays/production
```
