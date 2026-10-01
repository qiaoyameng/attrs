# SPDX-License-Identifier: MIT

from collections.abc import Callable
from typing import Any

class OrderKey:
    key: Callable[[Any], Any] | None
    reverse: bool
    none_last: bool

def order_key(
    key: Callable[[Any], Any] | None = ...,
    *,
    reverse: bool = ...,
    none_last: bool = ...,
) -> OrderKey: ...

def _field_order_key(
    order_key: OrderKey,
) -> Callable[[Any], tuple[bool, int, Any]]: ...
def compare_order(
    left_values: tuple[tuple[bool, int, Any], ...],
    right_values: tuple[tuple[bool, int, Any], ...],
    order_key_configs: tuple[OrderKey, ...],
    *,
    less: bool,
    equals: bool,
) -> bool: ...
