import re

from .classifier import classify_query
from .handlers import *
from .db import fetch_one
from .sentiment import analyze_sentiment

# -------------------------------
# HELPERS
# -------------------------------
def is_english_text(text: str) -> bool:
    """
    Allows only English letters, digits and spaces
    """
    return bool(re.fullmatch(r"[A-Za-z0-9 ]+", text.strip()))

def extract_id(text: str):
    text = text.upper()

    digit_map = {
        "ZERO": "0", "जीरो": "0", "शून्य": "0",
        "ONE": "1", "एक": "1",
        "TWO": "2", "दो": "2",
        "THREE": "3", "तीन": "3",
        "FOUR": "4", "चार": "4",
        "FIVE": "5", "पांच": "5",
        "SIX": "6", "छह": "6",
        "SEVEN": "7", "सात": "7",
        "EIGHT": "8", "आठ": "8",
        "NINE": "9", "नौ": "9"
    }

    for k, v in digit_map.items():
        text = text.replace(k, v)

    # 🔥 YAHI EDIT HAI (spaces + dots + hyphen sab remove)
    text = re.sub(r"[^A-Z0-9]", "", text)

    m = re.search(r"[A-Z]{2,5}\d{2,6}", text)
    return m.group() if m else None

import re

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


# =====================================================
# YES / NO WORD BANK (50+ each)
# =====================================================

YES_EXACT = {
    # ---------- Hinglish ----------
    "haan", "ha", "haan ji", "haanji", "haan bhai",
    "ha ji", "ha bhai", "haan sir", "haan madam",
    "bilkul", "bilkul haan", "theek hai", "thik hai",
    "theek", "thik", "sahi", "sahi hai",

    # ---------- English ----------
    "yes", "yeah", "yup", "yep", "ya", "yah",
    "ok", "okay", "ok ji", "ok bhai",
    "sure", "sure ji", "alright", "right",
    "correct", "absolutely",

    # ---------- Pure Hindi ----------
    "हाँ", "हाँ जी", "जी हाँ", "बिल्कुल",
    "ठीक", "ठीक है", "सही", "सही है",

    # ---------- Casual / Indian ----------
    "haan haan", "haa", "haan ha", "done",
    "kar do", "kar dijiye"
}

NO_EXACT = {
    # ---------- Hinglish ----------
    "nahi", "nahin", "nahi ji", "nahi bhai",
    "na", "na ji", "na bhai",
    "bilkul nahi", "galat", "galat hai",

    # ---------- English ----------
    "no", "nope", "nah", "not really",
    "never", "dont", "don't",

    # ---------- Pure Hindi ----------
    "नहीं", "नही", "नहीं जी", "ना",
    "गलत", "गलत है",

    # ---------- Casual / Indian ----------
    "matlab nahi", "abhi nahi",
    "cancel", "chhod do", "rehne do"
}


# ---------- PARTIAL / CUT SPEECH PREFIXES ----------
YES_PREFIXES = (
    "ha", "han", "haa", "he", "ye", "ya",
    "ok", "al", "ri", "su", "ji"
)

NO_PREFIXES = (
    "na", "nah", "no", "ni", "ne", "ma"
)


# =====================================================
# DETECTION FUNCTIONS
# =====================================================

def is_yes(text: str) -> bool:
    t = normalize_text(text)

    # 1️⃣ Exact match
    if t in YES_EXACT:
        return True

    # 2️⃣ Prefix match (cut / noisy speech)
    if any(t.startswith(p) for p in YES_PREFIXES):
        return True

    # 3️⃣ Ultra-short hint (audio cut)
    if len(t) <= 2 and t in {"h", "y", "ok"}:
        return True

    return False


def is_no(text: str) -> bool:
    t = normalize_text(text)

    # 1️⃣ Exact match
    if t in NO_EXACT:
        return True

    # 2️⃣ Prefix match
    if any(t.startswith(p) for p in NO_PREFIXES):
        return True

    # 3️⃣ Ultra-short hint
    if len(t) <= 2 and t in {"n"}:
        return True

    return False





def wants_reset(text):
    return "forget" in text.lower() or "reset" in text.lower()


# -------------------------------
# ESCALATION
# -------------------------------

