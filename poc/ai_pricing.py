"""Price table for Anthropic models and the cost estimate derived from it.

Token accounting (Mail Client MAIL-49, TDD D-48) stores the tokens each
call used and an *estimated* cost computed here. The table is a snapshot:
``PRICE_TABLE_DATE`` is shown beside every figure in Settings → System so
the reader knows what the estimate is based on. Update the table when
Anthropic changes list prices; stored rows keep the estimate made at the
time of the call.
"""

from __future__ import annotations

#: Date the list prices below were taken from Anthropic's pricing page.
PRICE_TABLE_DATE = "2026-10-06"

#: Message Batches are billed at half the list price.
BATCH_DISCOUNT = 0.5

#: USD per million tokens: (input, output, cache write, cache read).
#: Cache write is 1.25× input and cache read 0.1× input where Anthropic has
#: not published a separate figure.
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-7": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 6.25, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 3.75, 0.30),
    "claude-sonnet-4": (3.00, 15.00, 3.75, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}


def prices_for(model: str) -> tuple[float, float, float, float] | None:
    """Prices for ``model``; a dated alias such as ``claude-sonnet-4-20250514``
    matches its undated family. ``None`` when the model is not in the table."""
    if not model:
        return None
    if model in PRICES:
        return PRICES[model]
    # Longest known prefix wins so "claude-opus-5-5" is not matched by "claude-opus-5".
    best = None
    for key in PRICES:
        if model.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return PRICES[best] if best else None


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    *,
    batch: bool = False,
) -> float | None:
    """Estimated USD cost of one call, or ``None`` when the model is unpriced."""
    p = prices_for(model)
    if p is None:
        return None
    inp, out, cw, cr = p
    usd = (
        (input_tokens or 0) * inp
        + (output_tokens or 0) * out
        + (cache_creation_input_tokens or 0) * cw
        + (cache_read_input_tokens or 0) * cr
    ) / 1_000_000
    if batch:
        usd *= BATCH_DISCOUNT
    return round(usd, 6)
