"""USD per million tokens (Anthropic first-party list prices, cached 2026-10).

Bedrock pricing is set by AWS and can differ; first-party prices are used as a
proxy until it is checked against the Bedrock pricing page.
"""
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    key = next((k for k in PRICES if model and k in model), None)
    if key is None:
        return 0.0
    pin, pout = PRICES[key]
    return (input_tokens * pin + output_tokens * pout) / 1_000_000
