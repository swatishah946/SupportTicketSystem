"""Deterministic rule-based classifier.

This is the fallback when the LLM is unavailable (no key, timeout, quota) and
the baseline the LLM is measured against in `evals/`. Keeping a baseline makes
it possible to show the LLM actually adds value rather than assuming it does.
"""

import re

CATEGORY_KEYWORDS = {
    "billing": {
        3: ["refund", "invoice", "charged", "charge", "billing", "payment", "subscription", "overcharged",
            "receipt", "gst", "tax invoice", "credit card", "debit card", "upi", "plan price", "renewal"],
        1: ["price", "pricing", "paid", "pay", "money", "cost", "discount", "coupon", "trial", "upgrade", "downgrade",
            "cancel my plan", "billed", "fee", "amount"],
    },
    "account": {
        3: ["password", "login", "log in", "sign in", "signin", "2fa", "two-factor", "otp", "locked out",
            "account locked", "reset link", "verification email", "delete my account", "deactivate",
            "change my email", "username", "profile"],
        1: ["account", "email address", "sso", "permissions", "access", "role", "invite", "team member"],
    },
    "technical": {
        3: ["error", "crash", "crashes", "bug", "500", "404", "timeout", "not loading", "doesn't load",
            "does not load", "broken", "exception", "api", "webhook", "outage", "down", "slow", "latency",
            "sync", "integration", "export", "import", "upload", "stack trace"],
        1: ["app", "page", "button", "server", "browser", "android", "ios", "update", "feature", "dashboard",
            "report", "notification", "freezes", "blank", "fails", "failing", "not working"],
    },
}

PRIORITY_PATTERNS = [
    ("critical", 3, r"\b(outage|all users|everyone|production (is )?down|site (is )?down|data (loss|lost)|"
                    r"security (breach|incident)|hacked|compromised|cannot process any|"
                    r"payments? (are )?failing for)\b"),
    ("critical", 2, r"\b(down|entire (team|company)|revenue|breach)\b"),
    ("high", 2, r"\b(urgent|asap|immediately|blocked|blocking|cannot (log ?in|access|work)|can'?t (log ?in|access)|"
                r"charged twice|double charged|deadline|locked out|lost access)\b"),
    ("high", 1, r"\b(crash(es|ing)?|error|failed|failing|not working)\b"),
    ("low", 2, r"\b(how (do|can) i|question|wondering|feature request|suggestion|would be nice|"
               r"when will|is it possible|curious|feedback|typo|cosmetic|minor)\b"),
]


def _count(text, phrase):
    return len(re.findall(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text))


def classify_rules(text):
    text = (text or "").lower()
    scores = {}
    for category, tiers in CATEGORY_KEYWORDS.items():
        scores[category] = sum(weight * _count(text, kw) for weight, kws in tiers.items() for kw in kws)
    best = max(scores, key=scores.get)
    category = best if scores[best] > 0 else "general"

    prio_scores = {"critical": 0, "high": 0, "low": 0}
    for level, weight, pattern in PRIORITY_PATTERNS:
        prio_scores[level] += weight * len(re.findall(pattern, text))
    if prio_scores["critical"] >= 3:
        priority = "critical"
    elif prio_scores["critical"] + prio_scores["high"] >= 2:
        priority = "high"
    elif prio_scores["low"] >= 2 and prio_scores["high"] == 0:
        priority = "low"
    else:
        priority = "medium"

    return {"category": category, "priority": priority}
