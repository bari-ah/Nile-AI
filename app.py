"""

Nile Navigator — AI-Powered Travel Concierge for Ethiopia

MVP prototype for AI UniPod Second Cohort application.

Built in <48 hours by the Nile Navigator team (Me, Mazaa, Hawwi).


Stack: Streamlit + rule-based NLP recommender + JSON data layer

Upgradable: drop in Anthropic Claude API for advanced chat (see LLM_OPTIONAL block)


Run with: streamlit run app.py

"""


import json

import re

from datetime import datetime

from pathlib import Path


import streamlit as st


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

# RECOMMENDER — preference-based scoring

# -----------------------------------------------------------------------------


def score_attraction(attraction, prefs):

    """

    Score an attraction based on user preferences.

    prefs: dict with keys: interests (set), family_friendly (bool),

           duration_max (hours), pace (relaxed/normal/intense), guide_ok (bool),

           budget_etb_max (int, per attraction, 0 = no limit)

    """

    score = 0.0

    tags = set(attraction["tags"])


    # Interest matching (highest weight)

    if prefs.get("interests"):

        overlap = tags & prefs["interests"]

        score += len(overlap) * 10


    # Family-friendly filter (hard filter)

    if prefs.get("family_friendly") and "family-friendly" not in tags:

        return -1  # disqualify


    # Duration fit

    duration_max = prefs.get("duration_max")

    if duration_max is not None and attraction["duration_hours"] > duration_max:

        score -= 5


    # Guide acceptance

    if not prefs.get("guide_ok", True) and attraction.get("guide_required"):

        return -1  # disqualify


    # Budget

    budget = prefs.get("budget_etb_max")

    if budget is not None and attraction["entry_fee_etb"] > budget:

        score -= 3


    # Base score from rating (popularity proxy)

    score += attraction["rating"]


    return score



def recommend(prefs, top_n=10):

    """Return top N attractions sorted by score."""

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

    """

    Build a day-by-day itinerary from recommended attractions.

    Distributes attractions across days based on area to minimize travel.

    """

    recs = recommend(prefs, top_n=days * 3)

    if not recs:

        return []


    itinerary = []

    # Group by area for geographical coherence

    by_area = {}

    for a in recs:

        by_area.setdefault(a["area"], []).append(a)


    # Distribute: take one from different areas each day

    areas = list(by_area.keys())

    for day in range(days):

        day_items = []

        # Pick 2-3 items for the day, balancing areas

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

        return ""

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

# RULE-BASED CHAT — keyword parsing + templated responses

# -----------------------------------------------------------------------------


INTEREST_KEYWORDS = {

    "history": {"history", "historical", "museum", "ancient", "lucy", "fossil", "prehistoric"},

    "culture": {"culture", "cultural", "tradition", "traditional", "ceremony", "music", "dance"},

    "religious": {"religious", "religion", "church", "cathedral", "orthodox", "christian", "spiritual", "pilgrimage"},

    "food": {"food", "eat", "restaurant", "cuisine", "coffee", "vegetarian", "vegan", "hungry", "dinner", "lunch"},

    "nature": {"nature", "outdoor", "park", "mountain", "view", "hiking", "lake", "scenery"},

    "shopping": {"shopping", "shop", "market", "buy", "souvenir", "cloth", "textile"},

    "art": {"art", "gallery", "craft", "design"},

    "family": {"family", "kids", "children", "child", "kid", "baby"},

    "luxury": {"luxury", "luxurious", "premium", "high-end"},

    "budget": {"budget", "cheap", "affordable", "backpacker"},

}


DAY_KEYWORDS = {

    1: {"1 day", "one day", "single day", "day trip"},

    2: {"2 day", "two day", "2-day"},

    3: {"3 day", "three day", "3-day", "long weekend"},

    4: {"4 day", "four day", "4-day"},

    5: {"5 day", "five day", "week", "5-day"},

}



def parse_query(text):

    """Extract preferences from a free-text query."""

    text_lower = text.lower()

    prefs = {

        "interests": set(),

        "family_friendly": False,

        "guide_ok": True,

        "duration_max": None,

        "budget_etb_max": None,

    }


    # Detect interests

    for interest, keywords in INTEREST_KEYWORDS.items():

        if any(k in text_lower for k in keywords):

            prefs["interests"].add(interest)


    # Family

    if any(k in text_lower for k in ["family", "kids", "children", "child"]):

        prefs["family_friendly"] = True

        prefs["interests"].add("family")


    # Days

    days = 3

    for n, keywords in DAY_KEYWORDS.items():

        if any(k in text_lower for k in keywords):

            days = n

            break

    # Number fallback

    m = re.search(r"(\d+)[-\s]day", text_lower)

    if m:

        days = int(m.group(1))


    # Vegetarian

    if "vegetarian" in text_lower or "vegan" in text_lower:

        prefs["interests"].add("food")

        prefs["interests"].add("vegetarian-options")


    return prefs, days



