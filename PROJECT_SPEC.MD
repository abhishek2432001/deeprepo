Here is the complete, self-contained **Master Specification Document**.

Save the content below as **`PROJECT_SPEC.md`**. You can then drag and drop this file into your AI tool (Antigravity/Cursor/Windsurf) and it will have every single architectural decision we discussed.

---

### **Copy This Content into `PROJECT_SPEC.md**`

```markdown
# PROJECT SPECIFICATION: DeepRepo (Local RAG Engine)

## 1. Project Overview
**Goal:** Build a production-grade, extensible Python library (`deeprepo`) for performing RAG (Retrieval Augmented Generation) on local codebases.
**Core Philosophy:** "Raw Python" implementation. No heavy frameworks (LangChain/LlamaIndex) and no external Vector DBs (Pinecone/Chroma). We build the vector store from scratch using NumPy and JSON.
**Deliverables:**
1.  `deeprepo_core`: A PyPI-installable library containing the logic.
2.  `web_app`: A FastAPI service wrapping the library.
3.  `docker`: Full containerization for "plug-and-play" deployment.

## 2. Tech Stack
* **Language:** Python 3.10+
* **Math/Data:** `numpy` (Cosine Similarity), `pandas` (Optional, for debugging).
* **AI/LLM:** `openai` SDK, `google-generativeai` SDK.
* **Web API:** `fastapi`, `uvicorn`, `pydantic`.
* **Infrastructure:** Docker, Docker Compose.

## 3. Architecture & Design Patterns (Strict Requirement)
The AI agent must implement the following patterns:
1.  **Repository Pattern (`VectorStore`):** Decouples the storage logic (JSON/Disk) from the application logic.
2.  **Strategy Pattern (`LLMProvider`):** Abstract base classes that define how an LLM behaves, allowing us to swap OpenAI for Gemini.
3.  **Registry Pattern (`@register_llm`):** A dynamic registry that auto-discovers LLM providers without hardcoded `if/else` chains.
4.  **Singleton Pattern (`API State`):** The FastAPI app must load the Vector Store into memory *once* at startup, not on every request.

## 4. Directory Structure
```text
DeepRepo-Project/
├── deeprepo_core/              # [LIBRARY]
│   ├── pyproject.toml
│   └── src/
│       └── deeprepo/
│           ├── __init__.py
│           ├── client.py       # Facade (Main Entry Point)
│           ├── storage.py      # VectorStore (JSON + NumPy)
│           ├── ingestion.py    # File Scanning & Chunking
│           ├── registry.py     # Decorator-based Registry
│           ├── interfaces.py   # Abstract Base Classes
│           └── providers/      # Plugin Folder
│               ├── __init__.py # Factory
│               ├── openai_v.py
│               └── gemini_v.py
│
├── web_app/                    # [API]
│   ├── main.py                 # FastAPI App
│   └── requirements.txt
│
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Service orchestration
└── README.md

```

## 5. Implementation Phases (Step-by-Step Instructions)

### Phase 1: Core Math & Storage

* **Task:** Implement `src/deeprepo/storage.py`.
* **Requirements:**
* Create `VectorStore` class.
* `save(chunks)`: Serialize list of dicts to `vectors.json`.
* `load()`: Read JSON and convert embedding lists to `np.array` for speed.
* `search(query_vec)`: Implement cosine similarity manually: `dot(A, B) / (norm(A) * norm(B))`.



### Phase 2: Ingestion Engine

* **Task:** Implement `src/deeprepo/ingestion.py`.
* **Requirements:**
* Use `os.walk` to traverse a directory.
* **Filter:** Ignore `.git`, `__pycache__`, `node_modules`, and binary files.
* **Chunking:** Split text into 1000-character chunks with 100-character overlap to preserve context at boundaries.



### Phase 3: The Plug-and-Play AI System (Registry)

* **Task:** Implement the extensible provider system.
* **Step A (`interfaces.py`):** Define `LLMProvider(ABC)` and `EmbeddingProvider(ABC)`.
* **Step B (`registry.py`):** Create a global dictionary and a `@register_llm(name)` decorator. Use `pkgutil` to auto-import modules in `providers/`.
* **Step C (`providers/`):** Implement `gemini_v.py` and `openai_v.py` using the decorator.
* **Step D (`client.py`):** The `DeepRepoClient` should initialize by calling a factory that reads `os.environ["LLM_PROVIDER"]` (defaulting to "openai").

### Phase 4: The Web API (FastAPI)

* **Task:** Create `web_app/main.py`.
* **Endpoints:**
* `POST /ingest`: payload `{"path": "/app/data"}`. Triggers ingestion.
* `POST /chat`: payload `{"query": "..."}`. Returns answer + history.


* **Context:** Use FastAPI `lifespan` to load the `DeepRepoClient` into memory only once when the server starts.

### Phase 5: Containerization

* **Task:** Create `Dockerfile` and `docker-compose.yml`.
* **Dockerfile:**
* Base: `python:3.10-slim`.
* Copy `deeprepo_core` and run `pip install -e .`.
* Copy `web_app` and run `uvicorn`.


* **Compose:**
* Map port `8000:8000`.
* Volume: `./data_mount:/app/data` (for code ingestion).
* Env Vars: `LLM_PROVIDER`, `OPENAI_API_KEY`, `GEMINI_API_KEY`.



## 6. Constraints & Guidelines

* **Documentation:** All functions must have Google-style docstrings.
* **Error Handling:** If `vectors.json` is missing, the store should initialize as empty, not crash.
* **Testing:** Create a `tests/` folder with one unit test mocking the vector math.

```

---

### **How to Trigger the Agent**

Once you have the file above, simply paste this instruction into your chat window:

> "I have uploaded `PROJECT_SPEC.md` which contains the full architecture for the 'DeepRepo' project.
>
> Please read it carefully. **Start by executing Phase 1 and Phase 2**: set up the directory structure, create the `pyproject.toml`, and implement the `VectorStore` and `Ingestion` logic exactly as specified in the document."

```