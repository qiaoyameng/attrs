# SPDX-License-Identifier: MIT


import functools
import operator
import types

from ._make import __ne__


_operation_names = {"eq": "==", "lt": "<", "le": "<=", "gt": ">", "ge": ">="}


class Order:
    """
    Describe how a field participates in generated ordering.

    Args:
        descending (bool): Sort values in descending order.
        ascending (bool | None): Sort values in ascending order.
        reverse (bool | None): Alias for *descending*.
        none_last (bool | None): Place `None` after non-`None` values if
            `True`, before them if `False`, and leave ordering to Python if
            `None`.
        none_first (bool | None): Place `None` before non-`None` values if
            `True` and after them if `False`.
        nulls_last (bool | None): Alias for *none_last*.
        nulls_first (bool | None): Alias for *none_first*.
        key (typing.Callable | None): Callable used to transform the field
            value before ordering.

    .. versionadded:: 26.2.0
    """

    __slots__ = (
        "_descending",
        "_key",
        "_none_last",
        "_wrapper_class",
    )

    _is_attrs_order = True

    def __init__(
        self,
        *,
        descending=None,
        ascending=None,
        reverse=None,
        none_last=None,
        none_first=None,
        nulls_last=None,
        nulls_first=None,
        key=None,
        wrapper_class=None,
    ):
        direction_arguments = [
            value is not None for value in (ascending, descending, reverse)
        ]
        if sum(direction_arguments) > 1:
            msg = (
                "Only one of ascending, descending, and reverse can be set."
            )
            raise ValueError(msg)

        if reverse is not None:
            if not isinstance(reverse, bool):
                msg = "reverse must be True, False, or None."
                raise TypeError(msg)

            descending = reverse
        elif ascending is not None:
            if not isinstance(ascending, bool):
                msg = "ascending must be True, False, or None."
                raise TypeError(msg)

            descending = not ascending
        elif descending is None:
            descending = False

        if not isinstance(descending, bool):
            msg = "descending must be True or False."
            raise TypeError(msg)

        if key is not None and not callable(key):
            msg = "key must be callable or None."
            raise TypeError(msg)

        last_arguments = (none_last, nulls_last)
        first_arguments = (none_first, nulls_first)

        if sum(value is not None for value in last_arguments) > 1:
            msg = "none_last and nulls_last are aliases."
            raise ValueError(msg)

        if sum(value is not None for value in first_arguments) > 1:
            msg = "none_first and nulls_first are aliases."
            raise ValueError(msg)

        none_last = next(
            (value for value in last_arguments if value is not None), None
        )
        none_first = next(
            (value for value in first_arguments if value is not None), None
        )

        if none_last is not None and none_first is not None:
            msg = "None position cannot be both first and last."
            raise ValueError(msg)

        if none_first is not None:
            if not isinstance(none_first, bool):
                msg = "The first-position argument must be True or False."
                raise TypeError(msg)

            none_last = not none_first

        if none_last is not None and not isinstance(none_last, bool):
            msg = "The last-position argument must be True or False."
            raise TypeError(msg)

        self._descending = descending
        self._none_last = none_last
        self._key = key
        self._wrapper_class = wrapper_class

    @property
    def descending(self):
        return self._descending

    @property
    def ascending(self):
        return not self._descending

    @property
    def reverse(self):
        return self._descending

    @property
    def none_last(self):
        return self._none_last

    @property
    def none_first(self):
        return None if self._none_last is None else not self._none_last

    @property
    def key(self):
        return self._key

    def __call__(self, value):
        if self._key is not None:
            value = self._key(value)

        wrapper_class = self._wrapper_class
        if wrapper_class is None:
            wrapper_class = _make_order_value_class(
                self._descending, self._none_last
            )
        return wrapper_class(value)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented

        return (
            self._descending is other._descending
            and self._none_last is other._none_last
            and self._key is other._key
        )

    def __hash__(self):
        return hash((self._descending, self._none_last, self._key))

    def __repr__(self):
        return (
            f"Order(descending={self._descending!r}, "
            f"none_last={self._none_last!r}, key={self._key!r})"
        )

    def _bind(self):
        return Order(
            descending=self._descending,
            none_last=self._none_last,
            key=self._key,
            wrapper_class=_make_order_value_class(
                self._descending, self._none_last
            ),
        )


