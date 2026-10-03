# Developer Guide: Extending Intents and Entity Types

## Adding a New Investigation Intent

1. **Update Enum**:
   Add the new intent key to `InvestigationIntent` in `backend/app/models/enums.py`:
   ```python
   class InvestigationIntent(str, Enum):
       ...
       FINANCIAL_ANALYSIS = "FINANCIAL_ANALYSIS"
   ```

2. **Add Intent Heuristic Rule**:
   In `backend/app/nlp/intent_classifier.py`:
   ```python
   fin_keywords = {"bank", "wire", "transfer", "crypto", "bitcoin", "wallet", "transaction"}
   if any(k in query_lower for k in fin_keywords):
       return InvestigationIntentResult(
           type=InvestigationIntent.FINANCIAL_ANALYSIS,
           confidence=0.90,
           explanation="Financial transaction or currency transfer inquiry detected."
       )
   ```

3. **Update Query Planner**:
   In `backend/app/nlp/query_planner.py`, configure recommended search mode and filters for the intent.

4. **Add Benchmark Samples**:
   Add test queries to `backend/tests/evaluation/synthetic_nlp_dataset.json` and run `python scripts/evaluate_nlp_pipeline.py`.

---

## Adding a New Entity Type

1. **Update Enum**:
   Add the new entity type to `EntityType` in `backend/app/models/enums.py` and `frontend/src/types/investigation.ts`.

2. **Implement Extractor Pattern / Lexicon**:
   In `backend/app/nlp/entity_extractor.py`:
   - Define regex or dictionary mapping.
   - Implement `_extract_<new_entity>()` method.
   - Invoke in `extract_entities()`.

3. **Add Canonical Normalization**:
   In `backend/app/normalizers/entities.py`, add normalization logic to maintain data consistency.
