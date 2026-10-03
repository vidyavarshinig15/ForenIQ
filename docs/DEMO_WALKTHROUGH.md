# Demonstration Guide — Synthetic Forensic Case Walkthrough

**Case Title**: Operation Apex — Multi-Device Financial Conduit Investigation  
**Case Number**: `CASE-E2E-APEX2026`  

---

## Step 1: User Authentication & Role-Based Dashboard
1. Navigate to `http://localhost:5173/login`.
2. Login as the Lead Forensic Investigator:
   - **Email**: `lead_investigator@ufdr.org`
   - **Password**: `ForensicPass2026!Strict`
   - **Role**: `INVESTIGATOR`
3. The Dashboard displays active cases, storage health, queue throughput, and worker heartbeat indicators.

---

## Step 2: Case Creation & Evidence Ingestion
1. Click **"New Investigation Case"**.
2. Set Case Number `CASE-E2E-APEX2026` and Title *"Operation Apex Multi-Device Analysis"*.
3. Navigate into the case and click **"Upload Evidence Package"**.
4. Select the synthetic archive: `backend/tests/evaluation/synthetic_multidevice_ground_truth.json` or sample UFDR ZIP.
5. Review the immediate cryptographic verification:
   - **SHA-256 Digest**: Computed on streaming upload.
   - **Chain-of-Custody Event**: Recorded with timestamp, actor ID, and upload signature.

---

## Step 3: Automated Streaming Parsing & Normalization
1. Click **"Parse Evidence"** to trigger the streaming XML ingestion worker.
2. Observe live progress indicator tracking artifact parsing.
3. Click **"Normalize Evidence"** to trigger the deterministic normalization engine:
   - Converts raw records into `CanonicalEvidence`.
   - Resolves phone numbers to international E.164 standard (`+15550101`).
   - Generates deterministic SHA-256 canonical fingerprints.

---

## Step 4: Multi-Modal Forensic Search
1. **Exact Search**: Enter `"APEX-LUX-9012"` in Exact Search mode. Instant exact hit on WhatsApp chat record.
2. **Lexical Search**: Enter `"Swiss bank"` to retrieve all banking references across chats, browser history, and contacts.
3. **Semantic / Hybrid Search**: Query `"offshore corporate assets"` to retrieve contextual records based on embedding vector similarity.

---

## Step 5: Natural Language Query & RAG Assistant
1. In the **Investigation Assistant**, enter natural language questions:
   - *"Show communications between Alex Mercer and Jordan Vance regarding banking"*
   - The NLP engine parses intent `COMMUNICATION_ANALYSIS` and builds a dynamic query plan.
2. Ask: *"What is the routing key for the offshore holding?"*
3. The RAG assistant provides an evidence-grounded response with verifiable citations `[CIT-001]` referencing primary artifacts.
4. If asked an unsupported question (e.g. *"Who murdered the witness?"*), the system outputs *"Insufficient evidence"*.

---

## Step 6: Communication Graph & Social Network Analytics
1. Navigate to the **Graph Analytics** tab.
2. Observe the interactive node-link network visualization (Alex Mercer, Jordan Vance, Casey Reed).
3. Inspect centrality metrics (Degree, Betweenness, Closeness, PageRank) and community clusters.

---

## Step 7: Multi-Source Timeline & Statistical Anomaly Detection
1. Switch to the **Timeline** view to examine chronological events across calls, chats, locations, and web history.
2. Click **"Detect Anomalies"** (window size `1h`, contamination `0.05`).
3. The Isolation Forest model highlights statistically unusual bursts with factual statistical baselines (e.g., *18 events within 15 minutes during off-hours*).

---

## Step 8: Structured Report Generation & Export
1. Click **"Generate Forensic Report"**.
2. Select all sections (Evidence Inventory, Chain of Custody, Timeline, Graph Analysis, Anomalies, RAG Findings).
3. Review the DRAFT report with verifiable citations.
4. Click **"Approve Report"** (locks version to APPROVED).
5. Click **"Export PDF"** / **"Export JSON"** / **"Export CSV"**:
   - Download court-ready PDF featuring header `X-Report-SHA256` for courtroom tamper-verification.