def escalate(session, reason):
    summary = {
        "driver_id": session.get("driver_id"),
        "name": session.get("name"),
        "intent": session.get("intent"),
        "last_state": session.get("state"),
        "last_user_message": session.get("last_message"),
        "sentiment": session.get("last_sentiment"),
        "severity": session.get("last_severity"),
        "reason": reason
    }
    session.clear()

    return (
        "Main aapko human agent se connect kar rahi hoon.\n\n"
        "📋 Agent Summary:\n"
        f"{summary}"
    )


# -------------------------------
# MAIN ORCHESTRATOR
# -------------------------------

def handle_input(user_text: str, session: dict):

    session["last_message"] = user_text

    # ---------- RESET ----------
    if wants_reset(user_text):
        session.clear()
        session.update({
            "state": "ASK_DRIVER_ID",
            "retry": 0,
            "intent_retry": 0,
            "sentiment_mode": False,
            "abuse_warned": False,
            "angry_count": 0
        })
        return "Theek hai. Hello, driver ID batayein."

    # ---------- INIT ----------
    if "state" not in session:
        session.update({
            "state": "ASK_DRIVER_ID",
            "retry": 0,
            "intent_retry": 0,
            "sentiment_mode": False,
            "abuse_warned": False,
            "angry_count": 0
        })
        return "Hello, driver ID batayein."

    # ---------- ASK DRIVER ID ----------
    if session["state"] == "ASK_DRIVER_ID":
        driver_id = extract_id(user_text)
        session["retry"] += 1

        row = fetch_one(
            "SELECT name FROM drivers WHERE driver_id=%s",
            (driver_id,)
        ) if driver_id else None

        if not row:
            if session["retry"] >= 3:
                return escalate(session, "Driver ID verification failed")
            return "Driver ID sahi se batayein please."

        session["driver_id"] = driver_id
        session["expected_name"] = row[0]
        session["state"] = "CONFIRM_DRIVER_ID"
        return f"Aapne driver ID {driver_id} bataya hai. Kya yeh sahi hai? Haan ya na."


    # ---------- CONFIRM DRIVER ID ----------
    if session["state"] == "CONFIRM_DRIVER_ID":
        if is_yes(user_text):
            session["state"] = "ASK_NAME"
            session["retry"] = 0
            return "Dhanyavaad. Ab apna naam batayein."
        if is_no(user_text):
            return escalate(session, "Driver ID not confirmed")
        return "Kripya sirf haan ya na mein jawab dein."

    # ---------- ASK NAME ----------
    if session["state"] == "ASK_NAME":
        session["retry"] += 1
        if user_text.strip().lower() != session["expected_name"].lower():
            if session["retry"] >= 3:
                return escalate(session, "Name verification failed")
            return "Naam match nahi hua. Dobara batayein."

        session["name"] = user_text.strip()
        session["state"] = "CONFIRM_NAME"
        return f"Aapne apna naam {session['name']} bataya hai. Kya yeh sahi hai? Haan ya na."


    # ---------- CONFIRM NAME ----------
    if session["state"] == "CONFIRM_NAME":
        if is_yes(user_text):
            session["state"] = "ASK_PROBLEM"
            session["intent_retry"] = 0
            return "Dhanyavaad. Aapki kya samasya solve kar sakti hoon?"
        if is_no(user_text):
            return escalate(session, "Name not confirmed")
        return "Kripya sirf haan ya na mein jawab dein."

    # ---------- ASK PROBLEM ----------
    if session["state"] == "ASK_PROBLEM":
        session["lat"] = 28.4595
        session["lon"] = 77.0266
        session["intent_retry"] += 1
        session["sentiment_mode"] = True

        sentiment = analyze_sentiment(user_text)
        session["last_sentiment"] = sentiment.get("sentiment")
        session["last_severity"] = sentiment.get("severity")

        if sentiment.get("abusive"):
            if not session.get("abuse_warned"):
                session["abuse_warned"] = True
                return "⚠️ Kripya shant aur sammaan poorvak bhasha ka prayog karein."
            return escalate(session, "Repeated abusive language")

        if sentiment.get("sentiment") == "angry":
            session["angry_count"] = session.get("angry_count", 0) + 1
            if session["angry_count"] >= 3:
                return escalate(session, "Persistent anger")
        else:
            session["angry_count"] = 0

        result = classify_query(user_text)
        intent = result.get("intent")
        confidence = result.get("confidence", 0)

        if confidence < 0.7 or intent == "UNKNOWN":
            if session["intent_retry"] >= 3:
                return escalate(session, "Intent not detected")
            return "Main samajh nahi paayi. Thoda clear batayein."

        session["intent"] = intent

        if intent in ["BATTERY_WIRE_MELTED", "BATTERY_DRAIN_FAST", "STATION_NO_BATTERY"]:
            session["state"] = "ASK_ENTITY"
            return "Kripya required ID batayein."

        response = route(intent, session["driver_id"], session=session)
        session["state"] = "ASK_MORE"
        return response + "\n\nKya aapki koi aur pareshani hai? (haan / na)"

    # ---------- ASK ENTITY ----------
    if session["state"] == "ASK_ENTITY":
        entity = extract_id(user_text)
        if not entity:
            return "ID sahi format mein batayein please."

        response = route(session["intent"], session["driver_id"], entity=entity, session=session)
        session["state"] = "ASK_MORE"
        return response + "\n\nKya aapki koi aur pareshani hai? (haan / na)"

    # ---------- ASK MORE ----------
    if session["state"] == "ASK_MORE":
        if is_yes(user_text):
            session["state"] = "ASK_PROBLEM"
            session["intent_retry"] = 0
            return "Theek hai. Aapki kya samasya hai?"
        if is_no(user_text):
            session.clear()
            return "Dhanyavaad. Safe ride!"
        return "Kripya sirf haan ya na mein jawab dein."

    return "Dhanyavaad. Safe ride!"


