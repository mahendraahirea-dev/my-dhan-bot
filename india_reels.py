# 🇮🇳 INDIA VIRAL REELS + YT SHORTS BOT
# Auto - Sarkari Yojana, Business, Raj Shamani Style, Motivation, Bhakti
# Owner: mahendraahirea-dev

import random
from datetime import datetime

# 1. INDIAN PUBLIC LA KAY PAHIJE - VIRAL NICHES
VIRAL_TOPICS = {
    "sarkari_yojana": [
        "PM Free Silai Machine Yojana - Mahilao ko 15000 mil rahe",
        "Ladli Behna Yojana 2026 New List Jari",
        "PM Awas Yojana - Ghar ke liye 2.5 Lakh",
        "Free Laptop Yojana Students ke liye"
    ],
    "business": [
        "Gaon me 20 hazar se chalne wala 3 business",
        "0 se Crore kaise bane - Raj Shamani Style",
        "Student ke liye 500 roj kamane ka tarika",
        "Bina paise ke business idea 2026"
    ],
    "motivation": [
        "Aaj ka gyan jo zindagi badal dega",
        "Safalta ka 1% Rule - Roz better bano",
        "Gareeb soch vs Ameer soch",
        "Time ka sahi use kaise kare"
    ],
    "bhakti": [
        "Hanuman ji ka ye mantra sunte hi kaam banega",
        "Shiv ji ka Pradosh ka chamatkari upay",
        "Aaj ka Panchang aur Shubh Muhurat"
    ]
}

def get_random_topic():
    niche = random.choice(list(VIRAL_TOPICS.keys()))
    topic = random.choice(VIRAL_TOPICS[niche])
    return niche, topic

def create_script(niche, topic):
    templates = {
        "sarkari_yojana": f"Badi Khabar! {topic}. Sarkar de rahi hai direct paisa. Apply kaise kare? Last date? Puri jankari is video me. Comment me YOJANA likho.",
        "business": f"Sunlo! {topic}. Ye business gaon me kabhi fail nahi hota. Mahine ka 50 hazar fix. Kaise start kare? Pura plan batata hu.",
        "motivation": f"{topic}. Raj Shamani ne bola hai - Agar tum roz 1% better bante ho, to saal me 37 guna aage nikal jaoge. Soch badlo, paisa ayega.",
        "bhakti": f"Jai Shri Ram! {topic}. Isko sunne se sab dukh door hote hai. Comment me Jai Hanuman likhna mat bhulna."
    }
    return templates.get(niche, templates["motivation"])

# 2. AUTO REEL GENERATOR
def auto_create_reel():
    niche, topic = get_random_topic()
    script = create_script(niche, topic)
    hashtags = f"#{niche} #viral #india #trending #motivation #yojana"
    
    print(f"✅ TOPIC: {topic}")
    print(f"📝 SCRIPT: {script}")
    print(f"🏷️ HASHTAGS: {hashtags}")
    print(f"🎬 FORMAT: 9:16 Reels + YT Shorts")
    print("--- READY TO UPLOAD ---")
    return {"niche": niche, "topic": topic, "script": script}

# 3. CLAUDE CUSTOM CONNECTOR KE LIYE
def claude_connector_info():
    return {
        "name": "India Viral Reels Connector",
        "niches": list(VIRAL_TOPICS.keys()),
        "status": "Auto Reels + YT Shorts LIVE"
    }

if __name__ == "__main__":
    print(f"Bot Started - {datetime.now()}")
    auto_create_reel()
