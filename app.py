import streamlit as st
from openai import OpenAI
import os

# Initialize OpenAI Client (Make sure to set your API Key)
# os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY"
client = OpenAI()

st.set_page_config(page_title="Wubet AI - MVP", page_icon="✨", layout="wide")

# App Header
st.title("✨ Wubet AI: Cultural Content & Smart Tourism Hub")
st.caption("AI UniPod Prototype Track — Transforming Cultural Appreciation into Tourism Revenue")
st.markdown("---")

# Layout Split: Left for Input, Right for Generated Content & E-commerce
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🎬 Content Configuration")
    
    # User Inputs
    culture_topic = st.selectbox(
        "Select Cultural Topic:",
        ["Traditional Coffee Ceremony (Buna)", "Habesha Luxury Fashion (Kemis)", "Rock-Hewn Churches (Lalibela)", "Ethiopian Gastronomy (Injera & Beyaynetu)"]
    )
    
    target_audience = st.selectbox(
        "Target Global Audience:",
        ["Western Foodies & Travelers", "East Asian Luxury Consumers", "Global History & Heritage Buffs"]
    )
    
    narrator_tone = st.slider("Energy Level (Calm to Viral Hype):", 1, 5, 4)
    
    generate_btn = st.button("🚀 Generate Viral Campaign & Pipeline", use_container_width=True)

with col2:
    if generate_btn:
        st.subheader("📱 Generated Viral Social Media Script")
        
        # Build prompt dynamically based on inputs
        tone_description = ["Educational and relaxed", "Warm and welcoming", "Engaging storytelling", "Hyper-energetic viral TikTok style", "Mind-blowing cinematic hook"][narrator_tone - 1]
        
        prompt = f"""
        Act as a world-class tourism marketing manager. Create a highly engaging viral short-form video script (TikTok/Instagram Reels format) about {culture_topic} in Ethiopia. 
        Tailor the script specifically to appeal to {target_audience}. The narrative tone must be {tone_description}.
        Include a punchy opening hook, visual scene directions in brackets, voiceover text, and high-trending hashtags.
        """
        
        with st.spinner("AI Engine generating viral assets and syncing marketplace..."):
            try:
                # Call LLM for Content Generation
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                script_output = response.choices[0].message.content
                
                # Display Generated Content
                st.text_area("Copy Voiceover Script & Scene Directions:", value=script_output, height=300)
                
                st.markdown("---")
                st.subheader("🛍️ Automated E-Commerce & Smart Tourism Bridge")
                st.info("Backend Engine matching real-time user intent with monetization loops:")
                
                # Dynamic E-Commerce/Tourism recommendations based on topic selection
                eco_col1, eco_col2 = st.columns(2)
                
                with eco_col1:
                    st.markdown("### 📦 Marketplace Product Hook")
                    if "Coffee" in culture_topic:
                        st.success("**Direct Sourced Yirgacheffe Coffee Beans**")
                        st.write("Price: $24.99 USD / Bag")
                        st.caption("Proceeds split 70/30 directly with Jimma area farm cooperatives via local payment APIs.")
                    elif "Fashion" in culture_topic:
                        st.success("**Futuristic Hand-Woven Netela/Dress**")
                        st.write("Price: $180.00 USD")
                        st.caption("Handcrafted by automated weaver syndicates in Addis Ababa.")
                    else:
                        st.success("**Traditional Ethiopian Spice & Herb Bundle**")
                        st.write("Price: $15.99 USD")
                        
                    st.button("Mock API Buy Request", disabled=True)

                with eco_col2:
                    st.markdown("### ✈️ Smart Travel Booking Gateway")
                    if "Lalibela" in culture_topic:
                        st.warning("**4-Day Lalibela Heritage Experience**")
                    elif "Coffee" in culture_topic:
                        st.warning("**Kaffa Cloud Forest Coffee Tour**")
                    else:
                        st.warning("**Addis Ababa Corridor & Culinary Tour**")
                        
                    st.write("Estimated Transit + Hotel: $1,250.00 USD")
                    st.caption("Dynamically calculated via mocked travel aggregator APIs.")
                    st.button("Mock API Booking Inquiry", disabled=True)
                    
            except Exception as e:
                st.error(f"Error connecting to AI Backend: {e}")
                st.info("Check your OpenAI API configurations.")
    else:
        st.info("Configure your target audience options on the left pane and click generate to run the pipeline.")
