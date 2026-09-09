from intent_bot.db import fetch_one, fetch_all
from datetime import datetime, timedelta
from intent_bot.services.nearest_dsk import get_nearest_active_dsk


# =====================================================
# 🔋 BATTERY RELATED
# =====================================================

def handle_battery_wire_melted(battery_id):
    return (
        "Aapki problem note kar li gayi hai. "
        "Hamari team aapse contact karegi. "
        "Tab tak please battery use na karein."
    )


def handle_battery_drain_fast(battery_id):
    row = fetch_one(
        "SELECT last_swap_time FROM batteries WHERE battery_id=%s",
        (battery_id,)
    )

    if not row:
        return "Battery ID galat hai."

    last_swap = row[0]

    if datetime.now() - last_swap <= timedelta(hours=2):
        return (
            "Aapki problem note kar li gayi hai. "
            "Agla swap karte waqt aapko charge waive off milega."
        )

    return (
        "Battery 2 ghante se zyada use ho chuki hai. "
        "Kripya nearest station par jaakar swap karein. "
        "Is case mein waiver apply nahi hoga."
    )


def handle_battery_stolen(battery_id):
    return "Main aapko turant human support agent se connect kar raha hoon."


# =====================================================
# 🔄 SWAP RELATED
# =====================================================

def handle_swap_today_count(driver_id):
    row = fetch_one(
        """
        SELECT COUNT(*)
        FROM swaps
        WHERE driver_id=%s AND DATE(swap_time)=CURRENT_DATE
        """,
        (driver_id,)
    )

    return f"Aaj aapne total {row[0]} swap kiye hain."


def handle_swap_limit_dispute(driver_id):
    rows = fetch_all(
        """
        SELECT swap_time, station_id
        FROM swaps
        WHERE driver_id=%s AND DATE(swap_time)=CURRENT_DATE
        ORDER BY swap_time
        """,
        (driver_id,)
    )

    if not rows:
        return "Aaj koi swap record nahi mila."

    msg = "Aaj ke swaps ka detail:\n"
    for t, s in rows:
        msg += f"- {t.strftime('%H:%M')} par {s} station\n"

    return msg


def handle_swap_charged_wrong(driver_id):
    row = fetch_one(
        """
        SELECT swap_time, station_id, price_tier, amount_charged
        FROM swaps
        WHERE driver_id=%s
        ORDER BY swap_time DESC
        LIMIT 1
        """,
        (driver_id,)
    )

    if not row:
        return "Koi recent swap nahi mila."

    t, s, p, a = row
    return (
        f"Aapka last swap {t.strftime('%H:%M')} par {s} station par hua tha. "
        f"Is swap par {p} charge laga tha (₹{a})."
    )


# =====================================================
# 📍 STATION / LOCATION
# =====================================================

def handle_station_no_battery(station_id):
    row = fetch_one(
        """
        SELECT name
        FROM stations
        WHERE battery_available_cnt > 0
        ORDER BY battery_available_cnt DESC
        LIMIT 1
        """
    )

    if not row:
        return "Abhi kisi station par battery available nahi hai."

    return (
        "Aapki problem note kar li gayi hai. "
        f"Next nearest station hai: {row[0]}"
    )


from intent_bot.services.nearest_station import get_nearest_station

def handle_nearest_station(driver_lat, driver_lon):

    if not driver_lat or not driver_lon:
        return "Nearest station batane ke liye location allow karein."

    result = get_nearest_station(driver_lat, driver_lon)

    if not result:
        return "Abhi kisi station par battery available nahi hai."

    return (
        f"Nearest station {result['distance_km']} km door hai. "
        f"Wahan {result['battery_count']} battery available hain."
    )



def handle_nearest_dsk(lat, lon):
    result = get_nearest_active_dsk(lat, lon)

    if not result:
        return "Koi active DSK available nahi hai."

    return (
        f"Nearest DSK {result['station_id']} hai. "
        f"Distance approx {result['distance_km']} km hai "
        f"aur wahan {result['available_batteries']} batteries available hain."
    )



# =====================================================
# 👤 ACCOUNT
# =====================================================

def handle_account_activate():
    return "Aapka account activation request note kar liya gaya hai."


def handle_account_deactivate():
    return "Aapka account deactivation request note kar liya gaya hai."


# =====================================================
# 💳 SUBSCRIPTION
# =====================================================

def handle_subscription_validity(driver_id):
    row = fetch_one(
        """
        SELECT valid_till
        FROM subscriptions
        WHERE driver_id=%s AND status='active'
        """,
        (driver_id,)
    )

    if not row:
        return "Aapki koi active subscription nahi hai."

    return f"Aapki subscription {row[0]} tak valid hai."


def handle_subscription_renewal():
    return "Subscription renewal request note kar li gayi hai."


def handle_subscription_pricing():
    return (
        "Subscription plans:\n"
        "• Basic – ₹299\n"
        "• Standard – ₹499\n"
        "• Premium – ₹699"
    )


# =====================================================
# 🏖️ LEAVE / PENALTY
# =====================================================

def handle_leave_info():
    return (
        "Leave rules:\n"
        "• Limited paid leaves allowed\n"
        "• Unauthorized leave par penalty lag sakti hai"
    )


def handle_leave_status(driver_id):
    row = fetch_one(
        """
        SELECT COUNT(*)
        FROM leaves
        WHERE driver_id=%s AND status='approved'
        """,
        (driver_id,)
    )

    return f"Aapne ab tak {row[0]} approved leaves li hain."


def handle_leave_penalty_info():
    return (
        "Penalty leave duration aur approval par depend karti hai. "
        "Unauthorized leave par penalty lag sakti hai."
    )


def handle_leave_penalty_current(driver_id):
    row = fetch_one(
        """
        SELECT SUM(amount)
        FROM penalties
        WHERE driver_id=%s AND status='unpaid'
        """,
        (driver_id,)
    )

    amount = row[0] or 0
    return f"Aapki current unpaid penalty ₹{amount} hai."


def handle_leave_penalty_waiver_request():
    return (
        "Aapki penalty waiver request note kar li gayi hai. "
        "Team is par review karegi."
    )