# -------------------------------
# ROUTER (SIGNATURE FIXED ONLY)
# -------------------------------

def route(intent, driver_id, entity=None, session=None):

    if intent == "BATTERY_WIRE_MELTED":
        return handle_battery_wire_melted(entity)

    if intent == "BATTERY_DRAIN_FAST":
        return handle_battery_drain_fast(entity)

    if intent == "BATTERY_STOLEN":
        return handle_battery_stolen(entity)

    if intent == "SWAP_TODAY_COUNT":
        return handle_swap_today_count(driver_id)

    if intent == "SWAP_LIMIT_DISPUTE":
        return handle_swap_limit_dispute(driver_id)

    if intent == "SWAP_CHARGED_WRONG":
        return handle_swap_charged_wrong(driver_id)

    if intent == "STATION_NO_BATTERY":
        return handle_station_no_battery(entity)

    if intent == "NEAREST_STATION":
        return handle_nearest_station(
            session.get("lat"),
            session.get("lon")
        )

    if intent == "DSK_NEAREST":
        return handle_nearest_dsk(session.get("lat"),
        session.get("lon"))

    if intent == "ACCOUNT_ACTIVATE":
        return handle_account_activate()

    if intent == "ACCOUNT_DEACTIVATE":
        return handle_account_deactivate()

    if intent == "SUBSCRIPTION_VALIDITY":
        return handle_subscription_validity(driver_id)

    if intent == "SUBSCRIPTION_RENEWAL":
        return handle_subscription_renewal()

    if intent == "SUBSCRIPTION_PRICING":
        return handle_subscription_pricing()

    if intent == "LEAVE_INFO":
        return handle_leave_info()

    if intent == "LEAVE_STATUS":
        return handle_leave_status(driver_id)

    if intent == "LEAVE_PENALTY_INFO":
        return handle_leave_penalty_info()

    if intent == "LEAVE_PENALTY_CURRENT":
        return handle_leave_penalty_current(driver_id)

    if intent == "LEAVE_PENALTY_WAIVER_REQUEST":
        return handle_leave_penalty_waiver_request()

    return "Is request ke liye abhi support available nahi hai."

# import re

# from intent_bot.classifier import classify_query
# from intent_bot.handlers import *
# from intent_bot.db import fetch_one
# from intent_bot.sentiment import analyze_sentiment

# # -------------------------------
# # HELPERS
# # -------------------------------

# def extract_id(text):
#     m = re.search(r"[A-Z0-9]{3,}", text.upper())
#     return m.group() if m else None

# def is_yes(text):
#     return text.lower().strip() in ["haan", "ha", "yes", "ji haan"]

# def is_no(text):
#     return text.lower().strip() in ["nahi", "na", "no"]

