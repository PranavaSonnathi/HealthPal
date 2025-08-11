import streamlit as st
import google.generativeai as genai
from PIL import Image
import pytesseract
import json
import re
import uuid
from db import login_user, register_user, save_chat, get_user_history
import datetime

# --- Configure Gemini ---
genai.configure(api_key="AIzaSyCXDUm-sTF9ymdW56YHddb5inoOWFx39ks")
model = genai.GenerativeModel("gemini-2.5-flash")

# --- Page Config ---
st.set_page_config(page_title="HealthPal", layout="centered")
st.markdown("<h1 style='text-align: center;'>🩺 HealthPal: Your AI Medical & Therapeutic Assistant</h1>", unsafe_allow_html=True)

# --- Session Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "therapy_disclaimer_shown" not in st.session_state:
    st.session_state["therapy_disclaimer_shown"] = False

# --- Authentication ---
if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("✅ Logged in successfully!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")
    with col2:
        if st.button("Sign Up"):
            if register_user(username, password):
                st.success("✅ Account created! Please log in.")
            else:
                st.warning("⚠ Username already exists.")
    st.stop()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Mode")
    mode = st.radio("", ["🩺 Medical Assistant", "🧠 Therapy Companion"], label_visibility="collapsed")
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

# --- Chat History ---
mode_key = "medical_messages" if "Medical" in mode else "therapy_messages"
if mode_key not in st.session_state:
    st.session_state[mode_key] = []

# --- Show Chat History ---
for msg in st.session_state[mode_key]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- FAQs / Suggestions ---
if len(st.session_state[mode_key]) == 0:
    st.markdown("💡 *Try asking:*")
    if "Medical" in mode:
        st.markdown("- I have a headache and fever.")
        st.markdown("- Suggest OTC medicine for cold.")
        st.markdown("- What could cause stomach pain?")
    else:
        st.markdown("- I'm feeling anxious and can't sleep.")
        st.markdown("- How do I cope with overthinking?")
        st.markdown("- I feel lonely and sad.")

    # Show recent chats
    history = get_user_history(st.session_state.username)
    if history:
        st.markdown("---")
        st.markdown("🕑 *Recent Queries:*")
        for h in history:
            st.markdown(f"- {h['message']}")

