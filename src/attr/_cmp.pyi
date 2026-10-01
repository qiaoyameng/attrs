from typing import Any, Callable

_CompareWithType = Callable[[Any, Any], bool]

class Order:
    @property
    def descending(self) -> bool: ...
    @property
    def ascending(self) -> bool: ...
    @property
    def reverse(self) -> bool: ...
    @property
    def none_last(self) -> bool | None: ...
    @property
    def none_first(self) -> bool | None: ...
    @property
    def key(self) -> Callable[[Any], Any] | None: ...
    def __init__(
        self,
        *,
        descending: bool = ...,
        ascending: bool | None = ...,
        reverse: bool | None = ...,
        none_last: bool | None = ...,
        none_first: bool | None = ...,
        nulls_last: bool | None = ...,
        nulls_first: bool | None = ...,
        key: Callable[[Any], Any] | None = ...,
    ) -> None: ...
    def __call__(self, value: Any) -> Any: ...

def cmp_using(
    eq: _CompareWithType | None = ...,
    lt: _CompareWithType | None = ...,
    le: _CompareWithType | None = ...,
    gt: _CompareWithType | None = ...,
    ge: _CompareWithType | None = ...,
    require_same_type: bool = ...,
    class_name: str = ...,
) -> type: ...
