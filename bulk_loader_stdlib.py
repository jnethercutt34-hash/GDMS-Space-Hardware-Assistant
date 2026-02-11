#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd
import os
import time
import urllib.request
import urllib.error
import re

# CONFIGURATION
GEMINI_API_KEY = "AIzaSyA3KjbmsC7copYynrmW5P_YPV_5Yj1UBnc"
DB_FILE = "space_parts_db.csv"

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

# LOAD OR CREATE DATABASE
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE)
    print(f"[OK] Loaded existing database with {len(df)} parts.")
else:
    df = pd.DataFrame(columns=[
        "Internal_PN", "Manufacturer", "Part_Number", "Category", 
        "Rad_Hard", "Specs", "Project_History", "Status", "Datasheet_Link"
    ])
    print("[OK] Created new empty database.")

# SIMPLE SCRAPER USING STDLIB URLLIB
def fetch_and_parse_page(url):
    """Fetch page and extract potential part numbers and specs."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Unknown"
        
        # Remove scripts and styles
        text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract product links/mentions - look for common patterns
        products = []
        
        # Pattern 1: Look for product codes (e.g., RTG4, ISL70001, etc.)
        product_codes = re.findall(r'\b([A-Z]{2,4}\d{2,6}[A-Z]*)\b', text)
        for code in product_codes[:20]:  # Limit to first 20
            if code not in [p.get('code') for p in products]:
                products.append({'code': code, 'type': 'part_number'})
        
        # Pattern 2: Look for product names in <h2>, <h3>, <strong>, <b> tags
        headers_text = re.findall(r'<(?:h[2-4]|strong|b)>(.*?)</(?:h[2-4]|strong|b)>', html, re.IGNORECASE)
        for header in headers_text[:15]:
            clean = re.sub(r'<[^>]+>', '', header).strip()
            if len(clean) > 5 and len(clean) < 200 and not clean.lower().startswith('menu'):
                products.append({'name': clean, 'type': 'product_name'})
        
        # Pattern 3: Look for links with product-like text
        links = re.findall(r'>([^<]{10,150}(?:product|module|fpga|mcu|memory|transceiver)[^<]{0,50})<', 
                          html, re.IGNORECASE)
        for link_text in links[:10]:
            clean = link_text.strip()
            if len(clean) > 5:
                products.append({'name': clean, 'type': 'link_text'})
        
        # Remove duplicates while preserving order
        seen = set()
        unique_products = []
        for p in products:
            key = p.get('code', p.get('name', '')).lower()
            if key and key not in seen:
                seen.add(key)
                unique_products.append(p)
        
        # Clean all text for specs extraction
        clean_text = re.sub(r'<[^>]+>', ' ', text)
        clean_text = ' '.join(clean_text.split())
        
        return title, unique_products, clean_text[:3000]
    except Exception as e:
        print(f"  [ERROR] Error fetching {url}: {e}")
        return None, None, None

# BULK LOAD LOOP
print("\n=== Starting Bulk Load ===\n")

added_count = 0

for i, target in enumerate(SEED_URLS, 1):
    print(f"[{i}/{len(SEED_URLS)}] Scraping {target['mfg']}")
    print(f"      URL: {target['url']}")
    
    title, products, page_text = fetch_and_parse_page(target['url'])
    
    if products is None:
        print(f"      [ERROR] Failed to fetch page. Skipping.")
        continue
    
    print(f"      [OK] Page fetched, found {len(products)} potential parts")
    print(f"      [INFO] Title: {title}")
    
    if not products:
        print(f"      [WARN] No products extracted from page.")
        continue
    
    # Create entries for each extracted product
    for j, product in enumerate(products):
        part_num = product.get('code') or product.get('name', f'UNKNOWN-{j}')
        
        entry = {
            "Internal_PN": f"BULK-{target['mfg'].upper()}-{j+1:03d}",
            "Manufacturer": target['mfg'],
            "Part_Number": part_num,
            "Category": target['category_hint'],
            "Rad_Hard": True,
            "Specs": f"Extracted from {title[:80]}",
            "Project_History": "Catalog Import",
            "Status": "Prototyping Only",
            "Datasheet_Link": target['url']
        }
        
        # Check for duplicates
        if entry['Part_Number'] not in df['Part_Number'].values:
            df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
            print(f"      [OK] Added: {part_num}")
            added_count += 1
        else:
            print(f"      [SKIP] Duplicate: {part_num}")
    
    time.sleep(1)  # Polite delay

print(f"\n=== Bulk Load Complete ===")
print(f"[OK] Database saved: {DB_FILE}")
print(f"[OK] Total parts added this run: {added_count}")
print(f"[OK] Total parts in database: {len(df)}")
df.to_csv(DB_FILE, index=False)
print(f"\n[OK] Script completed successfully!")
