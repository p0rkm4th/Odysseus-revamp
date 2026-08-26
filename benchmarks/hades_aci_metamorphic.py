"""Owner-free paraphrase sets for deterministic-read trajectory invariance."""

from __future__ import annotations


READ_PARAPHRASE_SETS = {
    "MEMORY": (
        "What do you remember about me?",
        "What do you know about me?",
        "Tell me about me.",
        "Tell me what you know about me.",
        "What have you learned about me?",
        "Give me a rundown on me.",
        "What's in your memory about me?",
        "You know anything about me?",
        "Remind me what you know about me.",
    ),
    "WORK": (
        "What am I working on?",
        "What projects have I got going?",
        "What's on my plate?",
        "Remind me what I'm working on.",
    ),
    "TECHNICAL_ASSET": (
        "What computers do I own?",
        "What machines do I have?",
        "Show me my hardware.",
        "What physical boxes have I got?",
    ),
    "NETWORK_CONTEXT": (
        "What network am I currently connected to?",
        "What network am I on?",
        "Where am I connected right now?",
        "What's my current network?",
    ),
}

# Lexically similar requests that must not collapse into harmless canonical
# reads. Expected operation/domain assertions live in focused tests so this
# corpus remains an adversarial semantic input, not a production route table.
NEGATIVE_NEAR_MISSES = {
    "MEMORY": (
        "What should you remember about me?",
        "Why do you remember things about me?",
        "Tell me about memory.",
        "Forget what you know about me.",
    ),
    "WORK": (
        "What should I work on?",
        "Start working on Hades.",
        "How does project management work?",
        "What should I prioritize?",
    ),
    "TECHNICAL_ASSET": (
        "What computer should I buy?",
        "Add this laptop to my inventory.",
        "Delete that machine.",
    ),
    "NETWORK": (
        "What is a network?",
        "Scan this network.",
        "Change my network.",
    ),
}

DETERMINISTIC_READ_TRAJECTORY = (
    "INTENT",
    "DETERMINISTIC_READ",
    "CANONICAL_RESULT",
    "RESULT_PROJECTION",
    "ANSWER",
    "COMPLETE",
)

DETERMINISTIC_READ_MUST_NOT = (
    "BOUNDED_ACTION_SELECTION",
    "APPROVAL",
    "INVENTED_ACTION",
    "SECOND_ACTION_DECISION",
)
