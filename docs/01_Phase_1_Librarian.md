# Phase 1: The Component Librarian

## Objective
Build a module within the GDMS Space Hardware Assistant where an engineer can upload a component datasheet (PDF), have an LLM extract the critical electrical and thermal parameters, and format that data into a clean table ready for the Xpedition Databook.

## Step-by-Step Implementation Plan

### Step 1: Frontend (React) Repurposing
* Strip out the legacy consumer PC-Part Picker UI elements.
* Rebrand the UI to match the "GDMS Space Hardware Assistant" theme.
* Create a clean, single-page dashboard for the "Component Librarian".
* Implement a drag-and-drop file upload zone specifically for PDF datasheets.
* Build a data table component to display the extracted results (Columns needed: `Part_Number`, `Manufacturer`, `Value`, `Tolerance`, `Voltage_Rating`, `Package_Type`, `Pin_Count`, `Thermal_Resistance`).
* Add a "Push to Xpedition" button (disabled until data is populated).

### Step 2: Backend (FastAPI) Ingestion
* Create an endpoint `POST /api/upload-datasheet` that accepts the PDF file.
* Implement a basic PDF text extraction utility (using PyPDF2 or pdfplumber) to convert the PDF into a text string.

### Step 3: Enterprise AI Extraction Logic (OpenAI Compatible)
* Create an AI service layer in Python. Do NOT use the Google Gemini SDK. 
* Use the standard `openai` Python package so the app can be routed to an internal enterprise AI gateway later.
* Ensure the backend pulls `INTERNAL_API_KEY`, `INTERNAL_BASE_URL`, and `INTERNAL_MODEL_NAME` from a `.env` file.
* Define a strict Pydantic model (`ComponentData`) to enforce the schema for the data table columns.
* Use the OpenAI SDK with `response_format={"type": "json_object"}` and embed the Pydantic JSON schema into the system prompt to force the LLM to return valid JSON.
* Validate the LLM's raw JSON response against the Pydantic model before returning it to the React frontend.

### Step 4: Xpedition COM API Stub
* Create an endpoint `POST /api/push-to-databook` that accepts the verified JSON data from the frontend.
* For now, this endpoint should just generate a dummy Python script utilizing `win32com.client` intended to connect to `ViewDraw.Application` and print the data to the console.