import streamlit as st
import json
import time
import pandas as pd
from serpapi import GoogleSearch
from google import genai

# ==========================================
# 1. UI Setup & Layout (British English Standard)
# ==========================================
st.set_page_config(page_title="CMT Price Intelligence | Pro", page_icon="📊", layout="wide")

st.title("📊 CMT Price Intelligence Workspace")
st.markdown("Analyse the UK market, compare competitors, and generate executive pricing strategies.")

# Sidebar for API Keys
with st.sidebar:
    st.header("⚙️ Configuration")
    SERPAPI_KEY = st.text_input("SerpApi Key", type="password")
    GEMINI_API_KEY = st.text_input("Gemini API Key", type="password")
    st.markdown("---")
    st.info("System uses advanced AI to estimate market demand and SEO competition.")

# ==========================================
# 2. Core Functions
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
    You are a Senior Pricing Strategist and Product Manager for a UK construction tools distributor.
    Product: {json.dumps(cmt_product)}
    Market Data: {json.dumps(shopping_results, indent=2)}
    
    Task: Conduct a deep executive analysis for the UK market. Match items based on specs (OWN_BRAND) or exact model (BRANDED).
    
    Return ONLY valid JSON in this exact format:
    {{
        "executive_summary": "A 2-sentence strategic summary of our market position.",
        "pricing_recommendation": "Specific advice on whether to hold, raise, or lower our price.",
        "estimated_market_demand": "High / Medium / Low (Estimate based on product type)",
        "seo_competition": "High / Medium / Low (Estimate how hard it is to rank for this query)",
        "lowest_price": {{"competitor": "", "price": 0, "link": ""}},
        "most_expensive": {{"competitor": "", "price": 0, "link": ""}},
        "closest_competitors": [
            {{"competitor": "", "price": 0, "match_confidence": "High/Medium/Low"}}
        ]
    }}
    """
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(5)
            else:
                raise e
    raise Exception("Server is busy.")

# ==========================================
# 3. Interactive Data Workspace
# ==========================================
st.markdown("### 📝 Product Workspace")
st.markdown("Add rows manually below, or click any cell to edit. You can also paste directly from Excel.")

# Default starting row
default_data = pd.DataFrame([{
    "SKU": "TX15-300/20",
    "Title": "OTEC TX15 Diamond Blade",
    "Type": "OWN_BRAND",
    "Price (£)": 85.00,
    "Specifications": "300mm diameter, 20mm bore, concrete, 15mm segment",
    "Search Query": "300mm 20mm bore concrete diamond blade 15mm segment"
}])

# Interactive Data Editor (Allows adding/deleting rows)
edited_df = st.data_editor(
    default_data, 
    num_rows="dynamic", # This is the magic that allows adding rows!
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ==========================================
# 4. Execution & Executive Reporting
# ==========================================
if st.button("🚀 Run Executive Market Analysis", type="primary"):
    if not SERPAPI_KEY or not GEMINI_API_KEY:
        st.error("⚠️ Please enter your API keys in the sidebar.")
    elif edited_df.empty:
        st.warning("⚠️ Please add at least one product to the workspace.")
    else:
        st.success("Initiating Market Research...")
        
        # We process each row and display results in an "Expander" for a clean UI
        for index, row in edited_df.iterrows():
            with st.spinner(f"Analysing SKU: {row['SKU']}..."):
                
                cmt_product = {
                    "sku": str(row['SKU']),
                    "title": str(row['Title']),
                    "type": str(row['Type']),
                    "specs": str(row['Specifications']),
                    "our_price": float(row['Price (£)'])
                }
                search_q = str(row['Search Query'])
                
                try:
                    raw_data = get_google_shopping_results(search_q)
                    report = analyse_with_gemini(cmt_product, raw_data)
                    
                    # Displaying results in a professional collapsible box for each product
                    with st.expander(f"📊 Market Report: {row['Title']} (SKU: {row['SKU']})", expanded=True):
                        
                        # Top Metrics Row
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Our Price", f"£{row['Price (£)']}")
                        m2.metric("Lowest Market", f"£{report['lowest_price']['price']}", report['lowest_price']['competitor'])
                        m3.metric("Est. Demand", report['estimated_market_demand'])
                        m4.metric("SEO Competition", report['seo_competition'])
                        
                        # Executive Summary
                        st.markdown("#### 🧠 Executive Summary")
                        st.info(report['executive_summary'])
                        
                        # Pricing Strategy
                        st.markdown("#### 💷 Strategy Recommendation")
                        st.warning(report['pricing_recommendation'])
                        
                        # Competitor Table
                        st.markdown("#### 🎯 Closest Competitors")
                        st.table(report['closest_competitors'])
                        
                except Exception as e:
                    st.error(f"Error analysing {row['SKU']}: {e}")
