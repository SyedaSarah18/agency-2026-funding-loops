"""Deterministic math layer — the trust boundary.

Every function returns a MathResult so the UI can render the value, the SQL
that produced it, the source rows, the per-term arithmetic trace, and the
external references that document the formula.

Agents call these functions via Strands @tool wrappers (see ../tools/).
Agents never invent numbers; they only reason about which function to call
and how to interpret the result.
"""

from vendor_concentration_agent.math.types import MathResult
from vendor_concentration_agent.math.concentration import (
    hhi_by_category,
    cr_n_by_category,
    top_concentrated_categories,
)
from vendor_concentration_agent.math.procurement import sole_source_rate

__all__ = [
    "MathResult",
    "hhi_by_category",
    "cr_n_by_category",
    "top_concentrated_categories",
    "sole_source_rate",
]
