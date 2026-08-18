import io
import json
import os
import re
from html import escape

import google.generativeai as genai
from dotenv import load_dotenv
from gtts import gTTS
import streamlit as st


st.set_page_config(page_title="AccessFlow AI", page_icon="♿", layout="wide")


def load_gemini_model():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("Missing GEMINI_API_KEY. Add it to a .env file in the project folder before using Accessibility Studio.")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def get_uploaded_text(uploaded_file):
    if uploaded_file is None:
        return ""
    if uploaded_file.name.lower().endswith(".txt"):
        try:
            return uploaded_file.read().decode("utf-8", errors="replace")
        except Exception:
            return uploaded_file.read().decode("latin-1", errors="replace")
    return ""


def clean_json_response(raw_text):
    if raw_text is None:
        raise ValueError("Gemini returned an empty response.")
    text = str(raw_text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc


def validate_result(data):
    required_keys = ["title", "summary", "simplified_content", "key_points", "difficult_words"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required field: {key}")

    result = {
        "title": str(data.get("title", "Untitled")).strip() or "Untitled",
        "summary": str(data.get("summary", "")).strip() or "No summary provided.",
        "simplified_content": str(data.get("simplified_content", "")).strip() or "No simplified content provided.",
        "key_points": data.get("key_points") if isinstance(data.get("key_points"), list) else [str(data.get("key_points", "")).strip()],
        "difficult_words": data.get("difficult_words") if isinstance(data.get("difficult_words"), list) else [str(data.get("difficult_words", "")).strip()],
    }

    if not result["key_points"]:
        result["key_points"] = ["No key points provided."]
    if not result["difficult_words"]:
        result["difficult_words"] = ["No difficult words highlighted."]

    return result


def generate_accessible_version(content, mode, level, explain_words):
    model = load_gemini_model()
    if model is None:
        raise RuntimeError("Gemini model is not available.")

    mode_map = {
        "Easy Read": "Write it as easy read content for a general audience.",
        "Quick Summary": "Create a very short summary with the most important ideas first.",
        "Key Points": "List the most important points in a clear, direct format.",
        "Visual-Friendly Format": "Use short sections, direct sentences, and clear structure that is easy to scan.",
    }

    level_map = {
        "Very Simple": "Use very simple language and short sentences.",
        "Standard": "Use straightforward language for everyday reading.",
        "Detailed": "Keep the detail but make the structure easier to follow.",
    }

    words_rule = "Include a list of difficult words or terms with simple explanations in the difficult_words field." if explain_words else "Do not add a difficult word list. Set difficult_words to an empty list."

    prompt = f"""
You are helping turn written content into a more accessible version.
Read the original text exactly as provided.
Keep names, dates, numbers, warnings, safety information, deadlines, and important facts exactly as they appear.
Do not invent information or add facts that are not present in the source text.
If something is unclear or missing, say so plainly instead of guessing.

Goal: {mode_map.get(mode, 'Create a clear accessible version.')}
Reading level: {level_map.get(level, 'Use straightforward language.')}
{words_rule}

Original content:
{content}

Return ONLY valid JSON using this exact structure:
{
  "title": "A short title",
  "summary": "A brief summary in plain language",
  "simplified_content": "The accessible version of the text",
  "key_points": ["point 1", "point 2"],
  "difficult_words": ["word 1", "word 2"]
}

Rules:
- Preserve all important facts exactly.
- Keep the output as JSON, not markdown.
- Do not include any extra commentary outside the JSON object.
- Do not invent names, dates, numbers, actions, warnings, or outcomes.
"""

    response = model.generate_content(prompt)
    data = clean_json_response(getattr(response, "text", ""))
    return validate_result(data)


def render_home_page():
    st.title("AccessFlow AI")
    st.subheader("One piece of content. Multiple accessible experiences.")
    st.write(
        "AccessFlow AI helps people with low vision and people who find long or complex writing difficult to process "
        "turn one document into easier, clearer versions."
    )

    st.markdown("### The problem")
    st.write(
        "Many important documents are written in dense language. They can be hard to read, easy to miss, and difficult "
        "for some people to understand quickly."
    )

    st.markdown("### Who this helps")
    st.write(
        "- People with low vision\n"
        "- People who find long text tiring or confusing\n"
        "- People who benefit from short, clear explanations"
    )

    st.markdown("### Three-step workflow")
    st.markdown(
        "1. Paste or upload text\n"
        "2. Choose the format and reading level\n"
        "3. Review the accessible version, listen to it, and save it"
    )

    st.markdown("### Responsible AI notice")
    st.info(
        "This tool helps simplify content, but it should support human review. The model is asked to protect names, "
        "dates, numbers, warnings, and important facts and not invent information."
    )


def render_studio_page():
    st.title("Accessibility Studio")
    st.caption("Paste text or upload a .txt file to create a clearer version.")

    with st.form("accessibility_form"):
        content_text = st.text_area("Paste your content here", height=220, placeholder="Paste a webpage, letter, handout, or policy here...")
        uploaded_file = st.file_uploader("Optional: upload a .txt file", type=["txt"])

        if uploaded_file is not None and not content_text.strip():
            content_text = get_uploaded_text(uploaded_file)

        mode = st.selectbox("Choose the format", ["Easy Read", "Quick Summary", "Key Points", "Visual-Friendly Format"])
        reading_level = st.selectbox("Reading level", ["Very Simple", "Standard", "Detailed"])
        explain_words = st.checkbox("Explain difficult words")

        submitted = st.form_submit_button("Make Accessible", use_container_width=True)

    if submitted:
        if not content_text.strip():
            st.warning("Please enter or upload some content before generating an accessible version.")
            return

        with st.spinner("Creating a more accessible version..."):
            try:
                result = generate_accessible_version(content_text, mode, reading_level, explain_words)
                st.session_state["latest_accessible_result"] = result
                st.success("Accessible version ready.")

                st.subheader(result["title"])
                st.markdown(f"**Summary:** {result['summary']}")

                with st.expander("Simplified content", expanded=True):
                    st.write(result["simplified_content"])

                with st.expander("Key points"):
                    for point in result["key_points"]:
                        st.markdown(f"- {point}")

                with st.expander("Difficult words"):
                    if explain_words and result["difficult_words"]:
                        for item in result["difficult_words"]:
                            st.markdown(f"- {item}")
                    else:
                        st.write("No difficult word list requested.")

                accessible_text = result["simplified_content"]
                if accessible_text.strip():
                    try:
                        audio_buffer = io.BytesIO()
                        gTTS(text=accessible_text, lang="en").write_to_fp(audio_buffer)
                        st.audio(audio_buffer.getvalue(), format="audio/mp3")
                    except Exception as exc:
                        st.warning(f"Text-to-speech is unavailable right now: {exc}")

            except Exception as exc:
                st.error(f"Something went wrong while generating the accessible version: {exc}")


def render_my_accessible_version_page():
    st.title("My Accessible Version")

    if "latest_accessible_result" not in st.session_state or not st.session_state["latest_accessible_result"]:
        st.info("There is no accessible version yet. Go to Accessibility Studio to create one.")
        return

    result = st.session_state["latest_accessible_result"]

    st.subheader(result["title"])
    text_size = st.slider("Text size", 18, 32, 22)
    high_contrast = st.checkbox("High contrast mode")

    bg_color = "#111111" if high_contrast else "#ffffff"
    text_color = "#f5f5f5" if high_contrast else "#111111"

    st.markdown(
        "<div style='background-color:{}; color:{}; padding:1.2rem; border-radius:10px; line-height:1.7; font-size:{}px;'>"
        .format(bg_color, text_color, text_size),
        unsafe_allow_html=True,
    )
    st.markdown(escape(result["summary"]))
    st.markdown("<br>")
    st.markdown(escape(result["simplified_content"]).replace("\n", "<br>"), unsafe_allow_html=True)
    st.markdown("</div>")

    st.markdown("### Key points")
    for point in result["key_points"]:
        st.markdown(f"- {point}")

    if result["difficult_words"]:
        with st.expander("Difficult words explained"):
            for item in result["difficult_words"]:
                st.markdown(f"- {item}")

    st.download_button(
        label="Download accessible text",
        data=result["simplified_content"],
        file_name="accessflow_accessible_version.txt",
        mime="text/plain",
        use_container_width=True,
    )

    if st.button("Clear result", type="secondary"):
        st.session_state.pop("latest_accessible_result", None)
        st.rerun()


def main():
    page = st.sidebar.radio("Navigation", ["Home", "Accessibility Studio", "My Accessible Version"])

    if page == "Home":
        render_home_page()
    elif page == "Accessibility Studio":
        render_studio_page()
    else:
        render_my_accessible_version_page()


if __name__ == "__main__":
    main()
