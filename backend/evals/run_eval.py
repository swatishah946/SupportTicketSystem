"""Offline evaluation for NexusDesk's AI features.

    python evals/run_eval.py                  # rule-based baseline (no API key needed)
    python evals/run_eval.py --classifier llm --retriever hybrid   # Gemini (needs GEMINI_API_KEY)

Measures on evals/tickets.jsonl (96 hand-written tickets, 24 intents x 4 paraphrases):
  * triage: category accuracy + macro-F1, priority exact accuracy and within-one-level
  * duplicate detection (lexical TF-IDF cosine, or hybrid with Gemini embeddings):
      - hit@1 / hit@3: is a paraphrase of the same issue ranked first / in the top 3
      - at each score threshold: recall (true duplicates flagged) and false-positive rate,
        where the FPR is measured leave-intent-out: every ticket of the query's intent is
        removed from the corpus, so any flag is by construction a false alarm.

Results are written to evals/results/<classifier>-<retriever>.json. See evals/README.md for caveats.
"""

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")
os.environ.setdefault("DEBUG", "True")

import django  # noqa: E402

django.setup()

from tickets.services import ai  # noqa: E402
from tickets.services.rules import classify_rules  # noqa: E402
from tickets.services.search import rank  # noqa: E402

CATEGORIES = ["billing", "technical", "account", "general"]
PRIORITIES = ["low", "medium", "high", "critical"]
THRESHOLDS = [0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8]


def load():
    with open(HERE / "tickets.jsonl") as f:
        return [json.loads(line) for line in f]


def text(t):
    return f"{t['title']} {t['title']} {t['description']}"


def macro_f1(pairs, labels):
    f1s = []
    for label in labels:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if g != label and p == label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0)
    return sum(f1s) / len(f1s)


def evaluate_triage(rows, classifier):
    cat_pairs, pri_pairs, latencies, sources = [], [], [], Counter()
    for r in rows:
        if classifier == "rules":
            start = time.perf_counter()
            pred = classify_rules(f"{r['title']}\n{r['description']}")
            latencies.append((time.perf_counter() - start) * 1000)
            sources["rules"] += 1
        else:
            pred = ai.classify(r["title"], r["description"])
            latencies.append(pred["latency_ms"])
            sources[pred["source"]] += 1
        cat_pairs.append((r["category"], pred["category"]))
        pri_pairs.append((r["priority"], pred["priority"]))

    n = len(rows)
    within_one = sum(abs(PRIORITIES.index(g) - PRIORITIES.index(p)) <= 1 for g, p in pri_pairs)
    confusion = defaultdict(Counter)
    for g, p in cat_pairs:
        confusion[g][p] += 1
    latencies.sort()
    return {
        "n": n,
        "sources": dict(sources),
        "category_accuracy": round(sum(g == p for g, p in cat_pairs) / n, 3),
        "category_macro_f1": round(macro_f1(cat_pairs, CATEGORIES), 3),
        "priority_accuracy": round(sum(g == p for g, p in pri_pairs) / n, 3),
        "priority_within_one": round(within_one / n, 3),
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(latencies[int(0.95 * (n - 1))], 2),
        "category_confusion": {g: dict(confusion[g]) for g in CATEGORIES},
    }


def evaluate_duplicates(rows, retriever):
    kwargs = {}
    if retriever == "hybrid":
        for r in rows:
            r["embedding"] = ai.embed(f"{r['title']}\n{r['description']}")
        missing = sum(r["embedding"] is None for r in rows)
        if missing:
            sys.exit(f"{missing} embeddings failed; check GEMINI_API_KEY / quota.")
        kwargs = {"embedding_of": lambda r: r["embedding"]}
    hit1 = hit3 = 0
    top_true, top_false = [], []
    for r in rows:
        query = f"{r['title']} {r['description']}"
        if kwargs:
            kwargs["query_embedding"] = r["embedding"]
        others = [o for o in rows if o["id"] != r["id"]]
        ranked = rank(query, others, text, top_k=3, **kwargs)
        if ranked and ranked[0][0]["intent"] == r["intent"]:
            hit1 += 1
        if any(o["intent"] == r["intent"] for o, _ in ranked):
            hit3 += 1
        # best score of a true duplicate when present
        true_scores = [s for o, s in ranked if o["intent"] == r["intent"]]
        top_true.append(max(true_scores) if true_scores else 0.0)
        # leave-intent-out: no true duplicate exists, any flag is a false positive
        negatives = [o for o in rows if o["intent"] != r["intent"]]
        neg_ranked = rank(query, negatives, text, top_k=1, **kwargs)
        top_false.append(neg_ranked[0][1] if neg_ranked else 0.0)

    n = len(rows)
    sweep = []
    for tau in THRESHOLDS:
        recall = sum(s >= tau for s in top_true) / n
        fpr = sum(s >= tau for s in top_false) / n
        sweep.append({"threshold": tau, "duplicate_recall": round(recall, 3), "false_positive_rate": round(fpr, 3)})
    return {
        "n": n, "retriever": retriever, "hit_at_1": round(hit1 / n, 3), "hit_at_3": round(hit3 / n, 3),
        "threshold_sweep": sweep,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifier", choices=["rules", "llm"], default="rules")
    parser.add_argument("--retriever", choices=["lexical", "hybrid"], default="lexical")
    args = parser.parse_args()
    needs_key = args.classifier == "llm" or args.retriever == "hybrid"
    if needs_key and not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY to evaluate the LLM classifier or hybrid retrieval.")

    rows = load()
    result = {
        "dataset": "evals/tickets.jsonl",
        "classifier": args.classifier,
        "triage": evaluate_triage(rows, args.classifier),
        "duplicates": evaluate_duplicates(rows, args.retriever),
    }
    out = HERE / "results" / f"{args.classifier}-{args.retriever}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")

    t, d = result["triage"], result["duplicates"]
    print(f"Triage ({args.classifier}, n={t['n']}, sources={t['sources']})")
    print(f"  category accuracy {t['category_accuracy']:.1%}  macro-F1 {t['category_macro_f1']:.3f}")
    print(f"  priority accuracy {t['priority_accuracy']:.1%}  within one level {t['priority_within_one']:.1%}")
    print(f"  latency p50 {t['latency_ms_p50']} ms  p95 {t['latency_ms_p95']} ms")
    print(f"Duplicate detection ({args.retriever}, n={d['n']})  hit@1 {d['hit_at_1']:.1%}  hit@3 {d['hit_at_3']:.1%}")
    for row in d["threshold_sweep"]:
        print(f"  tau={row['threshold']:.2f}  recall {row['duplicate_recall']:.1%}  "
              f"false positives {row['false_positive_rate']:.1%}")
    print(f"Wrote {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
