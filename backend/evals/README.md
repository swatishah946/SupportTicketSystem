# How the AI features are checked

The AI suggestions are measured on a fixed set of sample tickets, so changes can be compared and
nothing is claimed without a number behind it. CI runs the no-API-key version on every push.

```bash
cd backend
python evals/run_eval.py                                    # keyword rules + word matching (no API key needed)
GEMINI_API_KEY=... python evals/run_eval.py --classifier llm --retriever hybrid   # Gemini
```

Results are saved to `evals/results/`.

## The sample tickets

`tickets.jsonl` has **96 tickets I wrote by hand: 24 different problems, each described 4 different ways**
(for example "charged twice", "two debits for one order", "billed 2x"). Each ticket is labelled with the right
category, the right priority and which problem it is.

**Be aware of the limits:**
- The tickets are made up, not real customer data, and the same person wrote the tickets and the labels.
- Priority is partly a matter of opinion, so "off by at most one level" is reported next to "exactly right".
- 96 tickets is a small sample: treat the numbers as a rough guide, not a precise score.

## What is measured, and the results without an API key

**1. Category and priority suggestions** (keyword-rule fallback, used when Gemini is unavailable)

| Question | Result |
|---|---|
| How often is the category right? | **83%** (80 of 96) |
| How often is the priority exactly right? | 66% |
| How often is the priority right or off by just one level? | **95%** |

**2. "You already reported this" warning** (word matching)

For each ticket, the other 95 are searched for the same problem described differently.

| Question | Result |
|---|---|
| Is the top match the same problem? | 58% of the time |
| False alarms: how often is an unrelated ticket flagged? | **6%** at the threshold the app uses |
| Missed duplicates at that threshold | about 70% are not flagged |

The threshold is deliberately strict. Telling a customer "you already reported this" when they didn't is worse than
missing a duplicate, so the app accepts missing many paraphrased duplicates to keep false alarms rare. Word matching
can't connect "charged twice" with "two debits" because they share no words. That is what the Gemini embeddings
(hybrid mode) are for: they compare meaning instead of words. Run the Gemini command above to measure that mode.

**An experiment I did not keep:** adding a hand-made synonym list raised the "top match" score from 58% to 79%.
I didn't ship it because I wrote the list after looking at these same tickets, so the improvement would mostly
reflect the test data rather than real use.
