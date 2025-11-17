from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse

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

# Simple in-memory session store
sessions = {}

# ---- ENV VARS ----
GOOGLE_SHEET_WEBHOOK = os.getenv("GOOGLE_SHEET_WEBHOOK")


class Message(BaseModel):
    session_id: str
    text: str


# ---- HELPERS ----

def log_booking_to_sheet(name: str, event_type: str, city: str, slot: str):
    """
    Send booking data to Google Sheet via Apps Script Webhook.
    """
    if not GOOGLE_SHEET_WEBHOOK:
        # If not configured, just skip
        print("GOOGLE_SHEET_WEBHOOK not set, skipping sheet log.")
        return

    payload = {
        "name": name,
        "event_type": event_type,
        "city": city,
        "slot": slot,
        "timestamp": datetime.now().isoformat()
    }

    try:
        resp = requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
        print("Sheet log status:", resp.status_code, resp.text)
    except Exception as e:
        print("Error logging to sheet:", e)


# ---- CHAT LOGIC ----

@app.post("/chat")
def chat(msg: Message):
    # get or create session
    s = sessions.get(msg.session_id, {"step": "ask_name"})
    step = s["step"]
    text = msg.text.strip()

    if step == "ask_name":
        s["name"] = text
        s["step"] = "ask_event_type"
        reply = (
            f"Nice to meet you, {text}! 😊\n"
            "What are you mainly planning now?\n"
            "1️⃣ Wedding\n2️⃣ Reception\n3️⃣ Mehendi\n4️⃣ Sangeet\n5️⃣ Engagement\n6️⃣ Other"
        )

    elif step == "ask_event_type":
        mapping = {
            "1": "Wedding",
            "2": "Reception",
            "3": "Mehendi",
            "4": "Sangeet",
            "5": "Engagement",
        }
        s["event_type"] = mapping.get(text, text)
        s["step"] = "ask_city"
        reply = f"Got it, {s['event_type']} 🎉\nWhich city is the event happening in?"

    elif step == "ask_city":
        s["city"] = text
        s["step"] = "show_slots"
        reply = (
            "Perfect! Let’s book your free call with our Wedding Event Expert.\n\n"
            "Available slots (IST):\n"
            "1️⃣ Today, 6:30–7:00 PM\n"
            "2️⃣ Tomorrow, 11:00–11:30 AM\n"
            "3️⃣ Tomorrow, 4:00–4:30 PM\n\n"
            "Reply with 1, 2, or 3 to choose your slot."
        )

    elif step == "show_slots":
        slots = {
            "1": "Today, 6:30–7:00 PM",
            "2": "Tomorrow, 11:00–11:30 AM",
            "3": "Tomorrow, 4:00–4:30 PM",
        }
        if text not in slots:
            reply = "Please reply with 1, 2, or 3 to pick your slot 🙂"
        else:
            s["slot"] = slots[text]
            s["step"] = "done"

            name = s.get("name", "")
            event_type = s.get("event_type", "")
            city = s.get("city", "")
            slot = s.get("slot", "")

            # log to Google Sheet
            log_booking_to_sheet(name, event_type, city, slot)

            reply = (
                f"✅ All set, {name}!\n"
                f"Your free Wedding Event Expert call is booked.\n\n"
                f"📅 Time: {slot} (IST)\n"
                f"🏙️ City: {city}\n"
                f"🎉 Event: {event_type}\n\n"
                "Our expert will contact you at the scheduled time. 💐"
            )

    else:
        reply = (
            "Your call is already booked ✅\n"
            "If you want to test again, refresh the page to start a new session."
        )

    sessions[msg.session_id] = s
    return {"reply": reply}


@app.get("/")
def home():
    return FileResponse("index.html")
