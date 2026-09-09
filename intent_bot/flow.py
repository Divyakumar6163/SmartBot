import re
from classifier import classify_query

# -----------------------------------
# REQUIRED ENTITIES CONFIG
# -----------------------------------
REQUIRED_ENTITIES = {
    "BATTERY_WIRE_MELTED": ["battery_id"],
    "BATTERY_DRAIN_FAST": ["battery_id"],
    "BATTERY_STOLEN": ["battery_id"],
    "STATION_NO_BATTERY": ["station_id"]
}

FOLLOWUP_QUESTIONS = {
    "battery_id": "Battery ID batayein please.",
    "station_id": "Station ID batayein please."
}

# -----------------------------------
# HELPERS
# -----------------------------------
def extract_id(text: str):
    """
    Extracts alphanumeric ID from user input
    """
    match = re.search(r"[A-Z0-9]{4,}", text.upper())
    return match.group() if match else None


# -----------------------------------
# FINAL BUSINESS FUNCTIONS (STUBS)
# -----------------------------------
def call_final_function(intent: str, entities: dict):
    if intent == "BATTERY_WIRE_MELTED":
        return f"✅ Wire melted issue logged for Battery {entities['battery_id']}"

    if intent == "BATTERY_DRAIN_FAST":
        return f"✅ Fast drain issue logged for Battery {entities['battery_id']}"

    if intent == "BATTERY_STOLEN":
        return f"🚨 Battery {entities['battery_id']} theft escalated to support"

    if intent == "STATION_NO_BATTERY":
        return f"✅ Station {entities['station_id']} marked as no-battery"

    return "✅ Request processed successfully"


# -----------------------------------
# MAIN HANDLER
# -----------------------------------
def handle_user_input(user_text: str, session_state: dict):
    """
    Handles full flow:
    - intent detection
    - entity follow-up
    - final function call
    """

    # -------------------------------
    # CASE 1: FOLLOW-UP TURN
    # -------------------------------
    if session_state.get("pending_intent"):
        intent = session_state["pending_intent"]
        required_entity = REQUIRED_ENTITIES[intent][0]

        entity_value = extract_id(user_text)

        if not entity_value:
            # Still invalid → ask again
            return FOLLOWUP_QUESTIONS[required_entity]

        # Entity captured
        entities = {required_entity: entity_value}

        # Clear session
        session_state["pending_intent"] = None
        session_state["pending_entities"] = {}

        return call_final_function(intent, entities)

    # -------------------------------
    # CASE 2: NEW USER QUERY
    # -------------------------------
    result = classify_query(user_text)

    intent = result.get("intent")
    confidence = result.get("confidence", 0.0)

    # Normalize entities (remove empty values)
    entities = {
        k: v for k, v in result.get("entities", {}).items() if v
    }

    if confidence < 0.7:
        return "Thoda clear bataiye please."

    # -------------------------------
    # CHECK REQUIRED ENTITIES
    # -------------------------------
    required = REQUIRED_ENTITIES.get(intent, [])

    for r in required:
        # 🔴 IMPORTANT FIX: empty entity treated as missing
        if r not in entities or not entities.get(r):
            session_state["pending_intent"] = intent
            session_state["pending_entities"] = {}
            return FOLLOWUP_QUESTIONS[r]

    # -------------------------------
    # ALL GOOD → FINAL CALL
    # -------------------------------
    return call_final_function(intent, entities)
