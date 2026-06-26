"""
Nile Navigator — AI-Powered Travel Concierge for Ethiopia
MVP prototype for AI UniPod Second Cohort application.
Fully production-optimized version using Llama 3 AI.
"""

import json
import re
from datetime import datetime
from pathlib import Path
import streamlit as st
from openai import OpenAI

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Nile Navigator — Plan your Addis trip",
    page_icon="🇪🇹",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = Path(__file__).parent / "attractions.json"

# -----------------------------------------------------------------------------
# DATA LOAD
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

DATA = load_data()
ATTRACTIONS = {a["id"]: a for a in DATA["attractions"]}
HOTELS = {h["id"]: h for h in DATA["hotels"]}
CAR_RENTALS = {c["id"]: c for c in DATA.get("car_rentals", [])}

# -----------------------------------------------------------------------------
# RECOMMENDER ENGINE — preference-based mathematical scoring
# -----------------------------------------------------------------------------
def score_attraction(attraction, prefs):
    """Score an attraction based on user explicit structural menu filters."""
    score = 0.0
    tags = set(attraction["tags"])

    # Interest matching (highest priority weight)
    if prefs.get("interests"):
        overlap = tags & prefs["interests"]
        score += len(overlap) * 10.0

    # Family-friendly hard filtering rules
    if prefs.get("family_friendly") and "family-friendly" not in tags:
        return -1  

    # Maximum duration capacity limit constraints
    duration_max = prefs.get("duration_max")
    if duration_max is not None and attraction["duration_hours"] > duration_max:
        score -= 5.0

    # Guided tour requirement enforcement rules
    if not prefs.get("guide_ok", True) and attraction.get("guide_required"):
        return -1  

    # Budget caps
    budget = prefs.get("budget_etb_max")
    if budget is not None and attraction["entry_fee_etb"] > budget:
        score -= 3.0

    # Popularity rating weight factor balance
    score += attraction["rating"]
    return score

def recommend(prefs, top_n=10):
    """Return top N matched attractions from your json file sorted by target scores."""
    scored = []
    for a in DATA["attractions"]:
        s = score_attraction(a, prefs)
        if s < 0:
            continue
        scored.append((s, a))
    scored.sort(key=lambda x: -x[0])
    return [a for _, a in scored[:top_n]]
# -----------------------------------------------------------------------------
# ITINERARY BUILDER
# -----------------------------------------------------------------------------
def build_itinerary(prefs, days, hotel_id=None):
    """Build a day-by-day structured framework itinerary to minimize cross-city movement."""
    recs = recommend(prefs, top_n=days * 3)
    if not recs:
        return []

    itinerary = []
    by_area = {}
    for a in recs:
        by_area.setdefault(a["area"], []).append(a)

    areas = list(by_area.keys())
    for day in range(days):
        day_items = []
        for area in areas:
            if by_area[area]:
                item = by_area[area].pop(0)
                day_items.append(item)
                if len(day_items) >= 3:
                    break
        itinerary.append({
            "day": day + 1,
            "theme": _day_theme(day_items),
            "items": day_items,
        })
        if not any(by_area.values()):
            break

    return itinerary

def _day_theme(items):
    if not items:
        return "Explore Addis"
    types = [i["type"] for i in items]
    if "religious" in types and "museum" in types:
        return "Heritage & Faith"
    if "market" in types or "shopping" in types:
        return "Markets & Shopping"
    if "nature" in types:
        return "Nature & Views"
    if "food" in types:
        return "Food & Culture"
    return "Explore Addis"

# -----------------------------------------------------------------------------
# LIVE AI CHAT ENGINE — Secure OpenRouter JSON-Context Injector
# -----------------------------------------------------------------------------
def chat_reply(user_message):
    """Processes open dialogue while injecting your exact attractions.json file contents."""
    if "API_KEY" not in st.secrets:
        return "⚠️ **Configuration Error**: Missing API Key! Paste `API_KEY` into your Streamlit Cloud Secrets panel."

    try:
        client = OpenAI(
            base_url="https://openrouter.ai",
            api_key=st.secrets["API_KEY"]
        )

        # Inject your attractions.json database into the AI's active context window
        knowledge_base = []
        for item in DATA["attractions"]:
            knowledge_base.append(
                f"- ID: {item['id']} | Name: {item['name']} | Area: {item['area']} | "
                f"Fee: {item['entry_fee_etb']} ETB | Rating: {item['rating']}/5 | "
                f"Desc: {item['description']}"
            )
        
        system_instruction = (
            "You are Nile Navigator, an expert AI Travel Concierge chatbot for Addis Ababa, Ethiopia.\n"
            "Build engaging itineraries and provide rich travel tips based on real local info.\n"
            "CRITICAL RULE: You MUST prioritize using the explicit landmarks from your database context below. "
            "Do not hallucinate or create fictional venues.\n\n"
            f"VERIFIED ATTRACTIONS DATA LAYER:\n{chr(10).join(knowledge_base)}\n\n"
            "LANGUAGE RULE: Detect the user's input language. If they write in Amharic (አማርኛ) or French, "
            "respond back to them fluently in that exact language. Default to English otherwise."
        )

        completion = client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ]
        )
        return completion.choices.message.content

    except Exception as e:
        return f"❌ **AI Token Error**: Unable to get response context. Details: {str(e)}"
