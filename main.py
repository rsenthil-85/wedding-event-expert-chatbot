from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import os
import requests
from datetime import datetime

app = FastAPI()

# Allow frontend (browser) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mount (for logo etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

# Simple in-memory session store
sessions = {}

# Google Sheet webhook
GOOGLE_SHEET_WEBHOOK = os.getenv("GOOGLE_SHEET_WEBHOOK")

# WhatsApp recipients: format "+91xxxxxxx:APIKEY1,+91yyyyyyy:APIKEY2"
WHATSAPP_RECIPIENTS_RAW = os.getenv("WHATSAPP_RECIPIENTS", "")


class Message(BaseModel):
    session_id: str
    text: str


# ---------- GOOGLE SHEET LOGGING ----------

def log_booking_to_sheet(name: str, event_type: str, location: str, when_text: str):
    """
    Send booking data to Google Sheet via Apps Script Webhook.

    Using existing keys: city, slot (for backward compatibility).
    """
    if not GOOGLE_SHEET_WEBHOOK:
        print("GOOGLE_SHEET_WEBHOOK not set, skipping sheet log.")
        return

    payload = {
        "name": name,
        "event_type": event_type,
        "city": location,      # store full location
        "slot": when_text,     # store "date • time slot"
        "timestamp": datetime.now().isoformat()
    }

    try:
        resp = requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
        print("Sheet log status:", resp.status_code)
    except Exception as e:
        print("Error logging to sheet:", e)


# ---------- WHATSAPP NOTIFICATIONS ----------

def parse_whatsapp_recipients():
    """
    Parse WHATSAPP_RECIPIENTS env into list of (phone, apikey).
    Format: "+91xxxxxxx:APIKEY1,+91yyyyyy:APIKEY2"
    """
    recipients = []
    raw = WHATSAPP_RECIPIENTS_RAW or ""
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        phone, key = part.split(":", 1)
        phone = phone.strip()
        key = key.strip()
        if phone and key:
            recipients.append((phone, key))
    return recipients


def send_whatsapp_notifications(name: str, event_type: str, location: str, when_text: str):
    """
    Send WhatsApp notifications to all configured recipients using CallMeBot.
    """
    recipients = parse_whatsapp_recipients()
    if not recipients:
        print("No WHATSAPP_RECIPIENTS configured; skipping WhatsApp notifications.")
        return

    message = (
        "New Wedding Event Expert Booking\n"
        f"Name: {name}\n"
        f"Event: {event_type}\n"
        f"Location: {location}\n"
        f"Preferred: {when_text}\n"
    )

    for phone, apikey in recipients:
        try:
            resp = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": phone, "text": message, "apikey": apikey},
                timeout=8,
            )
            print(f"WhatsApp notify → {phone}: {resp.status_code}")
        except Exception as e:
            print(f"Error sending WhatsApp to {phone}: {e}")


# ---------- VALIDATION HELPERS ----------

def is_valid_name(text: str) -> bool:
    text = text.strip()
    if len(text) < 2:
        return False
    has_alpha = any(ch.isalpha() for ch in text)
    return has_alpha


def is_valid_location(text: str) -> bool:
    text = text.strip()
    if len(text) < 2:
        return False
    has_alpha = any(ch.isalpha() for ch in text)
    return has_alpha


def is_valid_date_text(text: str) -> bool:
    """
    Light validation: at least 5 chars and has a digit.
    For calendar we get things like '18 Nov 2025'.
    """
    text = text.strip()
    if len(text) < 5:
        return False
    has_digit = any(ch.isdigit() for ch in text)
    return has_digit


# ---------- CHAT LOGIC ----------

