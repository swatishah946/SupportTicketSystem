# Evaluating NexusDesk's AI features

The AI features are measured, not assumed. `run_eval.py` scores them against a
labelled dataset, and CI runs the key-free baseline on every push.

```bash
cd backend
python evals/run_eval.py                                     # rule-based triage + lexical retrieval
GEMINI_API_KEY=... python evals/run_eval.py --classifier llm --retriever hybrid
```

Results land in `evals/results/<classifier>-<retriever>.json`.

## Dataset

`tickets.jsonl` holds **96 hand-written tickets: 24 distinct issues × 4 paraphrases**.
Each ticket is labelled with a category, a priority and an intent (the issue it is about).
The paraphrases deliberately vary vocabulary ("charged twice" / "two debits" / "billed 2x"),
because that is what makes duplicate detection hard.

**Caveats, stated up front:**
- The tickets are synthetic and written by the project author, not production data.
- Priority labels follow the rubric in `CLASSIFY_SYSTEM` (see `tickets/services/ai.py`).
  Priority is partly subjective, so "within one level" is reported alongside exact match.
- The rule-based classifier was written before the dataset existed and was not tuned on it.
- A synonym-expansion experiment raised duplicate hit@1 from 58% to 79% on this set.
  It was **not** shipped, because the synonym list was written after seeing this data and
  its score would be overfit. Semantic embeddings (hybrid mode) are the principled fix.

## Metrics

| Task | Metric | Meaning |
|---|---|---|
| Triage | category accuracy, macro-F1 | 4 classes; macro-F1 weights each class equally |
| Triage | priority accuracy, within-one | exact level, and at most one level off (e.g. high vs critical) |
| Duplicates | hit@1, hit@3 | a paraphrase of the same issue is ranked 1st / in the top 3 |
| Duplicates | recall @ τ | share of tickets whose true duplicate scores ≥ τ (would be flagged) |
| Duplicates | false-positive rate @ τ | *leave-intent-out*: all tickets of the query's issue are removed, so any flag is wrong |

## Results (rule-based triage, lexical TF-IDF retrieval, no API key)

| Metric | Value |
|---|---|
| Category accuracy | **83.3%** (macro-F1 0.839) |
| Priority exact / within one level | 65.6% / **94.8%** |
| Classification latency p50 | 0.25 ms |
| Duplicate hit@1 / hit@3 | 58.3% / 66.7% |
| At τ = 0.30 (shipped default) | recall 29.2%, false positives **6.2%** |

The duplicate warning uses a conservative threshold on purpose. A false "you already
reported this" is worse than a missed one, so the default favours precision
(6% false alarms) over recall.

Lexical retrieval cannot match paraphrases that share no words. That is the job of
hybrid mode, which blends Gemini embeddings (70%) with TF-IDF (30%). Run it with a key
and set `DUPLICATE_THRESHOLD_HYBRID` from the sweep it prints.
