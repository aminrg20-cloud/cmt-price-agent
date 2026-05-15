import streamlit as st
import json
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
from google import genai

# ==========================================
# 1. UI Setup & Layout
# ==========================================
st.set_page_config(page_title="CMT Price Intelligence | Pro", page_icon="📊", layout="wide")

st.title("📊 CMT Price Intelligence Workspace")
st.markdown("Analyse the UK market, compare competitors, and generate executive pricing strategies.")

with st.sidebar:
    st.header("⚙️ Configuration")
    SERPAPI_KEY = st.text_input("SerpApi Key", type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", type="password")
    st.markdown("---")
    st.info("System calculates Market Average by filtering out irrelevant listings.")

# ==========================================
# 2. Session State
# ==========================================
if 'workspace_data' not in st.session_state:
    st.session_state.workspace_data = pd.DataFrame(columns=[
        "SKU", "Title", "Type", "Price (£)", "Specifications", "Search Query"
    ])

# ==========================================
# 3. Core Functions
# ==========================================
def extract_data_from_url(url, api_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text(separator=' ', strip=True)[:5000]
        
        client = genai.Client(api_key=api_key)
        prompt = f"Extract product details from this text: {page_text}. Return ONLY JSON with SKU, Title, Type (OWN_BRAND/BRANDED), Price (£), Specifications, and a 5-word Search Query."
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return json.loads(res.text.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        raise Exception(f"URL Fetch Error: {e}")

def get_google_shopping_results(query):
    params = {"engine": "google_shopping", "q": query, "hl": "en", "gl": "uk", "api_key": SERPAPI_KEY}
    results = GoogleSearch(params).get_dict()
    return [{"title": i.get("title"), "price": i.get("extracted_price"), "competitor": i.get("source")} for i in results.get("shopping_results", [])[:15]]

def analyse_with_gemini(cmt_product, shopping_results):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    Senior Pricing Strategist AI. 
    Product: {json.dumps(cmt_product)} 
    Market Data: {json.dumps(shopping_results)}
    
    Task: 
    1. Filter out irrelevant items.
    2. Calculate the 'Realistic Market Average' for this specific product in the UK.
    3. Provide pricing strategy.
    
    Return ONLY JSON:
    {{
        "executive_summary": "1 sentence.",
        "pricing_recommendation": "Advice.",
        "estimated_market_demand": "High/Med/Low",
        "average_market_price": 0.00,
        "lowest_price": {{"competitor": "", "price": 0.00}},
        "most_expensive": {{"competitor": "", "price": 0.00}}
    }}
    """
    for _ in range(3):
        try:
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return json.loads(res.text.replace('```json', '').replace('```', '').strip())
        except Exception:
            time.sleep(5)
    raise Exception("AI Service Busy")

# ==========================================
# 4. Input UI
# ==========================================
st.markdown("### 📥 Add Products to Workspace")
t1, t2 = st.tabs(["🔗 Auto-Fetch", "✍️ Manual Form"])

with t1:
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        p_url = st.text_input("Product URL", placeholder="https://www.cmt.co.uk/...", label_visibility="collapsed")
    with col_btn:
        if st.button("🪄 Fetch & Add", use_container_width=True):
            if p_url and GEMINI_API_KEY:
                with st.spinner("Fetching..."):
                    data = extract_data_from_url(p_url, GEMINI_API_KEY)
                    st.session_state.workspace_data = pd.concat([st.session_state.workspace_data, pd.DataFrame([data])], ignore_index=True)

with t2:
    with st.form("manual_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        m_sku = f1.text_input("SKU")
        m_title = f1.text_input("Title")
        m_price = f2.number_input("Price (£)", min_value=0.0)
        m_query = st.text_input("Search Query")
        if st.form_submit_button("➕ Add"):
            new_row = pd.DataFrame([{"SKU": m_sku, "Title": m_title, "Price (£)": m_price, "Search Query": m_query, "Type": "OWN_BRAND", "Specifications": ""}])
            st.session_state.workspace_data = pd.concat([st.session_state.workspace_data, new_row], ignore_index=True)

st.markdown("---")
st.markdown("### 🗂️ Workspace")
st.session_state.workspace_data = st.data_editor(st.session_state.workspace_data, num_rows="dynamic", use_container_width=True, hide_index=True)

# ==========================================
# 5. Execution & Reporting
# ==========================================
if st.button("🚀 Run Executive Market Analysis", type="primary", use_container_width=True):
    if not SERPAPI_KEY or not GEMINI_API_KEY:
        st.error("Missing Keys")
    else:
        for index, row in st.session_state.workspace_data.iterrows():
            with st.spinner(f"Analysing {row['SKU']}..."):
                try:
                    raw = get_google_shopping_results(str(row['Search Query']))
                    report = analyse_with_gemini(row.to_dict(), raw)
                    
                    with st.expander(f"📊 Report: {row['Title']}", expanded=True):
                        # اضافه شدن ستون چهارم برای میانگین قیمت
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Our Price", f"£{row['Price (£)']}")
                        m2.metric("Market Average", f"£{report['average_market_price']:.2f}")
                        m3.metric("Lowest Price", f"£{report['lowest_price']['price']}", report['lowest_price']['competitor'])
                        m4.metric("Est. Demand", report['estimated_market_demand'])
                        
                        st.info(f"**Strategy:** {report['pricing_recommendation']}")
                except Exception as e:
                    st.error(f"Error: {e}")
