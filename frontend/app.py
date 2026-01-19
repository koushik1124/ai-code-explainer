import json
import requests
import streamlit as st


# ----------------------------
# Page Setup
# ----------------------------
st.set_page_config(page_title="AI Code Explainer", layout="wide")
st.title("🧠 AI Code Explainer (RAG + Groq)")

API_BASE = st.sidebar.text_input("Backend URL", "http://127.0.0.1:8000").strip()


# ----------------------------
# Helpers
# ----------------------------
def safe_request(method: str, url: str, payload: dict | None = None, timeout: int = 90):
    """
    Safe HTTP request wrapper for production-grade Streamlit apps.
    Returns (ok: bool, status_code: int, data: dict | None, raw_text: str)
    """
    try:
        if method.upper() == "GET":
            res = requests.get(url, timeout=timeout)
        else:
            res = requests.post(url, json=payload or {}, timeout=timeout)

        raw_text = res.text or ""

        # Try to parse JSON even on error status codes
        try:
            data = res.json()
        except Exception:
            data = None

        # Return success=True for 200, False for everything else
        ok = (res.status_code == 200)
        
        return ok, res.status_code, data, raw_text

    except requests.exceptions.ConnectionError:
        return False, 0, None, "ConnectionError: Backend not reachable."
    except requests.exceptions.Timeout:
        return False, 0, None, "Timeout: Backend took too long to respond."
    except Exception as e:
        return False, 0, None, f"Unknown error: {e}"


def show_backend_status():
    """Display backend health status in sidebar."""
    ok, status, data, raw = safe_request("GET", f"{API_BASE}/health", timeout=10)
    if ok and data:
        st.sidebar.success(f"✅ Backend: Online\nModel: {data.get('model', 'unknown')}")
        
        # ✅ Show cache stats if available
        if 'cache_sizes' in data:
            with st.sidebar.expander("📊 Cache Statistics"):
                cache_stats = data['cache_sizes']
                st.write(f"**Explain Cache:** {cache_stats.get('explain', 0)} items")
                st.write(f"**Test Cache:** {cache_stats.get('test', 0)} items")
                st.write(f"**Refactor Cache:** {cache_stats.get('refactor', 0)} items")
    else:
        st.sidebar.error("❌ Backend: Offline")
        with st.sidebar.expander("Details"):
            st.code(raw)


def show_cache_status(data: dict):
    """
    ✅ NEW: Display cache status in sidebar.
    """
    if data.get("cached"):
        st.sidebar.success("⚡ Served from cache")
    else:
        st.sidebar.info("🧠 Fresh generation")


def render_explain_output(data: dict):
    """
    Nicely render explain response in a product UI style.
    """
    overview = data.get("overview", "")

    st.subheader("✅ Overview")
    st.write(overview if overview else "No overview returned.")

    tab1, tab2, tab3, tab4 = st.tabs(["🧭 Step-by-step", "🐞 Bugs", "🚀 Improvements", "📊 Complexity"])

    with tab1:
        steps = data.get("step_by_step", [])
        if isinstance(steps, list) and steps:
            for i, step in enumerate(steps, start=1):
                st.markdown(f"**{i}.** {step}")
        else:
            st.info("No step-by-step explanation returned.")

    with tab2:
        bugs = data.get("potential_bugs", [])
        if isinstance(bugs, list) and bugs:
            for b in bugs:
                st.markdown(f"- {b}")
        else:
            st.success("No major bugs detected.")

    with tab3:
        imps = data.get("improvements", [])
        if isinstance(imps, list) and imps:
            for imp in imps:
                st.markdown(f"- {imp}")
        else:
            st.info("No improvements suggested.")

    with tab4:
        st.json(data.get("complexity", {}))

    st.subheader("📌 Citations")
    citations = data.get("citations", [])
    if isinstance(citations, list) and citations:
        for i, c in enumerate(citations, start=1):
            src = c.get("source", "unknown")
            snippet = c.get("snippet", "")
            with st.expander(f"Source {i}: {src}"):
                st.write(snippet)
    else:
        st.info("No citations available.")


def render_tests_output(data: dict):
    """
    Render tests response nicely.
    """
    if "error" in data and data.get("error"):
        st.warning(f"⚠️ Test generation issue: {data.get('error')}")
        if data.get("raw_output"):
            with st.expander("Raw model output"):
                st.code(data["raw_output"])

    st.subheader("📄 Test File")
    st.write(data.get("test_file_name", "") or "tests_generated.py")

    st.subheader("🧪 Generated Unit Tests")
    test_code = data.get("test_code", "")
    if test_code:
        st.code(test_code, language="python")
        st.download_button(
            "⬇️ Download test file",
            data=test_code.encode("utf-8"),
            file_name=data.get("test_file_name", "tests_generated.py"),
            mime="text/plain",
        )
    else:
        st.info("No test code returned.")

    st.subheader("✅ Test Cases Covered")
    cases = data.get("test_cases_covered", [])
    if isinstance(cases, list) and cases:
        for c in cases:
            st.markdown(f"- {c}")
    else:
        st.info("No test cases list returned.")

    st.subheader("▶️ How to Run")
    how = data.get("how_to_run", "")
    if how:
        st.write(how)
    else:
        st.code("pytest -q", language="bash")


