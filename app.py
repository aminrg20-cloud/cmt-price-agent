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
    st.info("System uses advanced AI to extract data and estimate market demand.")

# ==========================================
# 2. Session State (Memory for the Table)
# ==========================================
if 'workspace_data' not in st.session_state:
    st.session_state.workspace_data = pd.DataFrame(columns=[
        "SKU", "Title", "Type", "Price (£)", "Specifications", "Search Query"
    ])

# ==========================================
# 3. Core Functions (Web Scraping & AI)
# ==========================================
def extract_data_from_url(url, api_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text(separator=' ', strip=True)[:5000]
        
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Extract product details from this webpage text: {page_text}
        Return ONLY valid JSON:
        {{
            "SKU": "Product code",
            "Title": "Product Name",
            "Type": "OWN_BRAND or BRANDED",
            "Price (£)": 0.00,
            "Specifications": "Brief specs",
            "Search Query": "4-6 word search query for Google Shopping"
        }}
        """
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return json.loads(res.text.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        raise Exception(f"Failed to fetch URL: {e}")

def get_google_shopping_results(query):
    params = {"engine": "google_shopping", "q": query, "hl": "en", "gl": "uk", "api_key": SERPAPI_KEY}
    results = GoogleSearch(params).get_dict()
    return [{"title": i.get("title"), "price": i.get("extracted_price"), "competitor": i.get("source")} for i in results.get("shopping_results", [])[:15]]

def analyse_with_gemini(cmt_product, shopping_results):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    Senior Pricing Strategist AI. Product: {json.dumps(cmt_product)} | Market Data: {json.dumps(shopping_results)}
    Return ONLY JSON:
    {{
        "executive_summary": "1 sentence strategic summary.",
        "pricing_recommendation": "Hold, raise, or lower price.",
        "estimated_market_demand": "High / Medium / Low",
        "lowest_price": {{"competitor": "", "price": 0}},
        "most_expensive": {{"competitor": "", "price": 0}}
    }}
    """
    for _ in range(3):
        try:
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return json.loads(res.text.replace('```json', '').replace('```', '').strip())
        except Exception:
            time.sleep(5)
    raise Exception("Server busy.")

# ==========================================
# 4. Interactive UI: Add Products
# ==========================================
st.markdown("### 📥 Add Products to Workspace")

input_tab1, input_tab2 = st.tabs(["🔗 Auto-Fetch from URL", "✍️ Manual Data Entry Form"])

with input_tab1:
    st.markdown("Paste a product URL (e.g., from cmt.co.uk). The AI will read the page and populate the table automatically.")
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        product_url = st.text_input("Product URL", placeholder="https://www.cmt.co.uk/...", label_visibility="collapsed")
    with col_btn:
        if st.button("🪄 Fetch & Add", use_container_width=True):
            if not GEMINI_API_KEY:
                st.error("⚠️ Gemini Key required.")
            elif product_url:
                with st.spinner("Scraping webpage..."):
                    try:
                        data = extract_data_from_url(product_url, GEMINI_API_KEY)
                        st.session_state.workspace_data = pd.concat([st.session_state.workspace_data, pd.DataFrame([data])], ignore_index=True)
                        st.success(f"Added {data['Title']}!")
                    except Exception as e:
                        st.error(str(e))

with input_tab2:
    st.markdown("Fill out the clean form below instead of editing tiny table cells.")
    with st.form("manual_entry_form", clear_on_submit=True):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            m_sku = st.text_input("SKU (e.g., TX15-300)")
            m_title = st.text_input("Product Title")
            m_type = st.selectbox("Product Type", ["OWN_BRAND", "BRANDED"])
        with f_col2:
            m_price = st.number_input("Price (£)", min_value=0.0, format="%.2f")
            m_specs = st.text_area("Specifications (crucial for Own Brand)")
        m_query = st.text_input("Google Shopping Search Query")
        
        if st.form_submit_button("➕ Add to Workspace", type="primary"):
            if m_sku and m_title:
                new_row = pd.DataFrame([{
                    "SKU": m_sku, "Title": m_title, "Type": m_type, 
                    "Price (£)": m_price, "Specifications": m_specs, "Search Query": m_query
                }])
                st.session_state.workspace_data = pd.concat([st.session_state.workspace_data, new_row], ignore_index=True)
                st.success("Product added successfully!")
            else:
                st.warning("SKU and Title are required.")

st.markdown("---")

# ==========================================
# 5. The Workspace View (Configured for Readability)
# ==========================================
st.markdown("### 🗂️ Current Workspace")
st.markdown("Review your list before analysing. You can still double-click any cell below to make quick edits.")

# Using column_config to make text areas wide and readable!
st.session_state.workspace_data = st.data_editor(
    st.session_state.workspace_data, 
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Title": st.column_config.TextColumn("Title", width="medium"),
        "Specifications": st.column_config.TextColumn("Specifications", width="large"),
        "Search Query": st.column_config.TextColumn("Search Query", width="large"),
        "Price (£)": st.column_config.NumberColumn("Price (£)", format="£%.2f")
    }
)

st.write("") # Spacing

# ==========================================
# 6. Execution
# ==========================================
if st.button("🚀 Run Executive Market Analysis", type="primary", use_container_width=True):
    if not SERPAPI_KEY or not GEMINI_API_KEY:
        st.error("⚠️ API keys required.")
    elif st.session_state.workspace_data.empty:
        st.warning("⚠️ Workspace is empty.")
    else:
        st.success("Initiating Market Research...")
        for index, row in st.session_state.workspace_data.iterrows():
            with st.spinner(f"Analysing {row['SKU']}..."):
                cmt_product = {"sku": str(row['SKU']), "title": str(row['Title']), "type": str(row['Type']), "specs": str(row['Specifications']), "our_price": float(row['Price (£)'])}
                try:
                    raw_data = get_google_shopping_results(str(row['Search Query']))
                    report = analyse_with_gemini(cmt_product, raw_data)
                    with st.expander(f"📊 Market Report: {row['Title']} (SKU: {row['SKU']})", expanded=True):
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Our Price", f"£{row['Price (£)']}")
                        m2.metric("Lowest Market", f"£{report['lowest_price']['price']}", report['lowest_price']['competitor'])
                        m3.metric("Est. Demand", report['estimated_market_demand'])
                        st.info(f"**Summary:** {report['executive_summary']}")
                        st.warning(f"**Strategy:** {report['pricing_recommendation']}")
                except Exception as e:
                    st.error(f"Error: {e}")