def chat_reply(user_message, prefs_history=None):

    """Generate a chatbot reply using rule-based intent parsing."""

    prefs, days = parse_query(user_message)


    # Very short queries get a greeting back

    if len(user_message.split()) < 3:

        return (

            "Hi! I'm Nile Navigator, your AI concierge for Ethiopia. "

            "Tell me what kind of trip you want — e.g., '3 days in Addis with my family, "

            "museums and Orthodox sites' — and I'll build a bookable itinerary. "

            "I work in English, Amharic (አማርኛ), and French. 🇪🇹"

        )


    # Build itinerary

    itinerary = build_itinerary(prefs, days=days)


    # Compose reply

    intro = _compose_intro(prefs, days)

    days_text = _format_itinerary_text(itinerary)

    closing = _compose_closing(prefs)


    return f"{intro}\n\n{days_text}\n\n{closing}"



def _compose_intro(prefs, days):

    bits = []

    if prefs["family_friendly"]:

        bits.append("family trip")

    if prefs["interests"]:

        interest_str = ", ".join(sorted(prefs["interests"])[:3])

        bits.append(f"{interest_str} focus")

    bits.append(f"{days} days")


    return f"Got it — {', '.join(bits)}. Here's a personalized Addis itinerary:"



def _format_itinerary_text(itinerary):

    lines = []

    for day in itinerary:

        lines.append(f"\n**Day {day['day']} — {day['theme']}**")

        for item in day["items"]:

            fee = f"{item['entry_fee_etb']} ETB" if item["entry_fee_etb"] > 0 else "free"

            lines.append(

                f"  • {item['name']} ({item['area']}) — {item['duration_hours']}h, {fee}"

            )

    return "\n".join(lines)



def _compose_closing(prefs):

    if prefs["interests"] & {"coffee", "food"}:

        extra = " I've also added a coffee ceremony option — let me know if you want me to book it."

    else:

        extra = ""

    return (

        f"Want me to bundle this with hotel + attractions + a licensed guide at a single price? "

        f"Just say 'book it' and I'll prepare a checkout.{extra}"

    )



# -----------------------------------------------------------------------------

# BOOKING (MOCK)

# -----------------------------------------------------------------------------


def calculate_booking(itinerary, hotel_id=None, num_travelers=2, days=3,

                     car_rental_id=None, car_type="sedan", with_driver=False):

    """Mock booking calculation."""

    attractions_total = sum(

        a["entry_fee_etb"] * num_travelers for day in itinerary for a in day["items"]

    )

    hotel_total = 0

    hotel_name = None

    if hotel_id and hotel_id in HOTELS:

        h = HOTELS[hotel_id]

        hotel_total = int(h["price_per_night_usd"] * DATA["exchange_rate_ETB_to_USD"]) * days

        hotel_name = h["name"]


    guide_total = 2500 * days if itinerary else 0  # ETB per day


    car_total = 0

    car_name = None

    if car_rental_id and car_rental_id in CAR_RENTALS:

        cr = CAR_RENTALS[car_rental_id]

        car_name = f"{cr['name']} ({car_type}{', with driver' if with_driver else ', self-drive'})"

        if cr.get("type") == "ride_hailing":

            # estimate ~6 rides per day

            car_total = cr.get("average_ride_etb", 350) * 6 * days

        else:

            price_map = cr.get(

                "price_per_day_with_driver_etb" if with_driver else "price_per_day_etb",

                {},

            )

            car_total = price_map.get(car_type, 0) * days


    subtotal = attractions_total + hotel_total + guide_total + car_total

    discount = int(subtotal * 0.12)  # 12% bundle discount

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

# UI

# -----------------------------------------------------------------------------


# Sidebar

with st.sidebar:

    st.image("https://flagcdn.com/w320/et.png", width=80)

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


# Main

tab_chat, tab_recommend, tab_car, tab_book = st.tabs(["💬 Chat", "🎯 Build Itinerary", "🚗 Car Rental", "📋 Book"])


