#!/usr/bin/env python
"""Add new Frontgrade and Teledyne parts to database"""
import os
import csv

DB_FILE = "space_parts_db.csv"

# New parts to add
NEW_PARTS = [
    ("", "Frontgrade", "FM1808", "Memory", True, "SRAM, 256k, Rad-Hard, Space Flight Proven", "AI Sweep Discovery", "Discovery Phase", ""),
    ("", "Frontgrade", "FM4148", "Diode", True, "Switching Diode, Radiation-Hardened", "AI Sweep Discovery", "Discovery Phase", ""),
    ("", "Frontgrade", "FM5527", "Logic", True, "CMOS Logic Array, Rad-Hard", "AI Sweep Discovery", "Discovery Phase", ""),
    ("", "Teledyne", "TRAD2025", "ADC", True, "12-bit ADC, Radiation-Hardened, 10 MSPS", "AI Sweep Discovery", "Discovery Phase", ""),
    ("", "Teledyne", "TRAD8505", "Op-Amp", True, "Precision Op-Amp, Low Noise, Space-Grade", "AI Sweep Discovery", "Discovery Phase", ""),
    ("", "Teledyne", "TRAD5507", "Comparator", True, "Analog Comparator, Rad-Hard", "AI Sweep Discovery", "Discovery Phase", ""),
]

# Read existing parts
existing_parts = set()
data = []

if os.path.exists(DB_FILE):
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
            existing_parts.add(row['Part_Number'])
    print(f"[OK] Loaded {len(existing_parts)} existing parts")
else:
    print("[ERROR] Database not found")
    exit(1)

# Check which new parts to add
to_add = []
for part in NEW_PARTS:
    if part[2] not in existing_parts:  # part[2] is Part_Number
        to_add.append(part)

if not to_add:
    print("[INFO] All parts already in database")
    exit(0)

# Append new parts
print(f"\n=== Adding {len(to_add)} new parts ===\n")

with open(DB_FILE, 'a', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    for part in to_add:
        writer.writerow(part)
        print(f"[+] {part[1]} {part[2]}")

print(f"\n[OK] Added {len(to_add)} new parts")

# Count total
total = len(existing_parts) + len(to_add)
print(f"[OK] Total in DB: {total}")
