import streamlit as st
from orchestrator import handle_input

st.set_page_config(page_title="Driver Voice Bot")

st.title("🛵 Driver Support Bot")

if "session" not in st.session_state:
    st.session_state.session = {}

if "chat" not in st.session_state:
    st.session_state.chat = []

user_text = st.text_input("Driver boliye:")

if st.button("Send") and user_text.strip():
    reply = handle_input(user_text, st.session_state.session)
    st.session_state.chat.append(("User", user_text))
    st.session_state.chat.append(("Bot", reply))

for role, msg in st.session_state.chat:
    st.markdown(f"**{role}:** {msg}")
