#!/usr/bin/env python
import sys
import traceback

print("Python executable:", sys.executable)
print("Python version:", sys.version)

try:
    print("\n1. Testing nest_asyncio...")
    import nest_asyncio
    nest_asyncio.apply()
    print("   ✓ nest_asyncio imported and applied")
except Exception as e:
    print(f"   ✗ nest_asyncio failed: {e}")
    traceback.print_exc()

try:
    print("\n2. Testing pandas...")
    import pandas as pd
    print("   ✓ pandas imported")
except Exception as e:
    print(f"   ✗ pandas failed: {e}")
    traceback.print_exc()

try:
    print("\n3. Testing scrapegraphai...")
    from scrapegraphai.graphs import SmartScraperGraph
    print("   ✓ scrapegraphai.graphs.SmartScraperGraph imported")
except Exception as e:
    print(f"   ✗ scrapegraphai failed: {e}")
    traceback.print_exc()

print("\n4. Attempting to read bulk_loader.py...")
try:
    with open('bulk_loader.py', 'r') as f:
        code = f.read()
    print(f"   ✓ bulk_loader.py read successfully ({len(code)} bytes)")
    
    print("\n5. Compiling bulk_loader.py...")
    compile(code, 'bulk_loader.py', 'exec')
    print("   ✓ bulk_loader.py compiles without syntax errors")
except Exception as e:
    print(f"   ✗ Error: {e}")
    traceback.print_exc()

print("\nTest complete!")
