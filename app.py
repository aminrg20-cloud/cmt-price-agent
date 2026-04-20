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
    st.session_state.workspace_data = pd.DataFrame([{
        "SKU": "TX15-300/20",
        "Title": "OTEC TX15 Diamond Blade",
        "Type": "OWN_BRAND",
        "Price (£)": 85.00,
        "Specifications": "300mm diameter, 20mm bore, concrete, 15mm segment",
        "Search Query": "300mm 20mm bore concrete diamond blade 15mm segment"
    }])

# ==========================================
# 3. Core Functions (Web Scraping & AI)
# ==========================================
def extract_data_from_url(url, api_key):
    """Scrape the webpage and use Gemini to extract product details."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get visible text from the webpage (limit to 5000 chars to save API tokens)
        page_text = soup.get_text(separator=' ', strip=True)[:5000]
        
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a data extraction bot. Read this text from a product webpage:
        ---
        {page_text}
        ---
        Extract the product details and return ONLY valid JSON:
        {{
            "SKU": "Product code/SKU",
            "Title": "Product Name",
            "Type": "Return 'OWN_BRAND' if brand is OTEC or similar own brand, otherwise 'BRANDED'",
            "Price (£)": 0.00 (Extract numeric ex-VAT price),
            "Specifications": "Brief comma-separated specs (size, material, etc)",
            "Search Query": "A clean, 4-6 word search query to find this item on Google Shopping based on specs or model"
        }}
        """
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        clean_text = res.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        raise Exception(f"Failed to fetch or parse URL: {e}")

def get_google_shopping_results(query):
    params = {"engine": "google_shopping", "q": query, "hl": "en", "gl": "uk", "api_key": SERPAPI_KEY}
    search = GoogleSearch(params)
    results = search.get_dict()
    shopping_results = []
    if "shopping_results" in results:
        for item in results["shopping_results"][:15]:
            shopping_results.append({
                "title": item.get("title"), "price": item.get("extracted_price"), 
                "source": item.get("source"), "link": item.get("link")
            })
    return shopping_results

def analyse_with_gemini(cmt_product, shopping_results):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    Senior Pricing Strategist AI. 
    Product: {json.dumps(cmt_product)} | Market Data: {json.dumps(shopping_results)}
    Return ONLY JSON:
    {{
        "executive_summary": "1 sentence strategic summary.",
        "pricing_recommendation": "Hold, raise, or lower price.",
        "estimated_market_demand": "High / Medium / Low",
        "lowest_price": {{"competitor": "", "price": 0, "link": ""}},
        "most_expensive": {{"competitor": "", "price": 0, "link": ""}}
    }}
    """
    for attempt in range(3):
        try:
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            clean_text = res.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception:
            time.sleep(5)
    raise Exception("Server busy.")

# ==========================================
# 4. Interactive UI: Add Products
# ==========================================
st.markdown("### 📥 Add Products to Workspace")

# Clean UI with Tabs for different input methods
input_tab1, input_tab2 = st.tabs(["🔗 Auto-Fetch from URL", "✏️ Manual / Bulk Edit"])

with input_tab1:
    st.markdown("Paste a product URL (e.g., from cmt.co.uk). The AI will read the page and populate the row automatically.")
    col_url, col_btn = st.columns([4, 1])
    with col_url:
        product_url = st.text_input("Product URL", placeholder="https://www.cmt.co.uk/...")
    with col_btn:
        st.write("") # Spacing
        if st.button("🪄 Fetch & Add", use_container_width=True):
            if not GEMINI_API_KEY:
                st.error("⚠️ Gemini API Key required for fetching.")
            elif not product_url:
                st.warning("Please enter a URL.")
            else:
                with st.spinner("Scraping webpage and extracting data..."):
                    try:
                        extracted_data = extract_data_from_url(product_url, GEMINI_API_KEY)
                        # Add new row to session state
                        new_row = pd.DataFrame([extracted_data])
                        st.session_state.workspace_data = pd.concat([st.session_state.workspace_data, new_row], ignore_index=True)
                        st.success(f"Added {extracted_data['Title']}!")
                    except Exception as e:
                        st.error(str(e))

with input_tab2:
    st.markdown("Edit directly below. Click the **'+'** icon at the bottom of the table to add a blank row.")
    # Dynamic Data Editor tied to Session State
    st.session_state.workspace_data = st.data_editor(
        st.session_state.workspace_data, 
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="data_editor_1"
    )

st.markdown("---")

# ==========================================
# 5. Execution & Executive Reporting
# ==========================================
if st.button("🚀 Run Executive Market Analysis", type="primary"):
    if not SERPAPI_KEY or not GEMINI_API_KEY:
        st.error("⚠️ Please enter your API keys in the sidebar.")
    elif st.session_state.workspace_data.empty:
        st.warning("⚠️ Workspace is empty.")
    else:
        st.success("Initiating Market Research...")
        
        for index, row in st.session_state.workspace_data.iterrows():
            with st.spinner(f"Analysing SKU: {row['SKU']}..."):
                cmt_product = {
                    "sku": str(row['SKU']), "title": str(row['Title']), "type": str(row['Type']),
                    "specs": str(row['Specifications']), "our_price": float(row['Price (£)'])
                }
                
                try:
                    raw_data = get_google_shopping_results(str(row['Search Query']))
                    report = analyse_with_gemini(cmt_product, raw_data)
                    
                    with st.expander(f"📊 Market Report: {row['Title']} (SKU: {row['SKU']})", expanded=True):
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Our Price", f"£{row['Price (£)']}")
                        m2.metric("Lowest Market", f"£{report['lowest_price']['price']}", report['lowest_price']['competitor'])
                        m3.metric("Est. Demand", report['estimated_market_demand'])
                        
                        st.info(f"**Executive Summary:** {report['executive_summary']}")
                        st.warning(f"**Strategy:** {report['pricing_recommendation']}")
                        
                except Exception as e:
                    st.error(f"Error analysing {row['SKU']}: {e}")
