import nest_asyncio
import json
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from scrapegraphai.graphs import SmartScraperGraph

nest_asyncio.apply()

# --- STEP 1: The "Tiered" Schema ---
class SpaceComponent(BaseModel):
    manufacturer: str
    part_number: str
    category: Literal["Processing", "Memory", "Comms", "Power", "Clocking", "Other"]
    
    # The New "Space Relevance" Logic
    relevance_tier: Literal["Tier 1: Rad-Hard", "Tier 2: High-Rel/Space-Capable", "Tier 3: Commercial Potential"] = Field(
        ..., 
        description="Tier 1 = Explicitly Rad-Hard/QML-V. Tier 2 = Enhanced Product, Automotive, or Ruggedized. Tier 3 = Commercial but high-performance."
    )
    space_promise_reason: str = Field(
        ..., 
        description="Why is this relevant? E.g., 'Uses GaN technology', 'AEC-Q100 Qualified', 'Ceramic Package', or 'Native Rad-Hard'."
    )
    
    # Technical Specs
    tid_krad: Optional[float] = Field(None, description="Total Ionizing Dose (if available)")
    key_spec: str = Field(..., description="The main spec (e.g., '28Gbps', '100k Logic Cells')")
    datasheet_url: str

# --- STEP 2: The "Extensive" Prompt ---
def sweep_manufacturer_tiered(url: str):
    prompt = """
    Analyze the components on this page for Space Relevance. 
    
    You are looking for three types of parts:
    1. **Tier 1 (Gold Standard):** Explicitly labeled 'Rad-Hard', 'Space-Grade', 'QML-V', or 'RHA'.
    2. **Tier 2 (Silver Standard):** Parts labeled 'Enhanced Product (EP)', 'Military Grade', 'Hi-Rel', or 'Automotive Qualified (AEC-Q100)'.
    3. **Tier 3 (Bronze Standard):** Commercial parts that show promise for space due to specific technologies. Look specifically for:
       - **GaN (Gallium Nitride)** or **SiC (Silicon Carbide)** materials (inherently rad-tolerant).
       - **Ceramic** or **Hermetic** packaging.
       - **Wide Temperature Ranges** (-55C to +125C).
    
    Extract the part details and strictly categorize them into one of these three tiers. 
    In the 'space_promise_reason' field, explain WHY you selected it (e.g., 'GaN FETs have high SEL immunity').
    """
    
    # Configure the AI
    graph_config = {
        "llm": {
            "api_key": "YOUR_GEMINI_API_KEY",
            "model": "google_genai/gemini-1.5-pro",
            "temperature": 0.1, # Keep it strict
        },
    }
    
    # Run the Sweep
    smart_graph = SmartScraperGraph(
        prompt=prompt,
        source=url,
        config=graph_config,
        schema=List[SpaceComponent]
    )

    return smart_graph.run()

# --- STEP 3: Test Run (Example: EPC Space or TI HiRel) ---
# Let's test it on a site that mixes Space and "High Rel" parts
target_url = "https://epc-co.com/epc/products/gan-fets-and-ics" 
# (EPC makes GaN FETs which are great for space but often start as commercial)

print(f"Sweeping {target_url} for Space Relevance...")
results = sweep_manufacturer_tiered(target_url)

print(json.dumps(results, indent=2))