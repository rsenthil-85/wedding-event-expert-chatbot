from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse


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


class Message(BaseModel):
    session_id: str
    text: str


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
            reply = (
                f"✅ All set, {s['name']}!\n"
                f"Your free Wedding Event Expert call is booked.\n\n"
                f"📅 Time: {s['slot']} (IST)\n"
                f"🏙️ City: {s['city']}\n"
                f"🎉 Event: {s['event_type']}\n\n"
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