# --- Image Upload ---
uploaded_image = st.file_uploader("Upload medical image (optional)", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed")
if uploaded_image:
    st.image(uploaded_image, caption="🖼 Preview", use_container_width=True)

# --- Chat Input ---
def estimate_tokens(text):
    return len(text) // 4

def get_context_parts(system_instruction, history, max_tokens=1800):
    parts = [system_instruction]
    total = estimate_tokens(system_instruction)
    for msg in reversed(history):
        formatted = f"{msg['role'].capitalize()}: {msg['content']}"
        tokens = estimate_tokens(formatted)
        if total + tokens > max_tokens:
            break
        parts.insert(1, formatted)
        total += tokens
    return parts

prompt = st.chat_input(f"Ask a question to your {mode}...")
if prompt:
    ocr_text = None
    if uploaded_image:
        fname = uploaded_image.name.lower()
        if any(kw in fname for kw in ["screenshot", "terminal", "code", "debug", "log", "cmd", "console"]):
            st.warning("🛑 Unrelated image. Please upload a medical report, scan, or prescription.")
            st.stop()
        if not any(word in prompt.lower() for word in ["image", "photo", "picture", "scan", "report", "prescription"]):
            st.warning("⚠ You uploaded an image, but your prompt doesn't mention it. Please include it if relevant.")
            st.stop()
        try:
            extracted_text = pytesseract.image_to_string(Image.open(uploaded_image))
            if extracted_text.strip():
                ocr_text = extracted_text.strip()
                prompt += "\n\n(Note: The uploaded image appears to be a prescription or report. Please analyze it.)"
        except Exception as e:
            print(f"OCR Error: {e}")

    st.session_state[mode_key].append({"role": "user", "content": prompt})
    save_chat(st.session_state.username, st.session_state.session_id, mode, "user", prompt, ocr_text)

    with st.chat_message("user"):
        st.markdown(prompt)

    system_instruction = """You are HealthPal, an advanced, empathetic AI medical assistant.

Important:
- NEVER respond to images unrelated to medical topics. If an image looks like a screenshot, code, or technical diagram, respond: 
  "I'm sorry, this image doesn't appear to be medical in nature. Please upload medical reports, scans, or symptom photos."
- You MUST reply ONLY with a single, valid JSON object.
- If the user describes symptoms (e.g., fever, pain, fatigue, irregular periods, etc.), analyze them and gently suggest a possible medical condition or illness.
  - Be cautious — never make a definitive diagnosis.
  - Always encourage users to consult a doctor.
- For medication-related queries, suggest only common OTC options which are widely known in india and donot suggest formulas (if appropriate), and remind users this is not a substitute for professional medical advice.
- Use bold to highlight important terms like possible diagnosis, **symptom, **medication, and **doctor type.
- Use this response format:
{
  "answer": "Your friendly, plain-text reply here.",
  "suggestions": ["Follow-up question 1", "2", "3"]
}
- If no follow-ups: "suggestions": []
- No markdown or explanations outside the JSON.

If Therapy:You are HealthPal, a compassionate, emotionally intelligent AI therapy companion.

Your role is to support users like a deeply caring, non-judgmental friend who listens, understands, and gently helps them feel seen and supported.

🧠 Core Behavior:
- Respond to emotional concerns like anxiety, stress, loneliness, heartbreak, overthinking, or sadness with warmth, empathy, and care.
- Offer comforting thoughts, soothing reflections, and reality checks like a supportive human would.
- Ask gentle follow-up questions when needed to help the user open up or reflect more.
- Let your tone feel human — like a friend who's always there, not like a chatbot or doctor.

💬 Mental Health Report Feature:
- If the user asks for a mental health report, begin a short reflective conversation:
  - Ask 3–5 thoughtful questions to understand their current mood, stressors, habits, or emotional triggers.
  - After that, return a summary as:
    - Their emotional state
    - Major stress factors
    - Coping mechanisms they’re using (or could use)
    - A kind suggestion or affirmation

⚠ Disclaimer:
- Show the following note only once as the first assistant message in the session:
  - "Note: This is not a substitute for professional mental health care. If you’re in crisis, please reach out to a mental health professional or helpline."
- Do not repeat this disclaimer again unless the user asks about suicide, self-harm, or crisis situations.

🧾 Format:
Respond ONLY with a single valid JSON object like this:
{
  "answer": "Your warm, emotionally supportive plain-text response goes here.",
  "suggestions": ["Helpful follow-up question 1", "2", "3"]
}
- If you have no follow-ups: "suggestions": []
- No formatting, markdown, or symbols.""".strip()

    parts = get_context_parts(system_instruction, st.session_state[mode_key])
    parts.append(f"User: {prompt}")
    if uploaded_image:
        parts.append(Image.open(uploaded_image))

    with st.chat_message("assistant"):
        try:
            response = model.generate_content(
                parts,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=1,
                    top_k=1,
                    max_output_tokens=2048
                )
            )
            raw = response.text.strip()
            raw = re.sub(r"[`]+(json)?", "", raw)
            raw = raw.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").strip()
            parsed = json.loads(raw)

            if "Therapy" in mode and not st.session_state["therapy_disclaimer_shown"]:
                st.markdown("Note: This is not a substitute for professional mental health care.")
                st.session_state["therapy_disclaimer_shown"] = True

            st.markdown(parsed["answer"])
            st.session_state[mode_key].append({"role": "assistant", "content": parsed["answer"]})
            save_chat(st.session_state.username, st.session_state.session_id, mode, "assistant", parsed["answer"])

            if "suggestions" in parsed and isinstance(parsed["suggestions"], list) and parsed["suggestions"]:
                st.markdown("Follow-up Questions:")
                for s in parsed["suggestions"]:
                    st.markdown(f"- {s}")

        except json.JSONDecodeError:
            st.error("❌ Gemini returned invalid JSON. Try again.")
        except Exception as e:
            st.error(f"❌ Error: {e}")