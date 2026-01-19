import os
import uuid
import traceback
import copy
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from backend.services.explainer import explain_code
from backend.services.testgen import generate_tests
from backend.services.retrieval_debug import debug_retrieval
from backend.services.refactor import refactor_code

from backend.utils.cache import LRUCache, make_cache_key


# ------------------------------------------------------------
# ✅ Load backend/.env reliably (production-grade)
# ------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(
    title="AI Code Explainer (RAG + Groq)",
    description="AI-powered code explanation, unit test generation, and refactoring service",
    version="1.0.0",
)

# ✅ Supported default model
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")


# ------------------------------------------------------------
# ✅ CORS (restrict in production)
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# ✅ Caches (API-layer caching – production standard)
# ------------------------------------------------------------
explain_cache = LRUCache(max_size=256, ttl_seconds=3600)   # 1 hour
test_cache = LRUCache(max_size=128, ttl_seconds=3600)
refactor_cache = LRUCache(max_size=128, ttl_seconds=3600)


# ------------------------------------------------------------
# Pydantic Models with Validation
# ------------------------------------------------------------
class ExplainRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Code to explain")
    language: str = Field(default="python", description="Programming language")
    use_rag: bool = Field(default=True, description="Whether to use RAG for context")
    k: int = Field(default=4, ge=1, le=10, description="Number of documents to retrieve")

    @validator("code")
    def code_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Code cannot be empty or whitespace only")
        return v

    @validator("language")
    def language_lowercase(cls, v):
        return v.lower()


class TestRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Code to generate tests for")
    language: str = Field(default="python", description="Programming language")

    @validator("code")
    def code_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Code cannot be empty or whitespace only")
        return v

    @validator("language")
    def language_lowercase(cls, v):
        return v.lower()


class RefactorRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Code to refactor")
    language: str = Field(default="python", description="Programming language")

    @validator("code")
    def code_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Code cannot be empty or whitespace only")
        return v

    @validator("language")
    def language_lowercase(cls, v):
        return v.lower()


# ------------------------------------------------------------
# Helpers: Stable JSON Shapes (frontend safe)
# ------------------------------------------------------------
def explain_error_payload(error_msg: str, request_id: str) -> Dict[str, Any]:
    return {
        "overview": "Backend error occurred while generating explanation.",
        "step_by_step": [],
        "potential_bugs": [],
        "improvements": [],
        "complexity": {},
        "citations": [],
        "error": error_msg,
        "request_id": request_id,
        "cached": False,
    }


def tests_error_payload(error_msg: str, request_id: str) -> Dict[str, Any]:
    return {
        "test_file_name": "",
        "test_code": "",
        "test_cases_covered": [],
        "how_to_run": "",
        "error": error_msg,
        "request_id": request_id,
        "cached": False,
    }


def refactor_error_payload(error_msg: str, request_id: str) -> Dict[str, Any]:
    return {
        "refactored_code": "",
        "explanation_of_changes": [],
        "improvements": [],
        "complexity": {},
        "error": error_msg,
        "request_id": request_id,
        "cached": False,
    }


# ------------------------------------------------------------
# Middleware: Request ID
# ------------------------------------------------------------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "AI Code Explainer",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "explain": "/explain",
            "generate_tests": "/generate-tests",
            "refactor": "/refactor",
            "cache_stats": "/cache/stats",
            "cache_clear": "/cache/clear",
            "debug": "/debug-retrieval",
        },
    }


@app.get("/health")
def health():
    groq_key_present = bool(os.getenv("GROQ_API_KEY"))
    return {
        "status": "ok" if groq_key_present else "degraded",
        "model": MODEL,
        "env_loaded": ENV_PATH.exists(),
        "has_groq_key": groq_key_present,
        "cache_sizes": {
            "explain": explain_cache.size(),
            "test": test_cache.size(),
            "refactor": refactor_cache.size(),
        },
    }


# ------------------------------------------------------------
# ✅ Explain Endpoint with API-layer caching
# ------------------------------------------------------------
@app.post("/explain")
def explain(req: ExplainRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    try:
        payload = {
            "code": req.code.strip(),
            "language": req.language,
            "use_rag": req.use_rag,
            "k": req.k,
            "model": MODEL,
        }
        key = make_cache_key("explain", payload)

        cached = explain_cache.get(key)
        if cached:
            out = copy.deepcopy(cached)
            out["cached"] = True
            out["request_id"] = request_id
            print(f"[{request_id}] ⚡ CACHE HIT: /explain")
            return JSONResponse(status_code=200, content=out)

        # generate fresh
        result = explain_code(req.code, req.language, MODEL, use_rag=req.use_rag, k=req.k)

        if not isinstance(result, dict):
            raise ValueError("Invalid response from explain_code (expected dict).")

        result["cached"] = False
        result["request_id"] = request_id

        # Store only safe responses
        if "⚠️" not in result.get("overview", ""):
            explain_cache.set(key, result)
            print(f"[{request_id}] 💾 CACHE SET: /explain")

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"[{request_id}] ERROR in /explain: {e}")
        traceback.print_exc()
        return JSONResponse(status_code=200, content=explain_error_payload(str(e), request_id))


