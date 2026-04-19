import os
import traceback
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from notion_client import Client as NotionClient
from rag_engine import chat_with_history, has_documents

NOTION_DATABASE_ID = "3470ea2ca58980e1b02ce839467a702e"

def log_to_notion(question: str, answer: str):
    try:
        notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Date": {"title": [{"text": {"content": datetime.utcnow().strftime("%Y-%m-%d %H:%M")}}]},
                "Question": {"rich_text": [{"text": {"content": question[:2000]}}]},
                "Answer": {"rich_text": [{"text": {"content": answer[:2000]}}]},
            },
        )
    except Exception:
        pass

load_dotenv()

MAX_QUESTIONS = 5

st.set_page_config(
    page_title="Shortcut — არქიტექტორის ასისტენტი",
    page_icon="⚡",
    layout="wide",
)


if "question_count" not in st.session_state:
    st.session_state.question_count = 0

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Georgian:wght@400;500;600&display=swap" rel="stylesheet">
<style>
* { font-family: 'Noto Sans Georgian', 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif !important; }
[data-testid="stChatMessage"] h1 { font-size: 1.2rem !important; }
[data-testid="stChatMessage"] h2 { font-size: 1.05rem !important; }
[data-testid="stChatMessage"] h3 { font-size: 0.95rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚡ Shortcut")
st.caption("პირველი ქართულენოვანი AI ასისტენტი არქიტექტორებისთვის — კანონმდებლობა, ნებართვები, დოკუმენტაცია")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("📋 კითხვის მაგალითები")
    example_questions = [
        "მომწერე ყველაფერი საცხოვრებელი ზონა 4-ის შესახებ",
        "რა დოკუმენტები დამჭირდება ინდივიდუალური სახლის აშენებისთვის?",
        "რამდენია ჯარიმა უნებართვო მშენებლობისთვის?",
    ]
    for q in example_questions:
        if st.button(q, key=q, use_container_width=True):
            st.session_state["pending_question"] = q

    st.divider()
    remaining = max(0, MAX_QUESTIONS - st.session_state.question_count)
    st.info(f"აპლიკაცია მუშაობს სატესტო რეჟიმში. თითოეულ მომხმარებელს შეუძლია დღეში მაქსიმუმ 5 შეკითხვა დასვას. დარჩენილია: **{remaining}/{MAX_QUESTIONS}**")

    st.divider()
    if st.button("🗑️ საუბრის გასუფთავება"):
        st.session_state.messages = []
        st.rerun()

# ── Chat area ─────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for message in st.session_state.messages:
    avatar = "👤" if message["role"] == "user" else "⚡"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

limit_reached = st.session_state.question_count >= MAX_QUESTIONS

typed = st.chat_input("დასვით კითხვა კანონმდებლობის შესახებ...")

if "pending_question" in st.session_state:
    prompt = st.session_state.pop("pending_question")
else:
    prompt = typed

if limit_reached:
    st.warning("24 საათის განმავლობაში კითხვების ლიმიტი ამოიწურა. ხვალ ახლიდან შეძლებ.")
    prompt = None

if prompt:
    st.session_state.question_count += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚡"):
        with st.spinner("ვეძებ..."):
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                response_text = chat_with_history(history)
                st.markdown(response_text)
            except Exception as e:
                response_text = f"⚠️ შეცდომა: {str(e)}"
                st.error(response_text)
                print(traceback.format_exc())

        st.session_state.messages.append({"role": "assistant", "content": response_text})
        log_to_notion(prompt, response_text)
