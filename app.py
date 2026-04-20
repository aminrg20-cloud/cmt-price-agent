import streamlit as st
import json
import time
from serpapi import GoogleSearch
from google import genai

# ==========================================
# 1. UI Setup & Layout (British English Standard)
# ==========================================
st.set_page_config(page_title="CMT Price Intelligence", page_icon="🏗️", layout="wide")

st.title("🏗️ CMT Price Intelligence Agent")
st.markdown("Analyse the UK market and compare prices across Google Shopping UK.")

# Sidebar for API Keys
with st.sidebar:
    st.header("⚙️ Configuration")
    st.markdown("Initialise the system with your API keys.")
    SERPAPI_KEY = st.text_input("SerpApi Key", type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", type="password")
    st.markdown("---")
    st.info("Keys are treated as shared mental context and not stored permanently.")

# ==========================================
# 2. Main Input Form
# ==========================================
col1, col2 = st.columns(2)

with col1:
    prod_title = st.text_input("Product Title", value="OTEC TX15 Diamond Blade")
    prod_sku = st.text_input("SKU", value="TX15-300/20")
    prod_type = st.selectbox("Product Type", ["OWN_BRAND", "BRANDED"])

with col2:
    prod_price = st.number_input("Our Price (Ex VAT £)", value=85.00, step=1.00)
    specs = st.text_area("Specifications", value="300mm diameter, 20mm bore, concrete, 15mm segment, Super Premium tier")

search_query = st.text_input("Google Shopping UK Search Query", value="300mm 20mm bore concrete diamond blade 15mm segment")

# ==========================================
# 3. Core Functions
# ==========================================
def get_google_shopping_results(query):
    params = {
      "engine": "google_shopping",
      "q": query,
      "hl": "en",
      "gl": "uk", 
      "api_key": SERPAPI_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    
    shopping_results = []
    if "shopping_results" in results:
        for item in results["shopping_results"][:15]:
            shopping_results.append({
                "title": item.get("title"),
                "price": item.get("extracted_price"),
                "source": item.get("source"),
                "link": item.get("link")
            })
    return shopping_results

def analyse_with_gemini(cmt_product, shopping_results):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    You are an expert pricing AI Agent for a UK distributor of construction and heavy machinery.
    Product: {json.dumps(cmt_product)}
    Market Data: {json.dumps(shopping_results, indent=2)}
    
    Task:
    1. Match items based on specs (for OWN_BRAND) or exact model (for BRANDED).
    2. Identify the cheapest, most expensive, and 3 closest competitors.
    3. Ensure all analysis is tailored for the UK trade market.
    
    Return ONLY JSON:
    {{
        "lowest_price": {{"competitor": "", "price": 0, "link": ""}},
        "most_expensive": {{"competitor": "", "price": 0, "link": ""}},
        "closest_competitors": [
            {{"competitor": "", "price": 0, "match_confidence": "High/Medium/Low"}}
        ]
    }}
    """
    
    response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
    clean_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(clean_text)

# ==========================================
# 4. Execution Logic
# ==========================================
if st.button("🚀 Run Market Analysis", type="primary"):
    if not SERPAPI_KEY or not GEMINI_API_KEY:
        st.error("⚠️ Please enter your API keys in the sidebar.")
    else:
        with st.spinner('Gathering data from Google Shopping UK and analysing...'):
            try:
                raw_data = get_google_shopping_results(search_query)
                final_report = analyse_with_gemini(cmt_product, raw_data)
                
                st.success("Analysis Complete!")
                
                res_col1, res_col2 = st.columns(2)
                res_col1.metric("Lowest Market Price", f"£{final_report['lowest_price']['price']}", final_report['lowest_price']['competitor'])
                res_col2.metric("Highest Market Price", f"£{final_report['most_expensive']['price']}", final_report['most_expensive']['competitor'])
                
                st.markdown("### 🎯 Competitor Breakdown")
                st.table(final_report['closest_competitors'])
                
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