# def wants_reset(text):
#     return "forget" in text.lower() or "reset" in text.lower()


# # -------------------------------
# # ESCALATION
# # -------------------------------

# def escalate(session, reason):
#     summary = {
#         "driver_id": session.get("driver_id"),
#         "name": session.get("name"),
#         "intent": session.get("intent"),
#         "last_state": session.get("state"),
#         "last_user_message": session.get("last_message"),
#         "sentiment": session.get("last_sentiment"),
#         "severity": session.get("last_severity"),
#         "reason": reason
#     }
#     session.clear()

#     return (
#         "Main aapko human agent se connect kar rahi hoon.\n\n"
#         "📋 Agent Summary:\n"
#         f"{summary}"
#     )


# # -------------------------------
# # MAIN ORCHESTRATOR
# # -------------------------------

# def handle_input(user_text: str, session: dict):

#     session["last_message"] = user_text

#     # ---------- RESET ----------
#     if wants_reset(user_text):
#         session.clear()
#         session.update({
#             "state": "ASK_DRIVER_ID",
#             "retry": 0,
#             "intent_retry": 0,
#             "sentiment_mode": False,
#             "abuse_warned": False,
#             "angry_count": 0
#         })
#         return "Theek hai. Hello, driver ID batayein."

#     # ---------- INIT ----------
#     if "state" not in session:
#         session.update({
#             "state": "ASK_DRIVER_ID",
#             "retry": 0,
#             "intent_retry": 0,
#             "sentiment_mode": False,
#             "abuse_warned": False,
#             "angry_count": 0
#         })
#         return "Hello, driver ID batayein."

#     # ---------- ASK DRIVER ID ----------
#     if session["state"] == "ASK_DRIVER_ID":
#         driver_id = extract_id(user_text)
#         session["retry"] += 1

#         row = fetch_one(
#             "SELECT name FROM drivers WHERE driver_id=%s",
#             (driver_id,)
#         ) if driver_id else None

#         if not row:
#             if session["retry"] >= 3:
#                 return escalate(session, "Driver ID verification failed")
#             return "Driver ID sahi se batayein please."

#         session["driver_id"] = driver_id
#         session["expected_name"] = row[0]
#         session["state"] = "CONFIRM_DRIVER_ID"
#         return f"Aapne driver ID **{driver_id}** bataya hai. Kya yeh sahi hai? (haan / na)"

#     # ---------- CONFIRM DRIVER ID ----------
#     if session["state"] == "CONFIRM_DRIVER_ID":
#         if is_yes(user_text):
#             session["state"] = "ASK_NAME"
#             session["retry"] = 0
#             return "Dhanyavaad. Ab apna naam batayein."
#         if is_no(user_text):
#             return escalate(session, "Driver ID not confirmed")
#         return "Kripya sirf haan ya na mein jawab dein."

#     # ---------- ASK NAME ----------
#     if session["state"] == "ASK_NAME":
#         session["retry"] += 1
#         if user_text.strip().lower() != session["expected_name"].lower():
#             if session["retry"] >= 3:
#                 return escalate(session, "Name verification failed")
#             return "Naam match nahi hua. Dobara batayein."

#         session["name"] = user_text.strip()
#         session["state"] = "CONFIRM_NAME"
#         return f"Aapne apna naam **{session['name']}** bataya hai. Kya yeh sahi hai? (haan / na)"

#     # ---------- CONFIRM NAME ----------
#     if session["state"] == "CONFIRM_NAME":
#         if is_yes(user_text):
#             session["state"] = "ASK_PROBLEM"
#             session["intent_retry"] = 0
#             return "Dhanyavaad. Aapki kya samasya solve kar sakti hoon?"
#         if is_no(user_text):
#             return escalate(session, "Name not confirmed")
#         return "Kripya sirf haan ya na mein jawab dein."

#     # ---------- ASK PROBLEM ----------
#     if session["state"] == "ASK_PROBLEM":
#         session["lat"] = 28.4595
#         session["lon"] = 77.0266
#         session["intent_retry"] += 1
#         session["sentiment_mode"] = True

#         sentiment = analyze_sentiment(user_text)
#         session["last_sentiment"] = sentiment.get("sentiment")
#         session["last_severity"] = sentiment.get("severity")

