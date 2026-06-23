"""
tui/models/config.py
Centralized model catalog and configuration constants for Biju TUI.
"""

from __future__ import annotations

DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
FAST_FALLBACK_MODEL = "meta/llama-3.1-8b-instruct"

# Re-organized by Provider/Type for clarity
AGENT_MODELS_CATEGORIZED: dict[str, list[tuple[str, str]]] = {
    "Recommended": [
        ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet — Industry standard for coding."),
        ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B — Best open-weights model."),
        ("google/gemini-pro-1.5", "Gemini Pro 1.5 — Massive 2M context window."),
    ],
    "OpenRouter (Premium)": [
        ("anthropic/claude-3-opus", "Claude 3 Opus — Most capable for complex logic."),
        ("openai/gpt-4o", "GPT-4o — Fast and very capable."),
        ("deepseek/deepseek-chat", "DeepSeek V3 — Exceptional value and performance."),
    ],
    "NVIDIA NIM (Free)": [
        ("nvidia/llama-3.3-nemotron-super-49b-v1.5", "Nemotron Super 49B — NVIDIA's high-performance MoE."),
        ("mistralai/mistral-large-3-675b-instruct-2512", "Mistral Large 3 — Top-tier from Mistral."),
        ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick — Latest Meta research model."),
    ],
    "Fast & Efficient": [
        ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B — Super fast for quick edits."),
        ("google/gemma-3n-e4b-it", "Gemma 3N E4B — Small and smart."),
        ("mistralai/mistral-7b-instruct-v0.3", "Mistral 7B — Reliable lightweight model."),
    ],
}

MODEL_LABELS: dict[str, str] = {
    "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
    "anthropic/claude-3-opus": "Claude 3 Opus",
    "google/gemini-pro-1.5": "Gemini Pro 1.5",
    "openai/gpt-4o": "GPT-4o",
    "deepseek/deepseek-chat": "DeepSeek V3",
    "meta/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5": "Nemotron 49B",
    "mistralai/mistral-large-3-675b-instruct-2512": "Mistral Large 3",
    "meta/llama-4-maverick-17b-128e-instruct": "Llama 4 Maverick",
    "meta/llama-3.1-8b-instruct": "Llama 3.1 8B",
    "google/gemma-3n-e4b-it": "Gemma 3N",
    "mistralai/mistral-7b-instruct-v0.3": "Mistral 7B",
}

THIRD_PARTY_MODELS: dict[str, dict] = {
    "anthropic/claude-3.5-sonnet": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "provider": "OpenRouter"},
    "anthropic/claude-3-opus": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "provider": "OpenRouter"},
    "google/gemini-pro-1.5": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "provider": "OpenRouter"},
    "openai/gpt-4o": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "provider": "OpenRouter"},
    "deepseek/deepseek-chat": {"key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1", "provider": "OpenRouter"},
}

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

def get_model_label(model_id: str) -> str:
    return MODEL_LABELS.get(model_id, model_id.split("/")[-1])

def get_all_model_ids() -> list[str]:
    ids = []
    for models in AGENT_MODELS_CATEGORIZED.values():
        ids.extend(m for m, _ in models)
    return ids

def get_web_search_model() -> str:
    # Use Llama 3.3 70B as default searcher
    return "meta/llama-3.3-70b-instruct"
