"""
BOM Analyzer - Upload Bill of Materials and find competitive alternatives
Analyzes user's BOM parts and suggests equivalent/competing parts in database
"""

import csv
import os
from io import StringIO

DB_FILE = "space_parts_db.csv"

def load_database():
    """Load entire database into memory."""
    parts_by_key = {}
    parts_by_category = {}
    
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['Manufacturer'], row['Part_Number'])
                parts_by_key[key] = row
                
                # Index by category
                cat = row['Category']
                if cat not in parts_by_category:
                    parts_by_category[cat] = []
                parts_by_category[cat].append(row)
    
    return parts_by_key, parts_by_category

def parse_bom(bom_content):
    """Parse BOM CSV content and extract parts."""
    try:
        reader = csv.DictReader(StringIO(bom_content))
        parts = []
        for row in reader:
            # Support various column names
            mfg = row.get('Manufacturer') or row.get('Mfg') or row.get('Maker') or ''
            pn = row.get('Part_Number') or row.get('Part Number') or row.get('PN') or ''
            qty = row.get('Quantity') or row.get('Qty') or '1'
            desc = row.get('Description') or row.get('Desc') or ''
            
            if mfg.strip() and pn.strip():
                parts.append({
                    'manufacturer': mfg.strip(),
                    'part_number': pn.strip(),
                    'quantity': int(qty) if qty.isdigit() else 1,
                    'description': desc.strip()
                })
        return parts
    except Exception as e:
        return None, f"Error parsing BOM: {str(e)}"
    
    return parts, None

def find_competitors(part_row, parts_by_category):
    """Find competing parts in same category (excluding the part itself)."""
    category = part_row.get('Category', '')
    if not category or category not in parts_by_category:
        return []
    
    competitors = []
    part_key = (part_row['Manufacturer'], part_row['Part_Number'])
    
    for candidate in parts_by_category[category]:
        candidate_key = (candidate['Manufacturer'], candidate['Part_Number'])
        # Exclude the part itself
        if candidate_key != part_key:
            competitors.append(candidate)
    
    # Sort by status (Flight Proven first)
    competitors.sort(key=lambda x: (x.get('Status', '') != 'Flight Proven', x['Manufacturer']))
    
    return competitors[:5]  # Return top 5 competitors

def analyze_bom(bom_content):
    """Analyze BOM and return matched parts with competitors."""
    # Parse BOM
    bom_parts, error = parse_bom(bom_content)
    if error:
        return None, error
    
    if not bom_parts:
        return None, "No parts found in BOM"
    
    # Load database
    parts_by_key, parts_by_category = load_database()
    
    # Analyze each BOM part
    analysis = []
    missing_parts = []
    
    for bom_part in bom_parts:
        key = (bom_part['manufacturer'], bom_part['part_number'])
        
        if key in parts_by_key:
            # Part found in database
            db_part = parts_by_key[key]
            competitors = find_competitors(db_part, parts_by_category)
            
            analysis.append({
                'status': 'FOUND',
                'bom_part': bom_part,
                'db_part': db_part,
                'competitors': competitors
            })
        else:
            # Part not found - mark for addition
            missing_parts.append(bom_part)
            analysis.append({
                'status': 'NOT_FOUND',
                'bom_part': bom_part,
                'db_part': None,
                'competitors': []
            })
    
    return analysis, missing_parts

def add_missing_bom_parts(missing_parts, program_name=""):
    """Add missing parts from BOM to database."""
    if not missing_parts:
        return 0
    
    # Append to database
    with open(DB_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Internal_PN", "Manufacturer", "Part_Number", "Category",
            "Rad_Hard", "Specs", "Project_History", "Status", "Datasheet_Link"
        ])
        
        for part in missing_parts:
            # Auto-detect category based on part number hints
            pn = part['part_number'].upper()
            if 'DDR' in pn or 'SRAM' in pn or 'FLASH' in pn or 'MRAM' in pn:
                category = 'Memory'
            elif 'FPGA' in pn or 'ASIC' in pn:
                category = 'FPGA'
            elif 'ADC' in pn or 'DAC' in pn or 'AMP' in pn or 'OPA' in pn:
                category = 'Analog'
            elif 'MCU' in pn or 'STM' in pn or 'RH' in pn:
                category = 'Microcontroller'
            else:
                category = 'Other'
            
            # Use program name if provided, otherwise use generic label
            project_history = f"BOM Import - {program_name}" if program_name.strip() else "BOM Import"
            
            writer.writerow({
                'Internal_PN': '',
                'Manufacturer': part['manufacturer'],
                'Part_Number': part['part_number'],
                'Category': category,
                'Rad_Hard': '',  # User will need to verify
                'Specs': part.get('description', ''),
                'Project_History': project_history,
                'Status': 'BOM Entry - Needs Verification',
                'Datasheet_Link': ''
            })
    
    return len(missing_parts)

def generate_comparison_report(analysis):
    """Generate a comparison report for BOM parts."""
    report = []
    
    for item in analysis:
        if item['status'] == 'FOUND':
            bom = item['bom_part']
            db = item['db_part']
            competitors = item['competitors']
            
            report.append({
                'part_number': f"{bom['manufacturer']} {bom['part_number']}",
                'quantity': bom['quantity'],
                'found': True,
                'specs': db.get('Specs', ''),
                'status': db.get('Status', ''),
                'category': db.get('Category', ''),
                'competitors': [
                    {
                        'name': f"{c['Manufacturer']} {c['Part_Number']}",
                        'specs': c.get('Specs', ''),
                        'status': c.get('Status', ''),
                        'category': c.get('Category', '')
                    } for c in competitors
                ]
            })
        else:
            bom = item['bom_part']
            report.append({
                'part_number': f"{bom['manufacturer']} {bom['part_number']}",
                'quantity': bom['quantity'],
                'found': False,
                'specs': bom.get('description', 'Unknown'),
                'status': 'Not in Database',
                'category': 'Unknown',
                'competitors': []
            })
    
    return report
