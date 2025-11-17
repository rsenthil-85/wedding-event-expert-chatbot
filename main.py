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

# Static mount (logo etc. if needed)
app.mount("/static", StaticFiles(directory="."), name="static")

# Simple in-memory session store
sessions = {}

# Google Sheet webhook
GOOGLE_SHEET_WEBHOOK = os.getenv("GOOGLE_SHEET_WEBHOOK")


class Message(BaseModel):
    session_id: str
    text: str


def log_booking_to_sheet(name: str, event_type: str, location: str, when_text: str):
    """
    Send booking data to Google Sheet via Apps Script Webhook.

    NOTE:
    For backward compatibility with your existing sheet script,
    we still send keys named `city` and `slot`.
    """
    if not GOOGLE_SHEET_WEBHOOK:
        print("GOOGLE_SHEET_WEBHOOK not set, skipping sheet log.")
        return

    payload = {
        "name": name,
        "event_type": event_type,
        "city": location,          # using 'city' key to store location
        "slot": when_text,         # using 'slot' key to store preferred date & time
        "timestamp": datetime.now().isoformat()
    }

    try:
        resp = requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
        print("Sheet log status:", resp.status_code)
    except Exception as e:
        print("Error logging to sheet:", e)


# -------- VALIDATION HELPERS --------

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


def is_valid_datetime_text(text: str) -> bool:
    """
    Very light check: at least a few chars and contains a digit.
    (Example: '12 Jan, 6:30 PM', 'Next Saturday evening')
    """
    text = text.strip()
    if len(text) < 5:
        return False
    has_digit = any(ch.isdigit() for ch in text)
    return has_digit


# -------- CHAT LOGIC --------

@app.post("/chat")
def chat(msg: Message):
    s = sessions.get(msg.session_id, {"step": "ask_name"})
    step = s["step"]
    text = msg.text.strip()

    # STEP 1 – Ask name (welcome + name)
    if step == "ask_name":
        if not is_valid_name(text):
            reply = (
                "Hi again 😊<br>"
                "Please share your <b>first name</b> (no numbers or emojis).<br>"
                "Example: <i>Ananya</i>, <i>Rahul</i>, <i>Divya</i>"
            )
        else:
            s["name"] = text
            s["step"] = "ask_event_type"
            reply = (
                f"Lovely name, {text}! 💐<br><br>"
                "Step 2 of 4: Which event are you planning?<br><br>"
                "1️⃣ Wedding<br>"
                "2️⃣ Reception<br>"
                "3️⃣ Mehendi<br>"
                "4️⃣ Sangeet<br>"
                "5️⃣ Engagement<br>"
                "6️⃣ Other"
            )

    # STEP 2 – Ask event type (1–6; if 6 → custom)
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
                    "Step 3 of 4: Which <b>city/location</b> is the event happening in?"
                )

    # STEP 2B – Custom event name
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
                "Step 3 of 4: Which <b>city/location</b> is the event happening in?"
            )

    # STEP 3 – Ask location
    elif step == "ask_location":
        if not is_valid_location(text):
            reply = (
                "Please share a valid city or location name 🌍<br>"
                "Example: <i>Chennai</i>, <i>Bangalore – Whitefield</i>, <i>Coimbatore</i>"
            )
        else:
            s["location"] = text
            s["step"] = "ask_datetime"
            reply = (
                "Great, noted the location 💫<br><br>"
                "Step 4 of 4: When would you like to schedule the <b>consultation call</b>?<br><br>"
                "You can reply like:<br>"
                "<i>12 Jan, between 6–7 PM</i><br>"
                "<i>Tomorrow evening after 5 PM</i>"
            )

    # STEP 4 – Ask preferred date & time
    elif step == "ask_datetime":
        if not is_valid_datetime_text(text):
            reply = (
                "Please share a clear date and time range for the call 😊<br>"
                "Example: <i>25 Dec, 4–5 PM</i> or <i>Tomorrow after 7 PM</i>"
            )
        else:
            s["when"] = text
            s["step"] = "done"

            name = s.get("name", "")
            event_type = s.get("event_type", "")
            location = s.get("location", "")
            when_text = s.get("when", "")

            # Log lead into Google Sheet
            log_booking_to_sheet(name, event_type, location, when_text)

            reply = (
                f"Thank you, {name}! ✨<br><br>"
                "Your details are shared with our Wedding Event Expert.<br><br>"
                f"🎉 <b>Event:</b> {event_type}<br>"
                f"📍 <b>Location:</b> {location}<br>"
                f"📅 <b>Preferred time:</b> {when_text}<br><br>"
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
