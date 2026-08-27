"""Owner-style RC2 corpus.

These are adversarial experience inputs, not runtime routing keywords.  The
held-out variants exercise semantic normalization, domain switching, scope
ambiguity, and provider/model agency.
"""

OWNER_UTTERANCES = (
    "what you know about me",
    "tell me about my tech",
    "what about mah hardware? what kinda computational assets do i have?",
    "Please explore my current hardware",
    "what about my current network?",
    "What all is on my network? do a discovery dive?",
    "yo wtf",
    "fuck bro, what is going on with you?",
    "i need you to like, scan your hardware",
    "can you help me pentest?",
    "its authorized, I own the systems",
    "tell me about the network, do a deep dive discovery mission to tell me whats going on",
    "the network we're currently on, figure it out",
)

HELD_OUT_VARIANTS = (
    "wht do u kno abotu me",
    "tell me bout my tech stuff",
    "explore this machine's computational hardware",
    "what's on the lan rn",
    "map the devices on our current network",
    "scan the current subnet and tell me what is there",
    "hardware?",
    "network, go figure it out",
    "can you explain pentesting",
    "pentest this host; it is mine",
)

JOURNEYS = {
    "memory_assets_host_network_general": (
        "what you know about me",
        "tell me about my tech",
        "Please explore my current hardware",
        "what about my current network?",
        "What all is on my network? do a discovery dive?",
        "yo wtf",
    ),
    "work_hardware_network_work": (
        "what am i working on",
        "tell me about my hardware",
        "what's my current network",
        "what am i working on now",
    ),
    "general_action_result_return": (
        "what is a checksum",
        "scan the current network",
        "what did that discovery find",
        "tell me a joke",
        "what about those hosts",
    ),
}
