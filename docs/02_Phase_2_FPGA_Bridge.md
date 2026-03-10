# Phase 2: The FPGA I/O Pin-Swap Bridge

## Objective
Build a module within the GDMS Space Hardware Assistant that automates the handoff between the FPGA team (Vivado) and the Board team (Xpedition). It will ingest pinout CSVs, calculate the deltas (swaps), use AI to flag SI/PI risks, and format the output for Xpedition I/O Designer.

## Step-by-Step Implementation Plan

### Step 1: Frontend (React) Architecture
* Update the main app navigation to include a sidebar or tab system routing between "Component Librarian" and "FPGA I/O Bridge".
* Build a dashboard for the FPGA tool featuring TWO drag-and-drop zones:
  1. `Baseline Pinout CSV` (The current state of the Xpedition schematic).
  2. `New Vivado CSV` (The updated export from the FPGA team).
* Create a delta data table to display the results. Columns needed: `Signal_Name`, `Old_Pin`, `New_Pin`, `Old_Bank`, `New_Bank`, and `AI_Risk_Assessment`.

### Step 2: Backend (FastAPI) Delta Engine
* Create an endpoint `POST /api/compare-fpga-pins` that accepts both CSV files via multipart form data.
* Write a Python utility (using `pandas` or the standard `csv` module) that compares the two files based on the `Signal_Name` column.
* The utility must filter out all unchanged pins and return a JSON array containing ONLY the pins that have moved to a new physical location.

### Step 3: Enterprise AI Risk Assessment
* Pass the JSON array of swapped pins to the Enterprise AI service layer created in Phase 1 (using the OpenAI SDK).
* Create a new System Prompt for the AI instructing it to act as an SI/PI engineer. 
* The AI's job is to analyze the swaps and flag risks (e.g., "Low Risk: Pin moved within the same bank" vs. "High Risk: High-speed signal moved to a different bank, potential timing skew").
* Append this risk assessment string to each pin object before returning the final payload to the React frontend.

### Step 4: Xpedition I/O Designer Export
* Add a button to the frontend: "Export Xpedition Update Script".
* Create a backend endpoint that takes the delta JSON and generates a `.vbs` or `.py` script string (using `win32com.client`) designed to locate those specific symbols on the ViewDraw schematic and update their pin properties.
* Allow the user to download this script.