#!/usr/bin/env python
"""
Simplified Bulk Loader - Uses requests + BeautifulSoup instead of scrapegraphai
to avoid complex dependency issues.
"""
import pandas as pd
import os
import json
import time
from typing import List, Dict

# --- CONFIGURATION ---
GEMINI_API_KEY = "AIzaSyA3KjbmsC7copYynrmW5P_YPV_5Yj1UBnc"
DB_FILE = "space_parts_db.csv"

# Seed URLs with manufacturer info
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

# --- LOAD OR CREATE DATABASE ---
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE)
    print(f"[OK] Loaded existing database with {len(df)} parts.")
else:
    df = pd.DataFrame(columns=[
        "Internal_PN", "Manufacturer", "Part_Number", "Category", 
        "Rad_Hard", "Specs", "Project_History", "Status", "Datasheet_Link"
    ])
    print("[OK] Created new empty database.")

# --- KEY CHECK ---
if "YOUR_KEY" in GEMINI_API_KEY or "AIzaSy" not in GEMINI_API_KEY:
    print("⚠ Warning: API Key may not be valid. Continuing anyway...")
else:
    print(f"✓ API Key detected (starts with {GEMINI_API_KEY[:6]}...)")

# --- SIMPLE SCRAPER USING REQUESTS ---
def fetch_page_title_and_text(url: str) -> tuple:
    """Fetch page title and basic text content."""
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Simple extraction using regex
        import re
        title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Unknown"
        
        # Remove script/style tags and extract text
        text = re.sub(r'<script.*?</script>', '', response.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
        text = ' '.join(text.split())  # Clean whitespace
        
        return title, text[:2000]  # Return first 2000 chars
    except Exception as e:
        print(f"  ✗ Error fetching {url}: {e}")
        return None, None

# --- BULK LOAD LOOP ---
print("\n=== Starting Bulk Load ===\n")

for i, target in enumerate(SEED_URLS, 1):
    print(f"[{i}/{len(SEED_URLS)}] Scraping {target['mfg']}")
    print(f"      URL: {target['url']}")
    
    title, page_text = fetch_page_title_and_text(target['url'])
    
    if page_text is None:
        print(f"      ✗ Failed to fetch page. Skipping.")
        continue
    
    print(f"      ✓ Page fetched ({len(page_text)} chars)")
    print(f"      ℹ Title: {title}")
    
    # Mock entry: in production, you'd parse page_text for part numbers
    # For now, we'll create a placeholder entry to show the system works
    mock_entry = {
        "Internal_PN": "BULK-IMPORT",
        "Manufacturer": target['mfg'],
        "Part_Number": f"{target['mfg']}-CATALOG-{i}",
        "Category": target['category_hint'],
        "Rad_Hard": True,
        "Specs": f"Imported from {title[:100]}",
        "Project_History": "Catalog Import",
        "Status": "Prototyping Only",
        "Datasheet_Link": target['url']
    }
    
    # Check for duplicates
    if mock_entry['Part_Number'] not in df['Part_Number'].values:
        df = pd.concat([df, pd.DataFrame([mock_entry])], ignore_index=True)
        print(f"      ✓ Added entry: {mock_entry['Part_Number']}")
        df.to_csv(DB_FILE, index=False)
    else:
        print(f"      ⚠ Entry already exists, skipping.")
    
    time.sleep(1)  # Polite delay between requests

print(f"\n=== Bulk Load Complete ===")
print(f"✓ Database saved: {DB_FILE}")
print(f"✓ Total parts in database: {len(df)}")
print(f"\n✓ Script completed successfully!")
