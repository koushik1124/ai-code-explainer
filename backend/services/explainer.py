import json
from typing import Any, Dict, List, Optional

from backend.utils.groq_client import get_groq
from backend.rag.retriever import get_retriever
from backend.rag.prompts import EXPLAIN_PROMPT
from backend.utils.security import detect_prompt_injection


def _safe_json_loads(text: str) -> Dict[str, Any]:
    """Safely parse model output as JSON."""
    clean = (text or "").strip()
    clean = clean.replace("```json", "").replace("```", "").strip()

    if "{" in clean and "}" in clean:
        start = clean.find("{")
        end = clean.rfind("}") + 1
        clean = clean[start:end]

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Attempted to parse: {clean[:200]}...")
        raise ValueError(f"Invalid JSON from model: {str(e)}")


def _retrieve_docs(retriever, query: str) -> List[Any]:
    """Compatible retrieval across LangChain versions."""
    try:
        return retriever.invoke(query)
    except AttributeError:
        return retriever.get_relevant_documents(query)
    except Exception as e:
        print(f"Warning: Document retrieval failed: {str(e)}")
        return []


def _empty_result(message: str, citations: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Stable JSON shape for frontend safety."""
    return {
        "overview": message,
        "step_by_step": [],
        "potential_bugs": [],
        "improvements": [],
        "complexity": {},
        "citations": citations or [],
    }


def _validate_and_fix_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the response has all required fields with correct types."""
    result = {
        "overview": "",
        "step_by_step": [],
        "potential_bugs": [],
        "improvements": [],
        "complexity": {},
        "citations": []
    }
    
    if isinstance(parsed.get("overview"), str):
        result["overview"] = parsed["overview"]
    
    if isinstance(parsed.get("step_by_step"), list):
        result["step_by_step"] = [str(x) for x in parsed["step_by_step"]]
    
    if isinstance(parsed.get("potential_bugs"), list):
        result["potential_bugs"] = [str(x) for x in parsed["potential_bugs"]]
    
    if isinstance(parsed.get("improvements"), list):
        result["improvements"] = [str(x) for x in parsed["improvements"]]
    
    if isinstance(parsed.get("complexity"), dict):
        result["complexity"] = parsed["complexity"]
    
    if isinstance(parsed.get("citations"), list):
        result["citations"] = parsed["citations"]
    
    return result


def explain_code(
    code: str, 
    language: str, 
    model: str,
    use_rag: bool = True,
    k: int = 4
) -> Dict[str, Any]:
    """
    Returns a JSON dict containing code explanation.
    
    Note: Caching is handled at the API layer (main.py).
    This function focuses purely on code analysis.
    """
    
    # ✅ Input validation
    if not code or not code.strip():
        return _empty_result("No code provided to explain.")
    
    if len(code) > 50000:
        return _empty_result("Code is too long. Please submit code under 50,000 characters.")
    
    # ✅ Security: Detect prompt injection
    is_bad, reason = detect_prompt_injection(code)
    if is_bad:
        print(f"⚠️ SECURITY: Prompt injection detected - {reason}")
        return {
            "overview": "⚠️ Input rejected due to unsafe or prompt-injection content.",
            "step_by_step": [],
            "potential_bugs": [reason],
            "improvements": ["Remove instruction-like text and provide only source code."],
            "complexity": {},
            "citations": [],
        }
    
    # ✅ RAG Retrieval (if enabled)
    retriever = None
    docs = []
    citations: List[Dict[str, str]] = []
    
    if use_rag:
        try:
            try:
                retriever = get_retriever(k=k)
            except TypeError:
                retriever = get_retriever()
        except Exception as e:
            print(f"Warning: RAG retriever initialization failed: {str(e)}")

        if retriever:
            try:
                query = code[:2000]
                docs = _retrieve_docs(retriever, query)
            except Exception as e:
                print(f"Warning: Document retrieval failed: {str(e)}")
                docs = []

    # Build context from retrieved docs
    context_parts: List[str] = []
    for d in docs or []:
        try:
            src = (getattr(d, "metadata", None) or {}).get("source", "unknown")
            text = getattr(d, "page_content", "") or ""
            snippet = text[:300]

            context_parts.append(f"[SOURCE: {src}]\n{text}")
            citations.append({"source": src, "snippet": snippet})
        except Exception as e:
            print(f"Warning: Error processing document: {str(e)}")
            continue

    context = "\n\n".join(context_parts).strip() or "No additional documents found in knowledge base."

    # ✅ Format prompt
    try:
        prompt = EXPLAIN_PROMPT.format(context=context, language=language, code=code)
    except Exception as e:
        raise ValueError(f"Error formatting prompt: {str(e)}")

    # ✅ Get Groq client
    try:
        client = get_groq()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Groq client: {str(e)}. Check your GROQ_API_KEY in .env")

    # ✅ Call Groq API
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise code analysis assistant. "
                        "You MUST respond with valid JSON only. "
                        "Never include markdown, explanations, or any text outside the JSON object. "
                        "Your response must start with { and end with }."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as json_error:
        print(f"JSON mode failed: {str(json_error)}, trying without response_format...")
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise code analysis assistant. "
                            "You MUST respond with valid JSON only. "
                            "Never include markdown, explanations, or any text outside the JSON object. "
                            "Your response must start with { and end with }."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
        except Exception as fallback_error:
            raise RuntimeError(f"Groq API call failed: {str(fallback_error)}")

    content = (resp.choices[0].message.content or "").strip()
    
    if not content:
        raise ValueError("Groq API returned empty response")

    # ✅ Parse and validate JSON
    try:
        parsed = _safe_json_loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object.")
        
        parsed = _validate_and_fix_response(parsed)
        
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw model output: {content[:500]}...")
        return _empty_result(
            f"The AI model returned invalid JSON format. Error: {str(e)}",
            citations=citations
        )

    # ✅ Attach citations
    if not parsed.get("citations"):
        parsed["citations"] = citations

    # ✅ Guarantee required keys exist
    parsed.setdefault("overview", "")
    parsed.setdefault("step_by_step", [])
    parsed.setdefault("potential_bugs", [])
    parsed.setdefault("improvements", [])
    parsed.setdefault("complexity", {})

    return parsed