def render_refactor_output(data: dict):
    """
    Render refactored code response nicely.
    """
    if "error" in data and data.get("error"):
        st.warning(f"⚠️ Refactoring issue: {data.get('error')}")
        if data.get("raw_output"):
            with st.expander("Raw model output"):
                st.code(data["raw_output"])

    st.subheader("💎 Refactored Code")
    refactored = data.get("refactored_code", "")
    if refactored:
        st.code(refactored, language="python")
        st.download_button(
            "⬇️ Download refactored code",
            data=refactored.encode("utf-8"),
            file_name="refactored_code.py",
            mime="text/plain",
        )
    else:
        st.info("No refactored code returned.")

    st.subheader("📝 Explanation of Changes")
    changes = data.get("explanation_of_changes", [])
    if isinstance(changes, list) and changes:
        for i, change in enumerate(changes, start=1):
            st.markdown(f"**{i}.** {change}")
    else:
        st.info("No changes explained.")

    st.subheader("🚀 Improvements Made")
    improvements = data.get("improvements", [])
    if isinstance(improvements, list) and improvements:
        for imp in improvements:
            st.markdown(f"- {imp}")
    else:
        st.info("No improvements listed.")

    st.subheader("📊 Complexity Analysis")
    complexity = data.get("complexity", {})
    if complexity:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Before:**")
            before = complexity.get("before", {})
            if before:
                st.json(before)
            else:
                st.info("No 'before' complexity data")
        
        with col2:
            st.markdown("**After:**")
            after = complexity.get("after", {})
            if after:
                st.json(after)
            else:
                st.info("No 'after' complexity data")
        
        overall = complexity.get("overall_improvement", "")
        if overall:
            st.info(f"**Overall:** {overall}")
    else:
        st.info("No complexity analysis available.")


# ----------------------------
# Sidebar Backend status
# ----------------------------
show_backend_status()
use_rag = st.sidebar.toggle("Use RAG", value=True)
top_k = st.sidebar.slider("Top-K Retrieval", 2, 8, 4)

# ✅ Add cache clear button
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Clear Cache"):
    ok, status, data, raw = safe_request("POST", f"{API_BASE}/cache/clear", timeout=10)
    if ok:
        st.sidebar.success("Cache cleared successfully!")
        st.rerun()
    else:
        st.sidebar.error("Failed to clear cache")


# ----------------------------
# Input UI
# ----------------------------
language = st.selectbox("Language", ["python", "java", "javascript", "cpp"])
code = st.text_area("Paste your code here", height=280)

col1, col2, col3 = st.columns(3)


# ----------------------------
# Explain Code
# ----------------------------
with col1:
    if st.button("✅ Explain Code", use_container_width=True):
        if not code.strip():
            st.warning("Please paste code first.")
        else:
            with st.spinner("Explaining code..."):
                ok, status, data, raw = safe_request(
                    "POST",
                    f"{API_BASE}/explain",
                    payload={"code": code, "language": language, "use_rag": use_rag, "k": top_k},
                    timeout=120,
                )

            if ok and data:
                show_cache_status(data)  # ✅ Show cache status
                st.subheader("Explanation")
                render_explain_output(data)
            else:
                st.error("Failed to get explanation from backend.")
                st.write(f"Status: {status}")
                st.code(raw)


# ----------------------------
# Generate Unit Tests
# ----------------------------
with col2:
    if st.button("🧪 Generate Unit Tests", use_container_width=True):
        if not code.strip():
            st.warning("Please paste code first.")
        else:
            with st.spinner("Generating tests..."):
                ok, status, data, raw = safe_request(
                    "POST",
                    f"{API_BASE}/generate-tests",
                    payload={"code": code, "language": language},
                    timeout=180,
                )

            if ok and data:
                show_cache_status(data)  # ✅ Show cache status
                st.subheader("Unit Tests")
                render_tests_output(data)
            else:
                st.error("Failed to generate tests.")
                st.write(f"Status: {status}")
                st.code(raw)


# ----------------------------
# Refactor Code
# ----------------------------
with col3:
    if st.button("🔧 Refactor Code", use_container_width=True):
        if not code.strip():
            st.warning("Please paste code first.")
        else:
            with st.spinner("Refactoring code..."):
                ok, status, data, raw = safe_request(
                    "POST",
                    f"{API_BASE}/refactor",
                    payload={"code": code, "language": language},
                    timeout=180,
                )

            if ok and data:
                show_cache_status(data)  # ✅ Show cache status
                st.subheader("Refactored Code")
                render_refactor_output(data)
            else:
                st.error("Failed to refactor code.")
                st.write(f"Status: {status}")
                st.code(raw)