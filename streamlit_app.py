import streamlit as st
import websocket
import threading
import uuid
import queue
import time
import os
import requests
from streamlit_autorefresh import st_autorefresh

# ---------------- CONFIG ----------------
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "wss://ai-chat-backend-production-f884.up.railway.app/ws/session/{session_id}")
BACKEND_HTTP_URL = os.getenv("BACKEND_HTTP_URL", "https://ai-chat-backend-production-f884.up.railway.app")

# ---------------- STATE ----------------
if "session_id" not in st.session_state: st.session_state.session_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "connected" not in st.session_state: st.session_state.connected = False
if "ws" not in st.session_state: st.session_state.ws = None
if "ws_queue" not in st.session_state: st.session_state.ws_queue = queue.Queue()
if "waiting" not in st.session_state: st.session_state.waiting = False
if "summary" not in st.session_state: st.session_state.summary = None

# ---------------- WEBSOCKET ----------------
def start_ws(url, msg_queue):
    def on_message(ws, message):
        msg_queue.put(message)

    def on_open(ws):
        print("WS Connected")

    def on_close(ws, *_):
        print("WS Closed")

    ws = websocket.WebSocketApp(
        url, 
        on_message=on_message, 
        on_open=on_open, 
        on_close=on_close
    )
    
    t = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()
    return ws

# ---------------- UI SETUP ----------------
st.set_page_config(page_title="Realtime AI Assistant", page_icon="✨", layout="wide")

