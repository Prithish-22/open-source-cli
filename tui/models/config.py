"""
tui/models/config.py
Centralized model catalog and configuration constants for Biju TUI.
Mirrors the existing CLI so both tools share the same model list.
"""

from __future__ import annotations

# ── Default model ─────────────────────────────────────────────────────────────
DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"
FAST_FALLBACK_MODEL = "meta/llama-3.1-8b-instruct"

# ── Categorized model list (NVIDIA free API + third-party) ────────────────────
AGENT_MODELS_CATEGORIZED: dict[str, list[tuple[str, str]]] = {
    "Flagship": [
        ("meta/llama-3.3-70b-instruct",                 "Llama 3.3 70B — Best overall for coding and logic."),
        ("mistralai/mistral-large-3-675b-instruct-2512", "Mistral Large 3 675B — Top-tier from Mistral."),
        ("nvidia/llama-3.3-nemotron-super-49b-v1.5",    "Nemotron Super 49B v1.5 — Great balance of speed and smarts."),
        ("nvidia/nemotron-3-super-120b-a12b",            "Nemotron 3 Super 120B — NVIDIA's large MoE model."),
        ("mistralai/mistral-nemotron",                   "Mistral Nemotron — NVIDIA-tuned Mistral."),
        ("meta/llama-4-maverick-17b-128e-instruct",      "Llama 4 Maverick 17B MoE — Latest Meta model."),
        ("openai/gpt-oss-120b",                          "GPT-OSS 120B — OpenAI's open-source on NVIDIA."),
    ],
    "Code & Reasoning": [
        ("abacusai/dracarys-llama-3.1-70b-instruct",     "Dracarys Llama 3.1 — Exceptional at coding."),
        ("openai/gpt-oss-20b",                           "GPT-OSS 20B — Compact OpenAI, good for code."),
        ("stepfun-ai/step-3.5-flash",                    "Step 3.5 Flash — StepFun's fast reasoning model."),
    ],
    "Fast & Lightweight": [
        ("meta/llama-3.1-8b-instruct",                   "Llama 3.1 8B — Super fast for quick tasks."),
        ("meta/llama-3.2-3b-instruct",                   "Llama 3.2 3B — Ultra-lightweight, instant responses."),
        ("meta/llama-3.2-1b-instruct",                   "Llama 3.2 1B — Smallest Llama, fastest possible."),
        ("mistralai/mistral-7b-instruct-v0.3",           "Mistral 7B v0.3 — Fast and reliable."),
        ("mistralai/ministral-14b-instruct-2512",        "Ministral 14B — Mistral's compact model."),
        ("mistralai/mistral-small-4-119b-2603",          "Mistral Small 4 119B — Compact but powerful."),
        ("nvidia/nemotron-mini-4b-instruct",             "Nemotron Mini 4B — NVIDIA's tiniest model."),
        ("nvidia/nvidia-nemotron-nano-9b-v2",            "Nemotron Nano 9B v2 — Latest compact NVIDIA."),
        ("google/gemma-3n-e4b-it",                       "Gemma 3N E4B — Google's nano model."),
        ("google/gemma-3n-e2b-it",                       "Gemma 3N E2B — Tiniest Google model."),
        ("upstage/solar-10.7b-instruct",                 "Solar 10.7B — Korean-made, strong for size."),
    ],
    "Third-Party APIs": [
        ("deepseek-chat",  "DeepSeek V3 (DeepSeek API). Brilliant at coding and math."),
        ("moonshot-v1-8k", "Kimi AI (Moonshot API). Great context window."),
    ],
    "Vision & Multimodal": [
        ("meta/llama-3.2-90b-vision-instruct",   "Llama 3.2 90B Vision — Large vision model."),
        ("meta/llama-3.2-11b-vision-instruct",   "Llama 3.2 11B Vision — Compact vision model."),
    ],
}

# ── Short human-readable labels ────────────────────────────────────────────────
MODEL_LABELS: dict[str, str] = {
    "meta/llama-3.3-70b-instruct":                  "Llama 3.3 70B",
    "mistralai/mistral-large-3-675b-instruct-2512":  "Mistral Large 3",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5":      "Nemotron Super 49B",
    "nvidia/nemotron-3-super-120b-a12b":             "Nemotron 3 Super 120B",
    "mistralai/mistral-nemotron":                    "Mistral Nemotron",
    "meta/llama-4-maverick-17b-128e-instruct":       "Llama 4 Maverick",
    "openai/gpt-oss-120b":                           "GPT-OSS 120B",
    "abacusai/dracarys-llama-3.1-70b-instruct":      "Dracarys 70B",
    "openai/gpt-oss-20b":                            "GPT-OSS 20B",
    "stepfun-ai/step-3.5-flash":                     "Step 3.5 Flash",
    "meta/llama-3.1-8b-instruct":                    "Llama 3.1 8B",
    "meta/llama-3.2-3b-instruct":                    "Llama 3.2 3B",
    "meta/llama-3.2-1b-instruct":                    "Llama 3.2 1B",
    "mistralai/mistral-7b-instruct-v0.3":            "Mistral 7B",
    "mistralai/ministral-14b-instruct-2512":         "Ministral 14B",
    "mistralai/mistral-small-4-119b-2603":           "Mistral Small 4",
    "nvidia/nemotron-mini-4b-instruct":              "Nemotron Mini 4B",
    "nvidia/nvidia-nemotron-nano-9b-v2":             "Nemotron Nano 9B",
    "google/gemma-3n-e4b-it":                        "Gemma 3N E4B",
    "google/gemma-3n-e2b-it":                        "Gemma 3N E2B",
    "upstage/solar-10.7b-instruct":                  "Solar 10.7B",
    "deepseek-chat":                                 "DeepSeek V3",
    "moonshot-v1-8k":                                "Kimi (8K)",
    "meta/llama-3.2-90b-vision-instruct":            "Llama 3.2 90B Vision",
    "meta/llama-3.2-11b-vision-instruct":            "Llama 3.2 11B Vision",
}

# ── Third-party API routing ────────────────────────────────────────────────────
THIRD_PARTY_MODELS: dict[str, dict] = {
    "deepseek-chat":    {"key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1",   "provider": "DeepSeek"},
    "deepseek-reasoner":{"key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1",   "provider": "DeepSeek"},
    "moonshot-v1-8k":   {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1",    "provider": "Kimi"},
    "moonshot-v1-32k":  {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1",    "provider": "Kimi"},
    "moonshot-v1-128k": {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1",    "provider": "Kimi"},
}

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ── Best NVIDIA models for web searching (ordered by capability/recency) ───────
# These are pure NVIDIA-hosted models, picked automatically — no third-party APIs.
# Order: newest architecture first, then largest parameter count.
_WEB_SEARCH_MODEL_PRIORITY = [
    "meta/llama-4-maverick-17b-128e-instruct",   # Latest Meta architecture
    "openai/gpt-oss-120b",                        # Largest OSS model on NVIDIA
    "nvidia/nemotron-3-super-120b-a12b",          # Large NVIDIA MoE
    "mistralai/mistral-large-3-675b-instruct-2512",  # Top Mistral
    "meta/llama-3.3-70b-instruct",                # Reliable flagship
]


def get_model_label(model_id: str) -> str:
    """Return short human-readable label for a model ID."""
    return MODEL_LABELS.get(model_id, model_id.split("/")[-1])


def get_all_model_ids() -> list[str]:
    """Return a flat list of all known model IDs."""
    ids = []
    for models in AGENT_MODELS_CATEGORIZED.values():
        ids.extend(m for m, _ in models)
    return ids


def get_web_search_model() -> str:
    """
    Auto-select the best available NVIDIA model for web searching.
    Picks the highest-priority model that exists in the current model list.
    This ensures the web search agent always uses the most up-to-date model
    from the configured list, regardless of what year or version it is.
    """
    all_ids = get_all_model_ids()
    for model_id in _WEB_SEARCH_MODEL_PRIORITY:
        if model_id in all_ids:
            return model_id
    # Fallback: first Flagship model
    flagship = AGENT_MODELS_CATEGORIZED.get("Flagship", [])
    if flagship:
        return flagship[0][0]
    return DEFAULT_MODEL
