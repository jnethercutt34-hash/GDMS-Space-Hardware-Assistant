import streamlit as st
import pandas as pd
import os
import subprocess
from bom_analyzer import analyze_bom, add_missing_bom_parts, generate_comparison_report

st.set_page_config(
    page_title="Space Parts Intelligence",
    page_icon="[SPACE]",
    layout="wide"
)

DB_FILE = "space_parts_db.csv"
DATASHEETS_DIR = "datasheets"
CHANGELOG_FILE = "parts_changelog.csv"

# Create datasheets directory if it doesn't exist
os.makedirs(DATASHEETS_DIR, exist_ok=True)

def run_ai_sweeper():
    """Run the AI Sweeper to discover new parts."""
    try:
        result = subprocess.run(
            ["python", "ai_sweeper.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "[ERROR] AI Sweeper timed out"
    except Exception as e:
        return f"[ERROR] Failed to run AI Sweeper: {str(e)}"

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        return df.fillna("")
    return pd.DataFrame()

def get_datasheet_path(manufacturer, part_number):
    """Returns the path to a datasheet folder for a part."""
    # Organize by manufacturer/part_number
    return os.path.join(DATASHEETS_DIR, manufacturer.replace(" ", "_"), f"{part_number}")

def datasheet_exists(manufacturer, part_number):
    """Check if datasheet folder/files exist for a part."""
    path = get_datasheet_path(manufacturer, part_number)
    if os.path.isdir(path):
        # Check if there are any files in the folder
        files = os.listdir(path)
        return len(files) > 0
    return False

def get_datasheet_files(manufacturer, part_number):
    """Get list of files in datasheet folder."""
    path = get_datasheet_path(manufacturer, part_number)
    if os.path.isdir(path):
        return os.listdir(path)
    return []

def load_changelog():
    """Load recent changes from changelog."""
    if os.path.exists(CHANGELOG_FILE):
        try:
            df = pd.read_csv(CHANGELOG_FILE)
            # Sort by timestamp descending and return last 10
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            return df.sort_values('Timestamp', ascending=False).head(10)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

df = load_data()

st.title("🚀 Space Parts")
st.markdown(f"**Database:** {len(df)} radiation-hardened components")

# Sidebar Filters
st.sidebar.header("Filters")

# AI Sweeper Tool
if st.sidebar.button("🔍 Run AI Sweeper", use_container_width=True, help="Search internet for new space components"):
    with st.spinner("Running AI Sweeper... checking manufacturer sources..."):
        output = run_ai_sweeper()
        st.sidebar.success("✓ Sweep complete!")
        with st.sidebar.expander("Sweep Results"):
            st.text(output)
        st.rerun()

st.sidebar.divider()
if len(df) > 0:
    categories = ["All"] + sorted(df['Category'].unique().tolist())
    selected_cat = st.sidebar.selectbox("Category", categories)
    
    # Add program filter
    programs = ["All"] + sorted([p for p in df['Project_History'].unique().tolist() if p and p.strip()])
    selected_prog = st.sidebar.selectbox("Program", programs)
    
    rad_hard_only = st.sidebar.checkbox("Rad-Hard Only")
    missing_datasheet = st.sidebar.checkbox("Missing Datasheets Only")
    
    # Filtering
    filtered_df = df.copy()
    if selected_cat != "All":
        filtered_df = filtered_df[filtered_df['Category'] == selected_cat]
    if selected_prog != "All":
        filtered_df = filtered_df[filtered_df['Project_History'].str.contains(selected_prog, case=False, na=False)]
    if rad_hard_only:
        filtered_df = filtered_df[filtered_df['Rad_Hard'] == True]
    if missing_datasheet:
        filtered_df = filtered_df[~filtered_df.apply(
            lambda row: datasheet_exists(row['Manufacturer'], row['Part_Number']), 
            axis=1
        )]
    
    # Search
    search = st.text_input("Search...", "")
    if search:
        mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        filtered_df = filtered_df[mask]
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", len(df))
    col2.metric("Filtered", len(filtered_df))
    col3.metric("Flight Proven", len(df[df['Status'] == 'Flight Proven']))
    missing_count = sum(~df.apply(lambda row: datasheet_exists(row['Manufacturer'], row['Part_Number']), axis=1))
    col4.metric("Missing Datasheets", missing_count)
    
    st.divider()
    
    # Display with datasheet status
    st.subheader("Components")
    
    if len(filtered_df) > 0:
        # Create display dataframe with datasheet status
        display_df = filtered_df.copy()
        
        # Add datasheet status column
        datasheet_status = []
        for idx, row in filtered_df.iterrows():
            if datasheet_exists(row['Manufacturer'], row['Part_Number']):
                files = get_datasheet_files(row['Manufacturer'], row['Part_Number'])
                status = f"[Datasheet Available ({len(files)} file{'s' if len(files) > 1 else ''})]"
            else:
                status = "[Datasheet Missing]"
            datasheet_status.append(status)
        
        display_df['Datasheet'] = datasheet_status
        
        # Display columns
        display_cols = ['Manufacturer', 'Part_Number', 'Category', 'Specs', 'Status', 'Datasheet']
        display_cols = [c for c in display_cols if c in display_df.columns]
        
        st.dataframe(display_df[display_cols], use_container_width=True, hide_index=True, height=400)
        
        # Export
        csv = filtered_df.to_csv(index=False)
        st.download_button("Download CSV", csv, "space_parts.csv", "text/csv")
    else:
        st.info("No parts match your filters.")
else:
    st.info("Database empty. Run: `py bulk_loader_v4.py`")

# Recent Changes Section
st.divider()
st.subheader("Recent Updates")

changelog = load_changelog()
if len(changelog) > 0:
    # Display changelog with colors for different change types
    for idx, row in changelog.iterrows():
        timestamp = row['Timestamp']
        mfg = row['Manufacturer']
        pn = row['Part_Number']
        change_type = row['Change_Type']
        old_val = row['Old_Value']
        new_val = row['New_Value']
        
        if change_type == "New_Part":
            st.success(f"✓ **New Part** | {mfg} {pn} | {timestamp}")
        elif change_type == "Specs":
            st.info(f"ℹ **Specs Updated** | {mfg} {pn} | {timestamp}\n`{old_val}` → `{new_val}`")
        elif change_type == "Status":
            st.warning(f"⚠ **Status Changed** | {mfg} {pn} | {timestamp}\n`{old_val}` → `{new_val}`")
        else:
            st.info(f"◆ **{change_type}** | {mfg} {pn} | {timestamp}")
else:
    st.info("No recent changes. Run AI Sweeper to discover updates.")

# BOM Analyzer Section
st.divider()
st.subheader("📋 BOM Analyzer")

st.markdown("""
Upload a Bill of Materials (CSV) with your manufacturer part numbers. The tool will:
1. **Identify** which parts are in our database
2. **Find competitors** - alternative parts in the same category
3. **Add missing parts** from your BOM for future reference
""")

# Program input
program_name = st.text_input("Program Name (for BOM parts)", placeholder="e.g., Project X, Mission Alpha", help="This will be added to the Project_History field for new parts")

bom_file = st.file_uploader("Upload BOM File (CSV)", type="csv", key="bom_upload")

if bom_file:
    # Read BOM content
    bom_content = bom_file.read().decode('utf-8')
    
    # Analyze BOM
    analysis, missing_parts = analyze_bom(bom_content)
    
    if analysis is None:
        st.error(f"Error analyzing BOM: {missing_parts}")
    else:
        # Generate report
        report = generate_comparison_report(analysis)
        
        # Summary metrics
        found_count = sum(1 for item in report if item['found'])
        missing_count = len([item for item in report if not item['found']])
        total_qty = sum(item['quantity'] for item in report)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("BOM Parts", len(report))
        col2.metric("Found in DB", found_count)
        col3.metric("Not Found", missing_count)
        col4.metric("Total Quantity", total_qty)
        
        st.divider()
        
        # Display BOM analysis
        st.subheader("BOM Analysis & Competition")
        
        for item in report:
            pn_display = item['part_number']
            qty = item['quantity']
            
            if item['found']:
                st.success(f"✓ **{pn_display}** (Qty: {qty})")
                st.caption(f"Category: `{item['category']}` | Status: `{item['status']}`")
                st.write(f"**Specs:** {item['specs']}")
                
                if item['competitors']:
                    st.write("**Competitive Alternatives:**")
                    for comp in item['competitors']:
                        st.write(f"- `{comp['name']}` - {comp['specs'][:80]}... ({comp['status']})")
            else:
                st.warning(f"⚠ **{pn_display}** (Qty: {qty}) - NOT IN DATABASE")
                st.caption(f"Status: {item['status']}")
                if item['specs']:
                    st.write(f"**Description:** {item['specs']}")
        
        st.divider()
        
        # Option to add missing parts
        if missing_count > 0:
            if st.button("📥 Add Missing Parts to Database", use_container_width=True):
                added = add_missing_bom_parts(missing_parts, program_name)
                st.success(f"Added {added} parts from BOM to database!")
                st.info(f"New parts added with Program: '{program_name}' | Status: 'BOM Entry - Needs Verification'")
                st.rerun()
        
        # Export analysis
        st.divider()
        analysis_df = pd.DataFrame(report)
        csv = analysis_df.to_csv(index=False)
        st.download_button("Download Analysis", csv, "bom_analysis.csv", "text/csv")