# -----------------------------------------------------------------------------
# BOOKING TRANSACTION PROTOCOLS
# -----------------------------------------------------------------------------
def calculate_booking(itinerary, hotel_id=None, num_travelers=2, days=3,
                     car_rental_id=None, car_type="sedan", with_driver=False):
    attractions_total = sum(
        a["entry_fee_etb"] * num_travelers for day in itinerary for a in day["items"]
    )
    hotel_total = 0
    hotel_name = None
    if hotel_id and hotel_id in HOTELS:
        h = HOTELS[hotel_id]
        hotel_total = int(h["price_per_night_usd"] * DATA["exchange_rate_ETB_to_USD"]) * days
        hotel_name = h["name"]

    guide_total = 2500 * days if itinerary else 0  
    car_total = 0
    car_name = None
    if car_rental_id and car_rental_id in CAR_RENTALS:
        cr = CAR_RENTALS[car_rental_id]
        car_name = f"{cr['name']} ({car_type}{', with driver' if with_driver else ', self-drive'})"
        if cr.get("type") == "ride_hailing":
            car_total = cr.get("average_ride_etb", 350) * 6 * days
        else:
            price_map = cr.get("price_per_day_with_driver_etb" if with_driver else "price_per_day_etb", {})
            car_total = price_map.get(car_type, 0) * days

    subtotal = attractions_total + hotel_total + guide_total + car_total
    discount = int(subtotal * 0.12)  
    total = subtotal - discount

    return {
        "hotel_name": hotel_name,
        "hotel_total_etb": hotel_total,
        "attractions_total_etb": attractions_total,
        "guide_total_etb": guide_total,
        "car_name": car_name,
        "car_total_etb": car_total,
        "subtotal_etb": subtotal,
        "discount_etb": discount,
        "total_etb": total,
        "total_usd": round(total / DATA["exchange_rate_ETB_to_USD"], 2),
        "num_travelers": num_travelers,
        "days": days,
    }

# -----------------------------------------------------------------------------
# APPLICATION GRAPHICAL INTERFACE (UI)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://flagcdn.com", width=80)
    st.title("🇪🇹 Nile Navigator")
    st.caption("Your AI concierge for Ethiopia")
    st.markdown("---")
    st.markdown("**Quick filters**")
    family = st.checkbox("👨‍👩‍👧 Family-friendly")
    guide_ok = st.checkbox("🗣️ Licensed guide OK", value=True)
    budget = st.slider("💰 Per-attraction budget (ETB)", 0, 3000, 1000, 100)
    duration = st.slider("⏱️ Max attraction duration (hours)", 0.5, 8.0, 4.0, 0.5)
    st.markdown("---")
    st.markdown("**Language**")
    lang = st.radio("", ["English", "አማርኛ", "Français"], label_visibility="collapsed")
    st.markdown("---")
    st.caption("MVP built for AI UniPod · June 2026")

tab_chat, tab_recommend, tab_car, tab_book = st.tabs(["💬 Chat", "🎯 Build Itinerary", "🚗 Car Rental", "📋 Book"])