# ---------------- PRODUCTION-GRADE CSS ----------------
st.markdown("""
<style>
    /* --- FONTS & BASICS --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #e2e8f0;
        background-color: #020617; /* Slate 950 - Deepest Blue/Black */
        letter-spacing: -0.01em;
    }
    
    /* Smooth Scroll Behavior */
    html {
        scroll-behavior: smooth;
    }

    /* --- SIDEBAR (Premium) --- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #020617 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        box-shadow: 20px 0 40px rgba(0,0,0,0.3);
    }
    
    /* Sidebar Content Wrapper */
    [data-testid="stSidebarUserContent"] {
        padding-top: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Reduce sidebar width on desktop if supported, usually fixed by Streamlit */
    .css-17lntkn {
        color: #94a3b8 !important;
    }
    
    /* Sidebar Headers */
    [data-testid="stSidebar"] h5 {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b; /* Muted Slate */
        margin-bottom: 1rem;
        font-weight: 700;
        white-space: nowrap;
    }

    /* --- MAIN LAYOUT & CONTAINER --- */
    .block-container {
        padding-top: 3rem;
        padding-bottom: 8rem; /* Space for fixed chat input */
        max-width: 850px !important; /* Optimal reading width */
    }

    /* --- HEADER (Visual Hierarchy) --- */
    .header-container {
        text-align: center;
        margin-bottom: 3rem;
        animation: fadeIn 0.8s ease-out;
    }
    .header-title {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 50%, #F472B6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .header-subtitle {
        font-size: 1.1rem;
        color: #94a3b8; /* Slate 400 */
        font-weight: 400;
    }

    /* --- CHAT BUBBLES (Premium Feel) --- */
    
    /* Animation for new messages */
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    [data-testid="stChatMessage"] {
        animation: slideIn 0.3s ease-out forwards;
        padding: 1.5rem 0;
    }

    /* Bubble Content Box */
    [data-testid="stChatMessageContent"] {
        padding: 1rem 1.25rem;
        border-radius: 18px;
        font-size: 0.95rem;
        line-height: 1.6;
        width: fit-content !important;
        max-width: 85% !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    
    /* USER MESSAGES (Right Aligned) */
    /* Use :has() to target specific markers injected in Python */
    [data-testid="stChatMessage"]:has(.chat-user-marker) {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessage"]:has(.chat-user-marker) [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        margin-right: 12px;
        text-align: left;
        border-top-right-radius: 4px; /* Tail */
        border: 1px solid #3b82f6;
    }

    /* AI ASSOCIATE MESSAGES (Left Aligned) */
    [data-testid="stChatMessage"]:has(.chat-ai-marker) {
         flex-direction: row;
    }
    [data-testid="stChatMessage"]:has(.chat-ai-marker) [data-testid="stChatMessageContent"] {
        background-color: #1e293b;
        color: #f1f5f9;
        margin-left: 12px;
        border: 1px solid #334155;
        border-top-left-radius: 4px; /* Tail */
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.08);
    }

    /* AVATARS */
    .stChatMessageAvatar {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 1.2rem;
    }

    /* --- INPUT AREA (Glassmorphism & Floating) --- */
    .stChatInput {
        padding-bottom: 1rem;
        max-width: 850px;
        margin: 0 auto;
        border-radius: 20px;
    }

    /* Fixed Input Container */
    .stChatInput > div {
        background: rgba(15, 23, 42, 0.6); /* Semi-transparent Slate 900 */
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 9999px !important; /* Pill Shape Container */
        padding: 6px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    
    /* Text Area (Transparent to show blur) */
    [data-testid="stChatInputTextArea"] {
        background-color: transparent !important;
        color: #f8fafc !important;
        border: none !important; /* Remove individual border */
        border-radius: 9999px !important;
        padding: 0.8rem 1rem !important;
        box-shadow: none !important;
    }
    
    /* Focus State - Glow on Container */
    .stChatInput > div:focus-within {
        border-color: #60A5FA;
        box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.2), 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    
    /* Placeholder */
    [data-testid="stChatInputTextArea"]::placeholder {
        color: #94a3b8;
    }

    /* Send Button - Perfect Center */
    [data-testid="stChatInputSubmitButton"] {
        background-color: rgba(96, 165, 250, 0.1);
        color: #60A5FA !important;
        border: none;
        border-radius: 50%;
        padding: 0.5rem;
        height: 40px;
        width: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 4px;
        transition: all 0.2s ease;
    }
    [data-testid="stChatInputSubmitButton"]:hover {
        background-color: #60A5FA;
        color: white !important;
        box-shadow: 0 4px 12px rgba(96, 165, 250, 0.3);
        transform: scale(1.05);
    }
    
    /* --- SCROLLBARS (Webkit) --- */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #020617; 
    }
    ::-webkit-scrollbar-thumb {
        background: #334155; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #475569; 
    }
    
    /* --- SELECTION COLOR --- */
    ::selection {
        background: rgba(96, 165, 250, 0.3);
        color: #fff;
    }
    
    /* Buttons */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 500;
        font-size: 0.95rem;
        padding: 0.6rem 1rem;
        border: none;
        transition: transform 0.1s, box-shadow 0.2s;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #4F46E5 0%, #3B82F6 100%);
        box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.3);
        color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px 0 rgba(79, 70, 229, 0.4);
    }
    div.stButton > button[kind="secondary"] {
        background-color: #1e293b;
        color: #cbd5e1;
        border: 1px solid #334155;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #334155;
        border-color: #475569;
    }

    /* Status Badges (Glossy Pills) */
    /* Status Badges (Glossy Pills) */
    .status-badge {
        font-size: 0.6rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 9999px;
        margin-bottom: 0.5rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        gap: 6px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(4px);
    }
    
    .status-online {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.2) 100%);
        color: #34d399; /* Emerald 400 */
        border: 1px solid rgba(16, 185, 129, 0.3);
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.15);
    }
    
    .status-offline {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(185, 28, 28, 0.2) 100%);
        color: #fca5a5; /* Red 300 */
        border: 1px solid rgba(239, 68, 68, 0.3);
        box-shadow: 0 0 15px rgba(239, 68, 68, 0.15);
    }
    
    /* Divider */
    hr {
        border-color: #334155;
        opacity: 0.5;
    }
    
    /* Footer Credit */
    .footer-credit {
        position: fixed;
        bottom: 10px;
        right: 20px;
        font-size: 0.7rem;
        color: #475569;
        pointer-events: none;
        z-index: 999;
    }

    /* Mobile Tweaks */
    @media (max-width: 768px) {
        .header-title { font-size: 2rem; }
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        [data-testid="stChatMessageContent"] { max-width: 90% !important; }
    }
</style>
""", unsafe_allow_html=True)

