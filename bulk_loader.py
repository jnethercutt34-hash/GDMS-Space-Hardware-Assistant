import nest_asyncio
import pandas as pd
import os
from scrapegraphai.graphs import SmartScraperGraph

# --- THE FIX: Force SSL Bypass at System Level ---
os.environ["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"

nest_asyncio.apply()

# --- CONFIGURATION ---
# !!! PASTE YOUR KEY INSIDE THE QUOTES BELOW !!!
GEMINI_API_KEY = "AIzaSyA3KjbmsC7copYynrmW5P_YPV_5Yj1UBnc" # <--- REPLACE THIS WITH YOUR KEY IF NEEDED

DB_FILE = "space_parts_db.csv"

# The "Golden List"
SEED_URLS = [
    {
        "mfg": "Microchip",
        "url": "https://www.microchip.com/en-us/solutions/aerospace-and-defense/space",
        "category_hint": "FPGA, MCU, Memory"
    },
    {
        "mfg": "Renesas",
        "url": "https://www.renesas.com/us/en/products/space-harsh-environment",
        "category_hint": "Power Management, Rad-Hard Analog"
    },
    {
        "mfg": "STMicroelectronics",
        "url": "https://www.st.com/en/space-products.html",
        "category_hint": "Logic, Power, Analog"
    }
]

# --- LOAD DATABASE ---
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE)
    print(f"Loaded existing database with {len(df)} parts.")
else:
    df = pd.DataFrame(columns=[
        "Internal_PN", "Manufacturer", "Part_Number", "Category", 
        "Rad_Hard", "Specs", "Project_History", "Status", "Datasheet_Link"
    ])
    print("Created new empty database.")

# --- THE BULK SCRAPER ---
graph_config = {
    "llm": {
        "api_key": GEMINI_API_KEY,
        "model": "google_genai/gemini-1.5-flash", 
        "temperature": 0,
    },
    # REMOVED the causing error line. Kept only timeout.
    "loader_kwargs": {
        "goto_timeout": 60000, # 60s timeout
    }
}

# --- KEY CHECK ---
if "YOUR_KEY" in GEMINI_API_KEY:
    print("❌ STOP! You didn't paste your real API Key in line 13.")
    exit()

print(f"✅ API Key detected (starts with {GEMINI_API_KEY[:6]}...)")

for target in SEED_URLS:
    print(f"\n--- Bulk Scraping {target['mfg']} ---")
    print(f"Target: {target['url']}")
    
    prompt = f"""
    You are a data engineer extracting a product catalog.
    Look at this page and extract a list of ALL space-grade/rad-hard electronic components listed.
    
    For each part, extract:
    1. Part Number (e.g., RTG4, ISL70001)
    2. Description/Specs (Key technical details)
    3. Category (Best guess based on: {target['category_hint']})
    
    Return a JSON list of objects.
    Important: If the page lists a table, try to get every row.
    """
    
    try:
        scraper = SmartScraperGraph(
            prompt=prompt,
            source=target['url'],
            config=graph_config
        )
        
        results = scraper.run()
        
        if isinstance(results, dict):
            results = [results]
            
        print(f"Found {len(results)} potential parts.")
        
        new_parts = []
        for item in results:
            # Avoid dupes
            if item.get('Part_Number') and item.get('Part_Number') not in df['Part_Number'].values:
                new_entry = {
                    "Internal_PN": "BULK-IMPORT",
                    "Manufacturer": target['mfg'],
                    "Part_Number": item.get('Part_Number'),
                    "Category": item.get('Category', "Uncategorized"),
                    "Rad_Hard": True,
                    "Specs": item.get('Description', "Imported from Master List"),
                    "Project_History": "Catalog Import",
                    "Status": "Prototyping Only",
                    "Datasheet_Link": target['url']
                }
                new_parts.append(new_entry)
        
        if new_parts:
            new_df = pd.DataFrame(new_parts)
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(DB_FILE, index=False)
            print(f"✅ Successfully added {len(new_parts)} new parts to DB.")
        else:
            print("No new parts found (or duplicates skipped).")
            
    except Exception as e:
        print(f"❌ Error scraping {target['mfg']}: {e}")

print("\nBulk Load Complete!")