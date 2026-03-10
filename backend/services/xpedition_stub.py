"""Xpedition Designer COM integration stub.

Implements the connection pattern from docs/xpedition_com_reference.md.
win32com.client is imported lazily inside the function so the module loads
cleanly on non-Windows machines and in CI test environments where pywin32
is not installed. Any failure (app not running, COM not found, ImportError)
is caught and returned as a 'simulation_only' response so the frontend
never receives an unhandled crash.
"""
import json


def simulate_xpedition_push(component_json_string: str) -> dict:
    """Attempts to connect to a running instance of Siemens Xpedition Designer
    and simulates pushing component data to the Databook.

    Args:
        component_json_string: JSON string of a single ComponentData record.

    Returns:
        dict with keys 'status' and 'message' (and optionally 'data_payload').
        status is 'success' when a live Xpedition instance was reached,
        'simulation_only' when it was not.
    """
    try:
        import win32com.client  # noqa: PLC0415 — intentional lazy import

        # Dispatch connects to the currently active ViewDraw (Xpedition Designer) instance
        vdapp = win32com.client.Dispatch("ViewDraw.Application")  # noqa: F841
        print("SUCCESS: Connected to Xpedition Designer (ViewDraw.Application)")

        data = json.loads(component_json_string)
        print(f"Simulating push for Part Number: {data.get('Part_Number')}")

        # Future implementation will interface with vdapp.GetProjectData() or Databook APIs

        return {"status": "success", "message": "Simulated push to Xpedition successful."}

    except Exception as e:
        # Triggers when Xpedition is not open, win32com is unavailable, or COM dispatch fails
        print("Xpedition Designer COM object not found. Is the application running?")
        print(f"Error: {str(e)}")

        return {
            "status": "simulation_only",
            "message": "Xpedition not running. Data logged to console.",
            "data_payload": json.loads(component_json_string),
        }
