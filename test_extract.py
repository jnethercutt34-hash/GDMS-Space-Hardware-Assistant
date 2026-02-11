#!/usr/bin/env python
import urllib.request
import re

def extract_parts(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        print(f"Fetching: {url}")
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        print(f"Downloaded {len(html)} bytes")
        
        # Extract part codes
        codes = re.findall(r'\b([A-Z]{2,4}\d{2,6}[A-Z]*)\b', html)
        codes = list(dict.fromkeys(codes))[:25]
        
        print(f"Found {len(codes)} part codes: {codes[:10]}")
        
        # Extract headings
        headings = re.findall(r'<(?:h[1-4]|strong)>(.*?)</(?:h[1-4]|strong)>', html, re.IGNORECASE)
        names = [re.sub(r'<[^>]+>', '', h).strip() for h in headings]
        names = [n for n in names if 5 < len(n) < 150][:25]
        
        print(f"Found {len(names)} product names: {names[:5]}")
        
        return codes + names
        
    except Exception as e:
        print(f"Error: {e}")
        return None

url = "https://www.renesas.com/us/en/products/space-harsh-environment"
parts = extract_parts(url)
print(f"\nTotal parts extracted: {len(parts) if parts else 0}")