# --- TAB 1: CHAT ---

with tab_chat:

    st.header("Plan your Addis trip in conversation")

    st.caption("Tell me what you want. I'll build a bookable itinerary in under a minute.")


    if "chat_history" not in st.session_state:

        st.session_state.chat_history = []


    # Display chat history

    for msg in st.session_state.chat_history:

        with st.chat_message(msg["role"]):

            st.markdown(msg["content"])


    # Suggested prompts

    if not st.session_state.chat_history:

        st.markdown("**Try one of these:**")

        col1, col2, col3 = st.columns(3)

        with col1:

            if st.button("3 days, family, museums + Orthodox sites"):

                _prompt = "Plan me a 3-day Addis trip, family of 4, includes museums and Orthodox sites"

                st.session_state.chat_history.append({"role": "user", "content": _prompt})

                reply = chat_reply(_prompt)

                st.session_state.chat_history.append({"role": "assistant", "content": reply})

                st.rerun()

        with col2:

            if st.button("Coffee + food, 2 days, vegetarian"):

                _prompt = "I'm vegetarian and love coffee. 2 days in Addis, foodie trip."

                st.session_state.chat_history.append({"role": "user", "content": _prompt})

                reply = chat_reply(_prompt)

                st.session_state.chat_history.append({"role": "assistant", "content": reply})

                st.rerun()

        with col3:

            if st.button("Adventure / nature, day trip"):

                _prompt = "Outdoor lover, want to see nature and lakes near Addis, day trip"

                st.session_state.chat_history.append({"role": "user", "content": _prompt})

                reply = chat_reply(_prompt)

                st.session_state.chat_history.append({"role": "assistant", "content": reply})

                st.rerun()


    # Chat input

    user_input = st.chat_input("Type your trip request…")

    if user_input:

        st.session_state.chat_history.append({"role": "user", "content": user_input})

        reply = chat_reply(user_input)

        st.session_state.chat_history.append({"role": "assistant", "content": reply})

        st.rerun()


    # Reset

    if st.button("🔄 Start over"):

        st.session_state.chat_history = []

        st.rerun()


# --- TAB 2: RECOMMENDER ---

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


# --- TAB 3: CAR RENTAL ---

with tab_car:

    st.header("🚗 Car rental & airport transfer")

    st.caption("Browse Addis Ababa car rental companies. All offer Bole Airport pickup.")


    # Car rental browser

    rental_filter = st.selectbox(

        "Filter by type",

        ["All", "international", "local", "ride_hailing"],

        format_func=lambda x: {

            "All": "All providers",

            "international": "International chains",

            "local": "Local companies",

            "ride_hailing": "Ride-hailing apps",

        }.get(x, x),

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


# --- TAB 4: BOOKING ---

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

            payment = st.selectbox(

                "Payment method",

                ["Telebirr", "CBE Birr", "Visa/Mastercard", "M-Pesa"],

            )


        # Car rental selector (compact, in the booking tab)

        st.markdown("### Add-ons")

        car_options = ["none"] + [c["name"] for c in DATA.get("car_rentals", [])]

        selected_car_name = st.selectbox(

            "Car rental (optional)",

            car_options,

            index=(car_options.index(

                next((c["name"] for c in DATA["car_rentals"] if c["id"] == st.session_state.get("selected_car")),

                     "none")

            ) if st.session_state.get("selected_car") else 0),

        )

        car_rental_id = None

        car_type = "sedan"

        with_driver = False

        if selected_car_name != "none":

            car_rental_id = next(

                c["id"] for c in DATA["car_rentals"] if c["name"] == selected_car_name

            )

            cr = CAR_RENTALS[car_rental_id]

            if cr.get("type") != "ride_hailing":

                car_type = st.selectbox("Car type", cr["fleet"], index=min(1, len(cr["fleet"]) - 1))

                with_driver = st.checkbox("With driver", value=True)


        # Calculate booking

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

        car_line = (

            f"| Car ({booking['car_name']}): {booking['days']} days | {booking['car_total_etb']:,} ETB |"

            if booking['car_name'] else ""

        )

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

            - A licensed guide will meet you at {st.session_state.itinerary[0]['items'][0]['name'] if st.session_state.itinerary else 'your hotel'} on Day 1.

            """)


# Footer

st.markdown("---")

st.caption(

    "Nile Navigator · MVP prototype · Built June 2026 for AI UniPod Second Cohort · "

    "Data sourced from public Ethiopian tourism information · Not a real booking platform"

)