#         if sentiment.get("abusive"):
#             if not session.get("abuse_warned"):
#                 session["abuse_warned"] = True
#                 return "⚠️ Kripya shant aur sammaan poorvak bhasha ka prayog karein."
#             return escalate(session, "Repeated abusive language")

#         if sentiment.get("sentiment") == "angry":
#             session["angry_count"] += 1
#             if session["angry_count"] >= 3:
#                 return escalate(session, "Persistent anger")
#         else:
#             session["angry_count"] = 0

#         result = classify_query(user_text)
#         intent = result.get("intent")
#         confidence = result.get("confidence", 0)

#         if confidence < 0.7 or intent == "UNKNOWN":
#             if session["intent_retry"] >= 3:
#                 return escalate(session, "Intent not detected")
#             return "Main samajh nahi paayi. Thoda clear batayein."

#         session["intent"] = intent

#         if intent in ["BATTERY_WIRE_MELTED", "BATTERY_DRAIN_FAST", "STATION_NO_BATTERY"]:
#             session["state"] = "ASK_ENTITY"
#             return "Kripya required ID batayein."

#         response = route(intent, session["driver_id"], session)
#         session["state"] = "ASK_MORE"
#         return response + "\n\nKya aapki koi aur pareshani hai? (haan / na)"

#     # ---------- ASK ENTITY ----------
#     if session["state"] == "ASK_ENTITY":
#         entity = extract_id(user_text)
#         if not entity:
#             return "ID sahi format mein batayein please."

#         response = route(session["intent"], session["driver_id"], session, entity)
#         session["state"] = "ASK_MORE"
#         return response + "\n\nKya aapki koi aur pareshani hai? (haan / na)"

#     # ---------- ASK MORE ----------
#     if session["state"] == "ASK_MORE":
#         if is_yes(user_text):
#             session["state"] = "ASK_PROBLEM"
#             session["intent_retry"] = 0
#             return "Theek hai. Aapki kya samasya hai?"
#         if is_no(user_text):
#             session.clear()
#             return "Dhanyavaad. Safe ride!"
#         return "Kripya sirf haan ya na mein jawab dein."

#     return "Dhanyavaad. Safe ride!"


# # -------------------------------
# # ROUTER (FIXED)
# # -------------------------------

# def route(intent, driver_id, session, entity=None):

#     if intent == "BATTERY_WIRE_MELTED":
#         return handle_battery_wire_melted(entity)

#     if intent == "BATTERY_DRAIN_FAST":
#         return handle_battery_drain_fast(entity)

#     if intent == "BATTERY_STOLEN":
#         return handle_battery_stolen(entity)

#     if intent == "SWAP_TODAY_COUNT":
#         return handle_swap_today_count(driver_id)

#     if intent == "SWAP_LIMIT_DISPUTE":
#         return handle_swap_limit_dispute(driver_id)

#     if intent == "SWAP_CHARGED_WRONG":
#         return handle_swap_charged_wrong(driver_id)

#     if intent == "STATION_NO_BATTERY":
#         return handle_station_no_battery(entity)

#     if intent == "NEAREST_STATION":
#         return handle_nearest_station(
#             session.get("lat"),
#             session.get("lon")
#         )

#     if intent == "DSK_NEAREST":
#         return handle_nearest_dsk()

#     if intent == "ACCOUNT_ACTIVATE":
#         return handle_account_activate()

#     if intent == "ACCOUNT_DEACTIVATE":
#         return handle_account_deactivate()

#     if intent == "SUBSCRIPTION_VALIDITY":
#         return handle_subscription_validity(driver_id)

#     if intent == "SUBSCRIPTION_RENEWAL":
#         return handle_subscription_renewal()

#     if intent == "SUBSCRIPTION_PRICING":
#         return handle_subscription_pricing()

#     if intent == "LEAVE_INFO":
#         return handle_leave_info()

#     if intent == "LEAVE_STATUS":
#         return handle_leave_status(driver_id)

#     if intent == "LEAVE_PENALTY_INFO":
#         return handle_leave_penalty_info()

#     if intent == "LEAVE_PENALTY_CURRENT":
#         return handle_leave_penalty_current(driver_id)

#     if intent == "LEAVE_PENALTY_WAIVER_REQUEST":
#         return handle_leave_penalty_waiver_request()

#     return "Is request ke liye abhi support available nahi hai."