# ------------------------------------------------------------
# ✅ Generate Tests Endpoint with API-layer caching
# ------------------------------------------------------------
@app.post("/generate-tests")
def tests(req: TestRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    try:
        payload = {
            "code": req.code.strip(),
            "language": req.language,
            "model": MODEL,
        }
        key = make_cache_key("tests", payload)

        cached = test_cache.get(key)
        if cached:
            out = copy.deepcopy(cached)
            out["cached"] = True
            out["request_id"] = request_id
            print(f"[{request_id}] ⚡ CACHE HIT: /generate-tests")
            return JSONResponse(status_code=200, content=out)

        result = generate_tests(req.code, req.language, MODEL)

        if not isinstance(result, dict):
            result = {"result": result}

        result["cached"] = False
        result["request_id"] = request_id

        # Store safe responses
        if "⚠️" not in str(result.get("how_to_run", "")):
            test_cache.set(key, result)
            print(f"[{request_id}] 💾 CACHE SET: /generate-tests")

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"[{request_id}] ERROR in /generate-tests: {e}")
        traceback.print_exc()
        return JSONResponse(status_code=200, content=tests_error_payload(str(e), request_id))


# ------------------------------------------------------------
# ✅ Refactor Endpoint with API-layer caching
# ------------------------------------------------------------
@app.post("/refactor")
def refactor(req: RefactorRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    try:
        payload = {
            "code": req.code.strip(),
            "language": req.language,
            "model": MODEL,
        }
        key = make_cache_key("refactor", payload)

        cached = refactor_cache.get(key)
        if cached:
            out = copy.deepcopy(cached)
            out["cached"] = True
            out["request_id"] = request_id
            print(f"[{request_id}] ⚡ CACHE HIT: /refactor")
            return JSONResponse(status_code=200, content=out)

        result = refactor_code(req.code, req.language, MODEL)

        if not isinstance(result, dict):
            raise ValueError("Invalid response from refactor_code (expected dict).")

        result["cached"] = False
        result["request_id"] = request_id

        # Store safe responses
        if "⚠️" not in str(result.get("error", "")):
            refactor_cache.set(key, result)
            print(f"[{request_id}] 💾 CACHE SET: /refactor")

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"[{request_id}] ERROR in /refactor: {e}")
        traceback.print_exc()
        return JSONResponse(status_code=200, content=refactor_error_payload(str(e), request_id))


# ------------------------------------------------------------
# Cache endpoints
# ------------------------------------------------------------
@app.get("/cache/stats")
def cache_stats():
    return {
        "explain": explain_cache.stats(),
        "test": test_cache.stats(),
        "refactor": refactor_cache.stats(),
    }


@app.post("/cache/clear")
def clear_caches():
    explain_cache.clear()
    test_cache.clear()
    refactor_cache.clear()
    return {"status": "all caches cleared", "cache_sizes": {
        "explain": explain_cache.size(),
        "test": test_cache.size(),
        "refactor": refactor_cache.size(),
    }}


# ------------------------------------------------------------
# Debug retrieval
# ------------------------------------------------------------
@app.get("/debug-retrieval")
def debug(query: str, k: int = 4):
    try:
        return {"query": query, "results": debug_retrieval(query, k)}
    except Exception as e:
        traceback.print_exc()
        return {"query": query, "results": [], "error": str(e)}


# ------------------------------------------------------------
# Global fallback exception handler
# ------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    traceback.print_exc()

    return JSONResponse(
        status_code=200,
        content={
            "error": "An unexpected error occurred",
            "detail": str(exc),
            "request_id": request_id,
            "type": type(exc).__name__,
        },
    )


# ------------------------------------------------------------
# Run locally
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AI Code Explainer API")
    print(f"📦 Model: {MODEL}")
    print(f"🔑 Groq API Key: {'✅ Present' if os.getenv('GROQ_API_KEY') else '❌ Missing'}")
    print(f"📁 .env loaded: {ENV_PATH.exists()}")
    print(
        f"💾 Cache initialized: Explain={explain_cache.max_size}, "
        f"Test={test_cache.max_size}, Refactor={refactor_cache.max_size}"
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