# ---------------- CONTROL PANEL (Sidebar) ----------------
with st.sidebar:
    st.markdown('<div style="margin-bottom: 1.5rem;"></div>', unsafe_allow_html=True) # Spacer
    
    # Status Indicator
    if st.session_state.connected:
        st.markdown('<div class="status-badge status-online">● Connected</div>', unsafe_allow_html=True)
        st.caption(f"Session: `{st.session_state.session_id[:8]}...`") 
    else:
        st.markdown('<div class="status-badge status-offline">○ Disconnected</div>', unsafe_allow_html=True)

    st.markdown("---") 
    
    if not st.session_state.connected:
        st.markdown("##### New Conversation")
        st.caption("Start a new realtime session.")
        if st.button("Start Session", type="primary"):
            sid = str(uuid.uuid4())
            st.session_state.session_id = sid
            st.session_state.messages = []
            st.session_state.summary = None
            st.session_state.connected = True
            ws_url = BACKEND_WS_URL.format(session_id=sid)
            st.session_state.ws = start_ws(ws_url, st.session_state.ws_queue)
            st.rerun()
    else:
        st.markdown("##### Actions")
        if st.button("End Session", type="secondary"):
            if st.session_state.ws:
                st.session_state.ws.close()
            st.session_state.connected = False

            # Fetch summary logic...
            try:
                time.sleep(1)
                r = requests.get(f"{BACKEND_HTTP_URL}/session/{st.session_state.session_id}/summary", timeout=2)
                st.session_state.summary = r.json().get("summary") if r.status_code == 200 else "Summary unavailable"
            except:
                st.session_state.summary = "Summary unavailable"

            st.rerun()

# ---------------- MAIN CHAT AREA ----------------

# Header (Centered, Visually Dominant)
st.markdown("""
<div class="header-container">
    <div class="header-title">AI Assistant Pro</div>
    <div class="header-subtitle">Realtime • Intelligent • Connected</div>
</div>
""", unsafe_allow_html=True)

# Footer
st.markdown('<div class="footer-credit">Built with Streamlit & FastAPI</div>', unsafe_allow_html=True)

# Chat Display
for m in st.session_state.messages:
    # Icons: 🧠 for AI, 👤 for User
    avatar_char = "👤" if m["role"] == "user" else "🧠"
    with st.chat_message(m["role"], avatar=avatar_char):
        marker_class = "chat-user-marker" if m["role"] == "user" else "chat-ai-marker"
        # Merge marker and content to prevent extra widget spacing
        full_content = f'<div class="{marker_class}" style="display:none;"></div>{m["content"]}'
        st.markdown(full_content, unsafe_allow_html=True)

# Summary Display (Elegant Card)
if st.session_state.summary:
    st.markdown("---")
    st.markdown("### 📝 Session Summary")
    st.info(st.session_state.summary, icon="✅")

# Input Area
if st.session_state.connected:
    if prompt := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        if st.session_state.ws:
            st.session_state.ws.send(prompt)
            st.session_state.waiting = True
        st.rerun()

# ---------------- STREAMING LOOP ----------------
if st.session_state.waiting:
    with st.chat_message("assistant", avatar="🧠"):
        # AI Marker class
        marker_html = '<div class="chat-ai-marker" style="display:none;"></div>'
        
        placeholder = st.empty()
        
        # Animated "Thinking" state - Merge marker
        placeholder.markdown(f"""
            {marker_html}
            <div style='color: #94a3b8; font-style: italic; animation: pulse 1.5s infinite;'>
                Thinking...
            </div>
            <style>
                @keyframes pulse {{ 0% {{ opacity: 0.4; }} 50% {{ opacity: 1; }} 100% {{ opacity: 0.4; }} }}
            </style>
        """, unsafe_allow_html=True)
        
        full = ""
        last = time.time()
        start_wait = time.time()
        
        while True:
            try:
                token = st.session_state.ws_queue.get(timeout=0.1)
                full += token
                # Render marker + text in one go
                placeholder.markdown(marker_html + full + "▌", unsafe_allow_html=True)
                last = time.time()
            except queue.Empty:
                now = time.time()
                # 15s Timeout for first token
                if not full:
                    if now - start_wait > 15:
                        placeholder.error("AI response timed out.")
                        break
                # 2s Timeout for gaps
                elif now - last > 2:
                    break

        # Final render
        placeholder.markdown(marker_html + full, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": full})
        st.session_state.waiting = False
        st.rerun()

# ---------------- HEARTBEAT ----------------
if st.session_state.connected:
    st_autorefresh(interval=1000, key="heartbeat")
