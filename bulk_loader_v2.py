#!/usr/bin/env python
import pandas as pd
import os
import time
import urllib.request
import re

GEMINI_API_KEY = "AIzaSyA3KjbmsC7copYynrmW5P_YPV_5Yj1UBnc"
DB_FILE = "space_parts_db.csv"

SEED_URLS = [
    {"mfg": "Microchip", "url": "https://www.microchip.com/en-us/solutions/aerospace-and-defense/space", "category_hint": "FPGA, MCU, Memory"},
    {"mfg": "Renesas", "url": "https://www.renesas.com/us/en/products/space-harsh-environment", "category_hint": "Power Management, Rad-Hard Analog"},
    {"mfg": "STMicroelectronics", "url": "https://www.st.com/en/space-products.html", "category_hint": "Logic, Power, Analog"}
]

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE)
    print(f"[OK] Loaded {len(df)} existing parts.")
else:
    df = pd.DataFrame(columns=["Internal_PN", "Manufacturer", "Part_Number", "Category", "Rad_Hard", "Specs", "Project_History", "Status", "Datasheet_Link"])
    print("[OK] Created new database.")

def extract_parts(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Unknown"
        
        # Remove scripts/styles
        html_clean = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r'<style.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract part codes (2-4 letters + 2-6 digits)
        codes = re.findall(r'\b([A-Z]{2,4}\d{2,6}[A-Z]*)\b', html_clean)
        codes = list(dict.fromkeys(codes))[:25]  # Unique, limit to 25
        
        # Extract product names from headings
        headings = re.findall(r'<(?:h[1-4]|strong)>(.*?)</(?:h[1-4]|strong)>', html_clean, re.IGNORECASE)
        names = [re.sub(r'<[^>]+>', '', h).strip() for h in headings]
        names = [n for n in names if 5 < len(n) < 150 and 'menu' not in n.lower()][:25]
        
        all_parts = []
        for code in codes:
            all_parts.append({'id': code, 'type': 'code'})
        for name in names:
            all_parts.append({'id': name, 'type': 'name'})
        
        return title, all_parts
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return None, None

print("\n=== Bulk Load ===\n")
added = 0

for i, target in enumerate(SEED_URLS, 1):
    print(f"[{i}/3] {target['mfg']}: {target['url']}")
    title, parts = extract_parts(target['url'])
    
    if not parts:
        print(f"  [SKIP] Failed to extract parts.")
        continue
    
    print(f"  [OK] Found {len(parts)} items")
    
    for j, part in enumerate(parts):
        entry = {
            "Internal_PN": f"BULK-{target['mfg'].upper()}-{j+1:03d}",
            "Manufacturer": target['mfg'],
            "Part_Number": part['id'],
            "Category": target['category_hint'],
            "Rad_Hard": True,
            "Specs": f"From {title[:60]}",
            "Project_History": "Catalog Import",
            "Status": "Prototyping Only",
            "Datasheet_Link": target['url']
        }
        
        if entry['Part_Number'] not in df['Part_Number'].values:
            df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
            added += 1
            print(f"    [+] {part['id']}")
    
    time.sleep(1)

df.to_csv(DB_FILE, index=False)
print(f"\n[OK] Added {added} new parts. Total in DB: {len(df)}")
