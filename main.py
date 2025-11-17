from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


import os
import requests
from datetime import datetime

app = FastAPI()


# Allow frontend (browser) to call this AP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (logo, images, etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

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
    f"Lovely name, {text}! 😊<br>"
    "To guide you better, which event are you planning?<br><br>"
    "1️⃣ Wedding<br>"
    "2️⃣ Reception<br>"
    "3️⃣ Mehendi<br>"
    "4️⃣ Sangeet<br>"
    "5️⃣ Engagement<br>"
    "6️⃣ Other"
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
       reply = (
    f"Great! {s['event_type']} it is! 🎉<br>"
    "Which city is the event happening in?"
)


    elif step == "ask_city":
        s["city"] = text
        s["step"] = "show_slots"
       reply = (
    "Amazing — just one last step! 💫<br><br>"
    "Please choose a slot for your free consultation call (IST):<br><br>"
    "1️⃣ Today • 6:30–7:00 PM<br>"
    "2️⃣ Tomorrow • 11:00–11:30 AM<br>"
    "3️⃣ Tomorrow • 4:00–4:30 PM<br><br>"
    "Reply with 1, 2, or 3."
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
    f"✨ You're all set, {s['name']}! ✨<br><br>"
    "Your free Wedding Event Expert call is confirmed.<br><br>"
    f"📅 <b>Slot:</b> {s['slot']}<br>"
    f"🏙️ <b>City:</b> {s['city']}<br>"
    f"🎉 <b>Event:</b> {s['event_type']}<br><br>"
    "Our expert will connect with you at the scheduled time.<br>"
    "Looking forward to making your wedding planning effortless 💐"
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
