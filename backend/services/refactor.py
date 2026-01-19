import json
from typing import Any, Dict

from backend.utils.groq_client import get_groq
from backend.rag.prompts import REFACTOR_PROMPT
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
        print(f"JSON Parse Error in refactor: {e}")
        print(f"Attempted to parse: {clean[:200]}...")
        raise ValueError(f"Invalid JSON from model: {str(e)}")


def _empty_refactor_result(message: str) -> Dict[str, Any]:
    """Stable schema so frontend never breaks."""
    return {
        "refactored_code": "",
        "explanation_of_changes": [],
        "improvements": [],
        "complexity": {},
        "error": message,
    }


def _validate_and_fix_refactor_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the response has all required fields with correct types."""
    result = {
        "refactored_code": "",
        "explanation_of_changes": [],
        "improvements": [],
        "complexity": {}
    }
    
    if isinstance(parsed.get("refactored_code"), str):
        result["refactored_code"] = parsed["refactored_code"]
    
    if isinstance(parsed.get("explanation_of_changes"), list):
        result["explanation_of_changes"] = [str(x) for x in parsed["explanation_of_changes"]]
    
    if isinstance(parsed.get("improvements"), list):
        result["improvements"] = [str(x) for x in parsed["improvements"]]
    
    if isinstance(parsed.get("complexity"), dict):
        result["complexity"] = parsed["complexity"]
    
    return result


def refactor_code(code: str, language: str, model: str) -> Dict[str, Any]:
    """
    Refactor and improve the given code.
    
    Note: Caching is handled at the API layer (main.py).
    """
    
    # ✅ Input validation
    if not code or not code.strip():
        return _empty_refactor_result("No code provided to refactor.")
    
    if len(code) > 50000:
        return _empty_refactor_result("Code is too long. Please submit code under 50,000 characters.")
    
    # ✅ Security check
    is_bad, reason = detect_prompt_injection(code)
    if is_bad:
        print(f"⚠️ SECURITY: Prompt injection detected - {reason}")
        return {
            "refactored_code": "",
            "explanation_of_changes": [],
            "improvements": ["Remove instruction-like text and provide only source code."],
            "complexity": {},
            "error": f"⚠️ Input rejected due to unsafe or prompt-injection content: {reason}",
        }
    
    # ✅ Format prompt
    try:
        prompt = REFACTOR_PROMPT.format(language=language, code=code)
    except Exception as e:
        raise ValueError(f"Error formatting refactor prompt: {str(e)}")

    # ✅ Get Groq client
    try:
        client = get_groq()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Groq client: {str(e)}. Check your GROQ_API_KEY in .env")

    # ✅ Call API
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise code refactoring assistant. "
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
                            "You are a precise code refactoring assistant. "
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
        raise ValueError("Groq API returned empty response for refactoring")

    # ✅ Parse and validate
    try:
        parsed = _safe_json_loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object.")
        
        parsed = _validate_and_fix_refactor_response(parsed)
        
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw model output: {content[:500]}...")
        return _empty_refactor_result(f"The AI model returned invalid JSON format. Error: {str(e)}")

    # ✅ Validate content
    if not parsed.get("refactored_code") or not parsed.get("refactored_code").strip():
        return _empty_refactor_result("The AI model did not generate any refactored code.")

    # ✅ Guarantee keys exist
    parsed.setdefault("refactored_code", "")
    parsed.setdefault("explanation_of_changes", [])
    parsed.setdefault("improvements", [])
    parsed.setdefault("complexity", {})

    return parsed

