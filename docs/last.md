That's a thorough audit. Let me work through all of these fixes systematically, starting with P0 and working down. First, let me understand the codebase structure.
Claude
Now let me read all the key files I need to modify:
Claude
Now let me read the remaining files I need:
Claude
Now let me read the frontend files:
Claude
Now let me read the remaining frontend pages to understand the duplicated components:
Claude
Let me read the remaining pages and key files:
Claude
Let me check a few more files I need:
Claude
Now I have a complete picture. Let me implement all fixes systematically. I'll start with the backend changes:

BATCH 1: P0 fixes + Backend P1/P2 fixes
Claude
Now create the shared AI client utility:
Claude
Now refactor all 7 files to use the shared client. Starting with ai_extractor.py:
Claude
Now update the router that calls extract_components_from_text to handle the new tuple return:
Claude
Now refactor the remaining 6 AI service files to use the shared client:
Claude
Now I need to check the constraint router to handle the tuple return too:
Claude
Now update block_diagram_generator.py: