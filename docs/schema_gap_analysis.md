# Sample job-ad schema coverage review

## Ads reviewed
- **StepStone – Senior Data Engineer:** Inline mission/profile section with bullets for ETL design and collaboration.【F:tests/test_extractors_url.py†L16-L41】
- **Rheinbahn – Produktentwickler HTML:** Overview paragraph under “Darauf kannst du dich freuen” plus tasks and requirements lists.【F:tests/fixtures/html/rheinbahn_produktentwickler.html†L24-L42】
- **Rheinbahn – Text snippet:** Short ad with benefit list and dual contacts (IT lead + HR).【F:tests/fixtures/text/rheinbahn_case.txt†L1-L7】

## Findings
- **Benefits coverage gap:** The Rheinbahn text lists perks such as flexible hours, mobile work, pension plan, and a transit ticket, but heuristics currently map them to `company.benefits`, leaving `compensation.benefits` empty in downstream consumers.【F:tests/fixtures/text/rheinbahn_case.txt†L3-L5】【F:tests/test_extraction_rheinbahn.py†L11-L35】
- **Role summary/context loss:** The StepStone and Rheinbahn HTML samples both open with short mission/impact paragraphs (“Your mission,” “Darauf kannst du dich freuen”) that describe the role’s purpose. If the extractor only records bullet responsibilities, that narrative context is dropped instead of flowing into `position.role_summary` (or `position.key_projects` for the product initiatives).【F:tests/test_extractors_url.py†L16-L40】【F:tests/fixtures/html/rheinbahn_produktentwickler.html†L24-L42】
- **Hiring manager vs. HR contact:** The Rheinbahn text names an IT leader and a separate HR contact, but fallback parsing populates only the company contact fields with the HR details, leaving `process.hiring_manager_name`/`process.hiring_manager_role` blank.【F:tests/fixtures/text/rheinbahn_case.txt†L3-L7】【F:tests/test_extraction_rheinbahn.py†L18-L35】

## Recommended follow-up tasks
- **Mirror perks into compensation:** Extend the benefit lexicon/prompt so perks found via headings or footer parsing are also written to `compensation.benefits` while keeping `company.benefits` for branding; add a post-extraction check to copy uncaptured perk lists from the raw text.【F:tests/fixtures/text/rheinbahn_case.txt†L3-L5】【F:tests/test_extraction_rheinbahn.py†L23-L35】
- **Capture mission snippets as role summaries:** Update extraction prompts or add a heuristic pass that funnels “Your mission”/“Darauf kannst du dich freuen” paragraphs into `position.role_summary`, and pull explicit initiative statements (e.g., “entwickelst du innovative Produkte …”) into `position.key_projects` when present.【F:tests/test_extractors_url.py†L31-L40】【F:tests/fixtures/html/rheinbahn_produktentwickler.html†L24-L37】
- **Split hiring and HR contacts:** Teach contact parsing to assign the first named leader (e.g., “IT-Leiter: Max Mustermann”) to `process.hiring_manager_name`/`process.hiring_manager_role` while preserving HR contact info under `company.*`; add regression coverage using the existing Rheinbahn text fixture.【F:tests/fixtures/text/rheinbahn_case.txt†L3-L7】【F:tests/test_extraction_rheinbahn.py†L18-L35】