@app.post("/chat")
def chat(msg: Message):
    s = sessions.get(msg.session_id, {"step": "ask_name"})
    step = s["step"]
    text = msg.text.strip()

    # STEP 1 – Ask name
    if step == "ask_name":
        if not is_valid_name(text):
            reply = (
                "Hi again 😊<br>"
                "Please share your <b>first name</b> (no numbers or emojis).<br>"
                "Example: <i>Ananya</i>, <i>Rahul</i>, <i>Divya</i>"
            )
        else:
            s["name"] = text
            s["step"] = "ask_date"
            reply = (
                f"Lovely name, {text}! 💐<br><br>"
                "Step 2 of 4: Which <b>date</b> works best for your consultation call?<br><br>"
                "You can select from the calendar below or type like:<br>"
                "<i>25 Dec</i> or <i>12 Jan 2026</i>"
            )

    # STEP 2 – Ask date (calendar date)
    elif step == "ask_date":
        if not is_valid_date_text(text):
            reply = (
                "Please select or type a clear date for the call 😊<br>"
                "Example: <i>25 Dec</i> or <i>12/01/2026</i>"
            )
        else:
            s["date"] = text
            s["step"] = "ask_time_slot"
            reply = (
                "Perfect, date noted 📅<br><br>"
                "Now choose a <b>time slot</b> for your call (IST).<br>"
                "We are available between <b>11:00 AM and 8:00 PM</b>.<br><br>"
                "Please pick one option:<br><br>"
                "1️⃣ 11:00 AM – 12:00 PM<br>"
                "2️⃣ 12:00 PM – 1:00 PM<br>"
                "3️⃣ 1:00 PM – 2:00 PM<br>"
                "4️⃣ 2:00 PM – 3:00 PM<br>"
                "5️⃣ 3:00 PM – 4:00 PM<br>"
                "6️⃣ 4:00 PM – 5:00 PM<br>"
                "7️⃣ 5:00 PM – 6:00 PM<br>"
                "8️⃣ 6:00 PM – 7:00 PM<br>"
                "9️⃣ 7:00 PM – 8:00 PM<br><br>"
                "Reply with a number between <b>1</b> and <b>9</b>."
            )

    # STEP 3 – Ask time slot (11 AM – 8 PM)
    elif step == "ask_time_slot":
        slots = {
            "1": "11:00 AM – 12:00 PM",
            "2": "12:00 PM – 1:00 PM",
            "3": "1:00 PM – 2:00 PM",
            "4": "2:00 PM – 3:00 PM",
            "5": "3:00 PM – 4:00 PM",
            "6": "4:00 PM – 5:00 PM",
            "7": "5:00 PM – 6:00 PM",
            "8": "6:00 PM – 7:00 PM",
            "9": "7:00 PM – 8:00 PM",
        }

        if text not in slots:
            reply = (
                "Just pick a time from the list above 😊<br>"
                "Reply with a number between <b>1</b> and <b>9</b>."
            )
        else:
            s["time_slot"] = slots[text]
            s["step"] = "ask_event_type"
            reply = (
                "Nice, time slot locked in! ⏰<br><br>"
                "Step 3 of 4: Which event are you planning?<br><br>"
                "1️⃣ Wedding<br>"
                "2️⃣ Reception<br>"
                "3️⃣ Mehendi<br>"
                "4️⃣ Sangeet<br>"
                "5️⃣ Engagement<br>"
                "6️⃣ Other"
            )

    # STEP 4 – Event type (1–6)
    elif step == "ask_event_type":
        if text not in ["1", "2", "3", "4", "5", "6"]:
            reply = (
                "To plan it right, please pick one option 😇<br><br>"
                "Reply with:<br>"
                "1️⃣ Wedding<br>"
                "2️⃣ Reception<br>"
                "3️⃣ Mehendi<br>"
                "4️⃣ Sangeet<br>"
                "5️⃣ Engagement<br>"
                "6️⃣ Other"
            )
        else:
            mapping = {
                "1": "Wedding",
                "2": "Reception",
                "3": "Mehendi",
                "4": "Sangeet",
                "5": "Engagement",
            }
            if text == "6":
                s["step"] = "ask_other_event"
                reply = (
                    "Nice! 🎉<br>"
                    "Please type the event name you’re planning.<br>"
                    "Example: <i>Baby shower</i>, <i>Puberty function</i>, <i>Corporate event</i>"
                )
            else:
                s["event_type"] = mapping[text]
                s["step"] = "ask_location"
                reply = (
                    f"Beautiful, we’ll plan for <b>{s['event_type']}</b> ✨<br><br>"
                    "Step 4 of 4: Which <b>city/location</b> is the event happening in?"
                )

    # STEP 4B – Custom event name
    elif step == "ask_other_event":
        if not is_valid_name(text):
            reply = (
                "Please share a clear event name 😊<br>"
                "Example: <i>Baby shower</i>, <i>Puberty function</i>"
            )
        else:
            s["event_type"] = text.strip().title()
            s["step"] = "ask_location"
            reply = (
                f"Lovely! We’ll plan for <b>{s['event_type']}</b> 🎉<br><br>"
                "Step 4 of 4: Which <b>city/location</b> is the event happening in?"
            )

    # STEP 4C – Ask location, then finish
    elif step == "ask_location":
        if not is_valid_location(text):
            reply = (
                "Please share a valid city or location name 🌍<br>"
                "Example: <i>Chennai</i>, <i>Bangalore – Whitefield</i>, <i>Coimbatore</i>"
            )
        else:
            s["location"] = text
            s["step"] = "done"

            name = s.get("name", "")
            event_type = s.get("event_type", "")
            location = s.get("location", "")
            date_text = s.get("date", "")
            time_slot = s.get("time_slot", "")
            when_text = f"{date_text} • {time_slot}"

            # 1️⃣ Log to Google Sheet
            log_booking_to_sheet(name, event_type, location, when_text)

            # 2️⃣ WhatsApp alerts (if configured)
            send_whatsapp_notifications(name, event_type, location, when_text)

            reply = (
                f"Thank you, {name}! ✨<br><br>"
                "Your details are shared with our Wedding Event Expert.<br><br>"
                f"🎉 <b>Event:</b> {event_type}<br>"
                f"📍 <b>Location:</b> {location}<br>"
                f"📅 <b>Preferred:</b> {when_text}<br><br>"
                "Our expert will review this and reach out to you shortly to confirm the exact slot and next steps 💐"
            )

    # STEP 5 – Session already complete
    else:
        reply = (
            "Your details are already captured 😊<br>"
            "If you’d like to restart the chat, simply refresh the page."
        )

    sessions[msg.session_id] = s
    return {"reply": reply}


@app.get("/")
def home():
    return FileResponse("index.html")