def _make_order_value_class(descending, none_last):
    value_operation = {
        "__lt__": operator.gt if descending else operator.lt,
        "__le__": operator.ge if descending else operator.le,
        "__gt__": operator.lt if descending else operator.gt,
        "__ge__": operator.le if descending else operator.ge,
    }

    def compare(self, other, operation):
        if other.__class__ is not self.__class__:
            return NotImplemented

        left = self.value
        right = other.value

        if none_last is not None:
            left_is_none = left is None
            right_is_none = right is None

            if left_is_none or right_is_none:
                if left_is_none and right_is_none:
                    return operation in {"__le__", "__ge__"}

                left_rank = 1 if left_is_none == none_last else 0
                right_rank = 1 if right_is_none == none_last else 0

                if operation == "__lt__":
                    return left_rank < right_rank
                if operation == "__le__":
                    return left_rank <= right_rank
                if operation == "__gt__":
                    return left_rank > right_rank
                return left_rank >= right_rank

        result = value_operation[operation](left, right)
        if result is NotImplemented:
            return NotImplemented

        return result

    body = {
        "__slots__": ("value",),
        "__init__": _make_init(),
        "__eq__": lambda self, other: (
            other.__class__ is self.__class__
            and self.value == other.value
        ),
        "__hash__": None,
        "__lt__": lambda self, other: compare(self, other, "__lt__"),
        "__le__": lambda self, other: compare(self, other, "__le__"),
        "__gt__": lambda self, other: compare(self, other, "__gt__"),
        "__ge__": lambda self, other: compare(self, other, "__ge__"),
    }

    return types.new_class("_OrderedValue", (), {}, lambda ns: ns.update(body))


def cmp_using(
    eq=None,
    lt=None,
    le=None,
    gt=None,
    ge=None,
    require_same_type=True,
    class_name="Comparable",
):
    """
    Create a class that can be passed into `attrs.field`'s ``eq``, ``order``,
    and ``cmp`` arguments to customize field comparison.

    The resulting class will have a full set of ordering methods if at least
    one of ``{lt, le, gt, ge}`` and ``eq``  are provided.

    Args:
        eq (typing.Callable | None):
            Callable used to evaluate equality of two objects.

        lt (typing.Callable | None):
            Callable used to evaluate whether one object is less than another
            object.

        le (typing.Callable | None):
            Callable used to evaluate whether one object is less than or equal
            to another object.

        gt (typing.Callable | None):
            Callable used to evaluate whether one object is greater than
            another object.

        ge (typing.Callable | None):
            Callable used to evaluate whether one object is greater than or
            equal to another object.

        require_same_type (bool):
            When `True`, equality and ordering methods will return
            `NotImplemented` if objects are not of the same type.

        class_name (str | None): Name of class. Defaults to "Comparable".

    See `comparison` for more details.

    .. versionadded:: 21.1.0
    """

    body = {
        "__slots__": ["value"],
        "__init__": _make_init(),
        "_requirements": [],
        "_is_comparable_to": _is_comparable_to,
    }

    # Add operations.
    num_order_functions = 0
    has_eq_function = False

    if eq is not None:
        has_eq_function = True
        body["__eq__"] = _make_operator("eq", eq)
        body["__ne__"] = __ne__

    if lt is not None:
        num_order_functions += 1
        body["__lt__"] = _make_operator("lt", lt)

    if le is not None:
        num_order_functions += 1
        body["__le__"] = _make_operator("le", le)

    if gt is not None:
        num_order_functions += 1
        body["__gt__"] = _make_operator("gt", gt)

    if ge is not None:
        num_order_functions += 1
        body["__ge__"] = _make_operator("ge", ge)

    type_ = types.new_class(
        class_name, (object,), {}, lambda ns: ns.update(body)
    )

    # Add same type requirement.
    if require_same_type:
        type_._requirements.append(_check_same_type)

    # Add total ordering if at least one operation was defined.
    if 0 < num_order_functions < 4:
        if not has_eq_function:
            # functools.total_ordering requires __eq__ to be defined,
            # so raise early error here to keep a nice stack.
            msg = "eq must be define is order to complete ordering from lt, le, gt, ge."
            raise ValueError(msg)
        type_ = functools.total_ordering(type_)

    return type_


def _make_init():
    """
    Create __init__ method.
    """

    def __init__(self, value):
        """
        Initialize object with *value*.
        """
        self.value = value

    return __init__


def _make_operator(name, func):
    """
    Create operator method.
    """

    def method(self, other):
        if not self._is_comparable_to(other):
            return NotImplemented

        result = func(self.value, other.value)
        if result is NotImplemented:
            return NotImplemented

        return result

    method.__name__ = f"__{name}__"
    method.__doc__ = (
        f"Return a {_operation_names[name]} b.  Computed by attrs."
    )

    return method


def _is_comparable_to(self, other):
    """
    Check whether `other` is comparable to `self`.
    """
    return all(func(self, other) for func in self._requirements)


def _check_same_type(self, other):
    """
    Return True if *self* and *other* are of the same type, False otherwise.
    """
    return other.value.__class__ is self.value.__class__
