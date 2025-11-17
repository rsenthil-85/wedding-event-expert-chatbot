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

# (Logo not used now, but static is harmless)
app.mount("/static", StaticFiles(directory="."), name="static")

# Simple in-memory session store
sessions = {}

# Google Sheet webhook (already set in Render)
GOOGLE_SHEET_WEBHOOK = os.getenv("GOOGLE_SHEET_WEBHOOK")


class Message(BaseModel):
    session_id: str
    text: str


def log_booking_to_sheet(name: str, event_type: str, city: str, slot: str):
    """
    Send booking data to Google Sheet via Apps Script Webhook.
    """
    if not GOOGLE_SHEET_WEBHOOK:
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
        print("Sheet log status:", resp.status_code)
    except Exception as e:
        print("Error logging to sheet:", e)


@app.post("/chat")
def chat(msg: Message):
    # get or create session
    s = sessions.get(msg.session_id, {"step": "ask_name"})
    step = s["step"]
    text = msg.text.strip()

    # STEP 1 – Ask name
    if step == "ask_name":
        s["name"] = text
        s["step"] = "ask_event_type"
        reply = (
            f"Lovely name, {text}! 😊<br>"
            "To guide you better, which event are you planning?<br><br>"
            "1️⃣ Wedding<br>"
            "2️⃣ Reception<br>"
            "3️⃣ Mehendi<br>"
            "4️⃣ Sangeet<br>"
            "5️⃣ Engagement<br>"
            "6️⃣ Other"
        )

    # STEP 2 – Ask event type
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
        reply = (
            f"Great! <b>{s['event_type']}</b> it is 🎉<br>"
            "Which city is the event happening in?"
        )

    # STEP 3 – Ask city
    elif step == "ask_city":
        s["city"] = text
        s["step"] = "show_slots"
        reply = (
            "Amazing — just one last step! 💫<br><br>"
            "Please choose a slot for your free consultation call (IST):<br><br>"
            "1️⃣ Today • 6:30–7:00 PM<br>"
            "2️⃣ Tomorrow • 11:00–11:30 AM<br>"
            "3️⃣ Tomorrow • 4:00–4:30 PM<br><br>"
            "Reply with <b>1</b>, <b>2</b>, or <b>3</b>."
        )

    # STEP 4 – Show slots and confirm
    elif step == "show_slots":
        slots = {
            "1": "Today • 6:30–7:00 PM",
            "2": "Tomorrow • 11:00–11:30 AM",
            "3": "Tomorrow • 4:00–4:30 PM",
        }
        if text not in slots:
            reply = (
                "Oops 😅 that doesn’t seem right.<br>"
                "Please reply with <b>1</b>, <b>2</b>, or <b>3</b> to pick your slot."
            )
        else:
            s["slot"] = slots[text]
            s["step"] = "done"

            name = s.get("name", "")
            event_type = s.get("event_type", "")
            city = s.get("city", "")
            slot = s.get("slot", "")

            # Log lead into Google Sheet
            log_booking_to_sheet(name, event_type, city, slot)

            reply = (
                f"✨ You’re all set, {name}! ✨<br><br>"
                "Your free Wedding Event Expert call is confirmed.<br><br>"
                f"📅 <b>Slot:</b> {slot}<br>"
                f"🏙️ <b>City:</b> {city}<br>"
                f"🎉 <b>Event:</b> {event_type}<br><br>"
                "Our expert will connect with you at the scheduled time.<br>"
                "Looking forward to making your planning effortless 💐"
            )

    # STEP 5 – Session already complete
    else:
        reply = (
            "Your consultation is already booked 😊<br>"
            "If you’d like to restart, simply refresh the page."
        )

    sessions[msg.session_id] = s
    return {"reply": reply}


@app.get("/")
def home():
    return FileResponse("index.html")
