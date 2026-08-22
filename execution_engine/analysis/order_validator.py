from __future__ import annotations


class OrderValidatorHelper:
    """Helper class providing utilities to validate price ticks and quantity precisions."""

    @staticmethod
    def is_precision_valid(quantity: float, decimal_precision: int) -> bool:
        """Verify that quantity does not exceed the allowed decimal precision."""
        qty_str = f"{quantity:.8f}".rstrip("0")
        parts = qty_str.split(".")
        if len(parts) < 2:
            return True
        decimal_part = parts[1]
        return len(decimal_part) <= decimal_precision

    @staticmethod
    def is_tick_size_valid(price: float, tick_size: float) -> bool:
        """Verify that price aligns with the allowed tick size steps."""
        if tick_size <= 0.0:
            return False
        remainder = round(price % tick_size, 8)
        return remainder == 0.0 or remainder == tick_size
