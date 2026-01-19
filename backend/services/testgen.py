import json
from typing import Any, Dict

from backend.utils.groq_client import get_groq
from backend.rag.prompts import TEST_PROMPT
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
        print(f"JSON Parse Error in testgen: {e}")
        print(f"Attempted to parse: {clean[:200]}...")
        raise ValueError(f"Invalid JSON from model: {str(e)}")


def _empty_test_result(message: str) -> Dict[str, Any]:
    """Stable schema so frontend never breaks."""
    return {
        "test_file_name": "",
        "test_code": "",
        "test_cases_covered": [],
        "how_to_run": message,
    }


def _validate_and_fix_test_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the response has all required fields with correct types."""
    result = {
        "test_file_name": "",
        "test_code": "",
        "test_cases_covered": [],
        "how_to_run": ""
    }
    
    if isinstance(parsed.get("test_file_name"), str):
        result["test_file_name"] = parsed["test_file_name"]
    
    if isinstance(parsed.get("test_code"), str):
        result["test_code"] = parsed["test_code"]
    
    if isinstance(parsed.get("test_cases_covered"), list):
        result["test_cases_covered"] = [str(x) for x in parsed["test_cases_covered"]]
    
    if isinstance(parsed.get("how_to_run"), str):
        result["how_to_run"] = parsed["how_to_run"]
    
    return result


def generate_tests(code: str, language: str, model: str) -> Dict[str, Any]:
    """
    Generate unit tests for given code.
    
    Note: Caching is handled at the API layer (main.py).
    """
    
    # ✅ Input validation
    if not code or not code.strip():
        return _empty_test_result("No code provided to generate tests.")
    
    if len(code) > 50000:
        return _empty_test_result("Code is too long. Please submit code under 50,000 characters.")
    
    # ✅ Security check
    is_bad, reason = detect_prompt_injection(code)
    if is_bad:
        print(f"⚠️ SECURITY: Prompt injection detected - {reason}")
        return {
            "test_file_name": "",
            "test_code": "",
            "test_cases_covered": [],
            "how_to_run": "⚠️ Input rejected due to unsafe or prompt-injection content.",
            "error": reason,
        }
    
    # ✅ Format prompt
    try:
        prompt = TEST_PROMPT.format(language=language, code=code)
    except Exception as e:
        raise ValueError(f"Error formatting test prompt: {str(e)}")

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
                        "You are a precise test generation assistant. "
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
                            "You are a precise test generation assistant. "
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
        raise ValueError("Groq API returned empty response for test generation")

    # ✅ Parse and validate
    try:
        parsed = _safe_json_loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object.")
        
        parsed = _validate_and_fix_test_response(parsed)
        
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}")
        print(f"Raw model output: {content[:500]}...")
        return _empty_test_result(f"The AI model returned invalid JSON format. Error: {str(e)}")

    # ✅ Validate content
    if not parsed.get("test_code") or not parsed.get("test_code").strip():
        return _empty_test_result("The AI model did not generate any test code.")
    
    if not parsed.get("test_cases_covered") or len(parsed.get("test_cases_covered", [])) == 0:
        parsed["test_cases_covered"] = ["Test cases not explicitly listed by AI"]

    # ✅ Guarantee keys exist
    parsed.setdefault("test_file_name", f"test_{language}_code.py")
    parsed.setdefault("test_code", "")
    parsed.setdefault("test_cases_covered", [])
    parsed.setdefault("how_to_run", "")

    return parsed