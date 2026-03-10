# Product Requirements Document (PRD): GDMS Space Hardware Assistant

## Overview
A modular, AI-augmented internal web application designed to accelerate digital hardware engineering workflows for space and mission systems. The tool bridges the gap between component research, schematic architecture, and physical layout by automating data formatting and directly interfacing with Siemens Xpedition Designer 2.13.

## Tech Stack
* **Frontend:** React (functional components, hooks) with Tailwind CSS for styling.
* **Backend:** Python with FastAPI.
* **AI Integration:** Google Gemini API (for high-context PDF parsing and data extraction).
* **Local Hardware Automation:** Python `win32com.client` for interacting with the Siemens Xpedition COM Object Model.

## Core Design Philosophy & Boundaries
1.  **No Spatial Guesswork:** The AI features will NEVER calculate physical routing coordinates (X/Y trace data). The AI's job is to calculate constraints, extract parameters, and format data. Xpedition handles the spatial geometry.
2.  **Modular Architecture:** The app is built in independent phases (Librarian, SI/PI Rules, FPGA Handoff). Ensure the backend routing and frontend navigation easily support adding new independent tools later.
3.  **The "Local Bridge" Concept:** Because the web app cannot directly touch a local desktop instance of Xpedition, the FastAPI backend will generate Python/VBScript files or JSON payloads that a local listener script will execute via `win32com`.

## Target User
Digital hardware engineers working on complex systems who need to quickly parse massive component datasheets, verify schematic integrity, and push clean, error-free data into the central Xpedition Databook and Constraint Editor System (CES).