# --- TAB 1: LIVE CHAT VIEW ---
with tab_chat:
    st.header("Plan your Addis trip in conversation")
    st.caption("Tell me what you want. I'll build a bookable itinerary in under a minute.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.chat_history:
        st.markdown("**Try one of these:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("3 days, family, museums + Orthodox sites"):
                _prompt = "Plan me a 3-day Addis trip, family of 4, includes museums and Orthodox sites"
                st.session_state.chat_history.append({"role": "user", "content": _prompt})
                with st.spinner("Nile Navigator AI is thinking..."):
                    reply = chat_reply(_prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                st.rerun()
        with col2:
            if st.button("Coffee + food, 2 days, vegetarian"):
                _prompt = "I'm vegetarian and love coffee. 2 days in Addis, foodie trip."
                st.session_state.chat_history.append({"role": "user", "content": _prompt})
                with st.spinner("Nile Navigator AI is mapping flavors..."):
                    reply = chat_reply(_prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                st.rerun()
        with col3:
            if st.button("Adventure / nature, day trip"):
                _prompt = "Outdoor lover, want to see nature and lakes near Addis, day trip"
                st.session_state.chat_history.append({"role": "user", "content": _prompt})
                with st.spinner("Nile Navigator AI is exploring maps..."):
                    reply = chat_reply(_prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                st.rerun()

    user_input = st.chat_input("Type your trip request…")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Nile Navigator AI is formulating your response..."):
            reply = chat_reply(user_input)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("🔄 Start over"):
        st.session_state.chat_history = []
        st.rerun()
# --- TAB 2: STRUCTURAL GENERATOR VIEW ---
with tab_recommend:
    st.header("Build your custom itinerary")

    col1, col2 = st.columns(2)
    with col1:
        interests = st.multiselect(
            "What are you interested in?",
            ["history", "culture", "religious", "food", "nature", "shopping", "art"],
            default=["history", "culture"],
        )
        days = st.slider("How many days?", 1, 7, 3)
    with col2:
        pace = st.select_slider("Pace", options=["relaxed", "normal", "intense"], value="normal")
        hotel_pref = st.selectbox(
            "Hotel preference",
            options=["no hotel"] + [h["name"] for h in DATA["hotels"]],
            index=1,
        )

    if st.button("🎯 Generate itinerary", type="primary"):
        prefs = {
            "interests": set(interests),
            "family_friendly": family,
            "guide_ok": guide_ok,
            "duration_max": duration,
            "budget_etb_max": budget,
        }
        itinerary = build_itinerary(prefs, days=days)

        st.session_state.itinerary = itinerary
        st.session_state.itinerary_prefs = prefs
        st.session_state.itinerary_days = days
        st.session_state.itinerary_hotel = (
            None if hotel_pref == "no hotel" else next(
                h["id"] for h in DATA["hotels"] if h["name"] == hotel_pref
            )
        )

    if "itinerary" in st.session_state and st.session_state.itinerary:
        st.success(f"Itinerary generated — {len(st.session_state.itinerary)} days")

        for day in st.session_state.itinerary:
            with st.expander(f"📅 Day {day['day']} — {day['theme']}", expanded=True):
                for item in day["items"]:
                    st.markdown(f"### {item['name']}")
                    fee_text = "Free" if item["entry_fee_etb"] == 0 else f"{item['entry_fee_etb']} ETB"
                    st.caption(f"📍 {item['area']} · ⏱️ {item['duration_hours']}h · 💵 {fee_text} · ⭐ {item['rating']}/5")
                    st.write(item["description"])
                    if item.get("guide_required"):
                        st.info("🗣️ Licensed guide required (we can arrange one)")

# --- TAB 3: VEHICLE BROWSER ---
with tab_car:
    st.header("🚗 Car rental & airport transfer")
    st.caption("Browse Addis Ababa car rental companies. All offer Bole Airport pickup.")

    rental_filter = st.selectbox(
        "Filter by type",
        ["All", "international", "local", "ride_hailing"],
        format_func=lambda x: {"All": "All providers", "international": "International chains", "local": "Local companies", "ride_hailing": "Ride-hailing apps"}.get(x, x),
    )

    rentals_to_show = DATA.get("car_rentals", [])
    if rental_filter != "All":
        rentals_to_show = [r for r in rentals_to_show if r["type"] == rental_filter]

    for r in rentals_to_show:
        with st.expander(f"🚗 {r['name']}  ⭐ {r['rating']}/5  ·  {r['type'].replace('_', ' ').title()}"):
            st.markdown(f"**Fleet:** {', '.join(r['fleet'])}")
            st.markdown(f"**Locations:** {', '.join(r['locations'])}")
            if r.get("airport_pickup"):
                st.success(f"✈️ Bole Airport pickup available — {r.get('airport_transfer_etb', 'N/A')} ETB one-way")
            if r.get("insurance_included"):
                st.info("🛡️ Insurance included")
            else:
                st.warning("⚠️ Insurance not included — add separately")

            if r.get("type") == "ride_hailing":
                st.markdown(f"**Average ride:** ~{r.get('average_ride_etb')} ETB")
                st.caption(r.get("note", ""))
            else:
                st.markdown("**Self-drive daily rates:**")
                cols = st.columns(len(r.get("price_per_day_etb", {})))
                for i, (car_type, price) in enumerate(r.get("price_per_day_etb", {}).items()):
                    with cols[i]:
                        st.metric(car_type.title(), f"{price:,} ETB")
                if r.get("has_driver_option"):
                    st.markdown("**With driver daily rates:**")
                    cols = st.columns(len(r.get("price_per_day_with_driver_etb", {})))
                    for i, (car_type, price) in enumerate(r.get("price_per_day_with_driver_etb", {}).items()):
                        with cols[i]:
                            st.metric(car_type.title(), f"{price:,} ETB")

            if st.button(f"Select {r['name']}", key=f"select_{r['id']}"):
                st.session_state.selected_car = r["id"]
                st.success(f"✅ {r['name']} selected — go to 'Book' tab to see it in your total")

# --- TAB 4: PROTO-CHECKOUT PLATFORM ---
with tab_book:
    st.header("📋 Book your trip")
    st.caption("Mock checkout — no real payment. This is the prototype.")

    if "itinerary" not in st.session_state or not st.session_state.itinerary:
        st.warning("Build an itinerary first in the 'Build Itinerary' tab, then come back here to book.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            travelers = st.number_input("Number of travelers", 1, 10, 2)
        with col2:
            payment = st.selectbox("Payment method", ["Telebirr", "CBE Birr", "Visa/Mastercard", "M-Pesa"])

        st.markdown("### Add-ons")
        car_options = ["none"] + [c["name"] for c in DATA.get("car_rentals", [])]
        selected_car_name = st.selectbox(
            "Car rental (optional)",
            car_options,
            index=(car_options.index(next((c["name"] for c in DATA["car_rentals"] if c["id"] == st.session_state.get("selected_car")), "none")) if st.session_state.get("selected_car") else 0),
        )
        
        car_rental_id = None
        car_type = "sedan"
        with_driver = False
        if selected_car_name != "none":
            car_rental_id = next(c["id"] for c in DATA["car_rentals"] if c["name"] == selected_car_name)
            cr = CAR_RENTALS[car_rental_id]
            if cr.get("type") != "ride_hailing":
                car_type = st.selectbox("Car type", cr["fleet"], index=min(1, len(cr["fleet"]) - 1))
                with_driver = st.checkbox("With driver", value=True)

        booking = calculate_booking(
            st.session_state.itinerary,
            hotel_id=st.session_state.get("itinerary_hotel"),
            num_travelers=travelers,
            days=st.session_state.get("itinerary_days", 3),
            car_rental_id=car_rental_id,
            car_type=car_type,
            with_driver=with_driver,
        )

        st.markdown("### Booking summary")
        car_line = f"| Car ({booking['car_name']}): {booking['days']} days | {booking['car_total_etb']:,} ETB |" if booking['car_name'] else ""
        
        st.markdown(f"""

        | Item | Cost |
        |---|---|
        | Hotel ({booking['hotel_name'] or 'None selected'}): {booking['days']} nights | {booking['hotel_total_etb']:,} ETB |
        | Attractions × {booking['num_travelers']} travelers | {booking['attractions_total_etb']:,} ETB |
        | Licensed guide × {booking['days']} days | {booking['guide_total_etb']:,} ETB |
        {car_line}

        | **Subtotal** | **{booking['subtotal_etb']:,} ETB** |
        | Bundle discount (12%) | -{booking['discount_etb']:,} ETB |
        | **Total** | **{booking['total_etb']:,} ETB (≈ ${booking['total_usd']})** |
        """)

        if st.button("✅ Confirm booking (mock)", type="primary"):
            st.session_state.booking_confirmed = booking
            st.balloons()
            st.success("🎉 Booking confirmed! Check your email for the itinerary PDF and WhatsApp confirmation.")
            car_msg = f"\n- Car rental: {booking['car_name']}" if booking['car_name'] else ""
            st.info(f"""
            **Confirmation details:**
            - Booking ID: NN-{datetime.now().strftime('%Y%m%d%H%M%S')}
            - Travelers: {travelers}
            - Payment: {payment}
            - Total: {booking['total_etb']:,} ETB (${booking['total_usd']}){car_msg}
            - A licensed guide will meet you at on Day 1.
            """)

# FOOTER
st.markdown("---")
st.caption("Nile Navigator · MVP prototype · Built June 2026 for AI UniPod Second Cohort · Data sourced from public Ethiopian tourism information · Not a real booking platform")
