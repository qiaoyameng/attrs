# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable

from .exceptions import FrozenAttributeError


class OrderKey:
    __slots__ = ("key", "reverse", "none_last")

    def __init__(self, *, key=None, reverse=False, none_last=False):
        if key is not None and not callable(key):
            raise TypeError("`key` must be callable.")
        if not isinstance(reverse, bool):
            raise TypeError("`reverse` must be a bool.")
        if not isinstance(none_last, bool):
            raise TypeError("`none_last` must be a bool.")

        object.__setattr__(self, "key", key)
        object.__setattr__(self, "reverse", reverse)
        object.__setattr__(self, "none_last", none_last)

    def __setattr__(self, name, value):
        raise FrozenAttributeError()

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented

        return (
            self.key == other.key
            and self.reverse == other.reverse
            and self.none_last == other.none_last
        )

    def __hash__(self):
        return hash((self.key, self.reverse, self.none_last))

    def __repr__(self):
        return (
            f"OrderKey(key={self.key!r}, reverse={self.reverse!r}, "
            f"none_last={self.none_last!r})"
        )

    def __call__(self, value):
        if self.key is None:
            return value

        return self.key(value)

    def __getstate__(self):
        return self.key, self.reverse, self.none_last

    def __setstate__(self, state):
        key, reverse, none_last = state
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "reverse", reverse)
        object.__setattr__(self, "none_last", none_last)


def order_key(key=None, *, reverse=False, none_last=False):
    """
    Configure how an attribute is ordered.

    Args:
        key: Callable used to transform the value before ordering.
        reverse: Order transformed values in descending order.
        none_last: Place `None` after non-`None` values.

    .. versionadded:: 26.2.0
    """
    return OrderKey(key=key, reverse=reverse, none_last=none_last)


def _field_order_key(order_key):
    def get_value(value):
        is_none = value is None

        if is_none:
            marker = 1 if order_key.none_last else 0
        else:
            marker = 0 if order_key.none_last else 1
            key = order_key.key
            value = key(value) if key is not None else value

        return is_none, marker, value

    return get_value


def _compare_values(left, right, *, outer_less, reverse, non_strict):
    left_none, left_marker, left_value = left
    right_none, right_marker, right_value = right

    if left_marker != right_marker:
        if non_strict:
            return False

        result = left_marker < right_marker
        return result if outer_less else not result

    if non_strict:
        if left_none and right_none:
            return True

        if reverse:
            return left_value >= right_value

        return left_value <= right_value

    return left_value > right_value if reverse else left_value < right_value


def compare_order(left_values, right_values, order_key_configs, *, less, equals):
    """
    Compare ordered attribute values lexicographically.
    """
    for left, right, order_key in zip(
        left_values,
        right_values,
        order_key_configs,
        strict=True,
    ):
        field_equal = left[0] and right[0]
        if not field_equal:
            field_equal = left[2] == right[2]
        if field_equal is NotImplemented:
            return NotImplemented

        if bool(field_equal):
            continue

        field_less = _compare_values(
            left,
            right,
            outer_less=less,
            reverse=(order_key.reverse if less else not order_key.reverse),
            non_strict=equals,
        )
        if field_less is NotImplemented:
            return NotImplemented

        return field_less

    return equals
