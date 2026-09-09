import sys
import os
import logging
import tempfile
import subprocess
import base64
import re

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import soundfile as sf
import noisereduce as nr
from openai import OpenAI

# =====================================================
# PATH SETUP
# =====================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("PROJECT_ROOT added to sys.path:", PROJECT_ROOT)

from intent_bot.orchestrator import handle_input

# =====================================================
# SESSION STORE (TEMP)
# =====================================================
SESSIONS = {}

def get_session(session_id: str):
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {}
    return SESSIONS[session_id]

# =====================================================
# TTS SANITIZER  ✅ IMPORTANT
# =====================================================
def sanitize_for_tts(text: str) -> str:
    """
    Remove markdown / symbols that TTS skips or misreads
    """
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"[📋⚠️🔥]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================
# OPENAI CLIENT
# =====================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================
# FASTAPI APP
# =====================================================
app = FastAPI(title="Hindi Speech-to-Speech API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# CONSTANTS
# =====================================================
MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_AUDIO_FORMATS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}
MIN_TEXT_LENGTH = 2

ENGLISH_ONLY_STATES = {
    "ASK_DRIVER_ID",
    "ASK_NAME",
    "ASK_ENTITY"
}

# =====================================================
# HELPERS
# =====================================================
def cleanup_files(*paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

def detect_language_context(text: str) -> str:
    has_hindi = any('\u0900' <= c <= '\u097F' for c in text)
    has_english = any('a' <= c.lower() <= 'z' for c in text)

    if has_hindi and has_english:
        return "hi-en"
    elif has_hindi:
        return "hi"
    return "en"

def select_tts_voice(lang: str) -> str:
    return "nova" if lang == "en" else "alloy"

# =====================================================
# HEALTH
# =====================================================
@app.get("/health")
def health():
    return {"status": "ok"}

# =====================================================
# MAIN ENDPOINT
# =====================================================
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    webm_path = wav_path = clean_wav_path = None

    try:
        # -------------------------------
        # FILE VALIDATION
        # -------------------------------
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_AUDIO_FORMATS:
            raise HTTPException(400, "Unsupported audio format")

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            data = await file.read()
            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(413, "File too large")
            f.write(data)
            webm_path = f.name

        # -------------------------------
        # CONVERT TO WAV
        # -------------------------------
        wav_path = webm_path.replace(ext, ".wav")
        if ext != ".wav":
            subprocess.run(
                ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path],
                check=True
            )
        else:
            wav_path = webm_path

        # -------------------------------
        # NOISE REDUCTION
        # -------------------------------
        audio, rate = sf.read(wav_path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        clean_audio = nr.reduce_noise(y=audio, sr=rate)
        clean_wav_path = wav_path.replace(".wav", "_clean.wav")
        sf.write(clean_wav_path, clean_audio, rate)

        # -------------------------------
        # SESSION + STATE
        # -------------------------------
        session_id = "demo-driver"
        session = get_session(session_id)
        current_state = session.get("state")

        # -------------------------------
        # STT LANGUAGE DECISION
        # -------------------------------
        stt_language = "en" if current_state in ENGLISH_ONLY_STATES else "hi"
        logger.info(f"STT language = {stt_language} (state={current_state})")

        # -------------------------------
        # SPEECH TO TEXT
        # -------------------------------
        with open(clean_wav_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=stt_language,
                response_format="text"
            )

        user_text = transcript.strip()
        logger.info(f"User said: {user_text}")

        if len(user_text) < MIN_TEXT_LENGTH:
            return {
                "text": "सुनाई नहीं दिया, कृपया फिर से बोलें।",
                "audio": None
            }

        # -------------------------------
        # BOT LOGIC
        # -------------------------------
        bot_text = handle_input(user_text, session)
        logger.info(f"Bot reply (raw): {bot_text}")

        # -------------------------------
        # 🔥 SANITIZE FOR TTS (KEY FIX)
        # -------------------------------
        clean_bot_text = sanitize_for_tts(bot_text)
        logger.info(f"Bot reply (tts-safe): {clean_bot_text}")

        # -------------------------------
        # TEXT TO SPEECH
        # -------------------------------
        lang_ctx = detect_language_context(clean_bot_text)
        voice = select_tts_voice(lang_ctx)

        tts = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=clean_bot_text,
            response_format="mp3"
        )

        audio_bytes = b"".join(tts.iter_bytes())
        audio_b64 = base64.b64encode(audio_bytes).decode()

        return {
            "text": clean_bot_text,
            "audio": audio_b64,
            "language": lang_ctx,
            "voice_used": voice,
            "success": True
        }

    except Exception as e:
        logger.exception("Processing failed")
        raise HTTPException(500, str(e))

    finally:
        cleanup_files(webm_path, wav_path, clean_wav_path)

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
