# SPDX-License-Identifier: MIT

"""
Tests for methods from `attrib._cmp`.
"""

import threading

import pytest

import attr
import attrs

from attr._compat import PY_3_13_PLUS
from attr._compat import eq_cycle_context
from attr._cmp import cmp_using


# Test parameters.
EqCSameType = cmp_using(eq=lambda a, b: a == b, class_name="EqCSameType")
PartialOrderCSameType = cmp_using(
    eq=lambda a, b: a == b,
    lt=lambda a, b: a < b,
    class_name="PartialOrderCSameType",
)
FullOrderCSameType = cmp_using(
    eq=lambda a, b: a == b,
    lt=lambda a, b: a < b,
    le=lambda a, b: a <= b,
    gt=lambda a, b: a > b,
    ge=lambda a, b: a >= b,
    class_name="FullOrderCSameType",
)

EqCAnyType = cmp_using(
    eq=lambda a, b: a == b, require_same_type=False, class_name="EqCAnyType"
)
PartialOrderCAnyType = cmp_using(
    eq=lambda a, b: a == b,
    lt=lambda a, b: a < b,
    require_same_type=False,
    class_name="PartialOrderCAnyType",
)


eq_data = [
    (EqCSameType, True),
    (EqCAnyType, False),
]

order_data = [
    (PartialOrderCSameType, True),
    (PartialOrderCAnyType, False),
    (FullOrderCSameType, True),
]

eq_ids = [c[0].__name__ for c in eq_data]
order_ids = [c[0].__name__ for c in order_data]

cmp_data = eq_data + order_data
cmp_ids = eq_ids + order_ids

# Compiler strips indents from docstrings in Python 3.13+
indent = "" if PY_3_13_PLUS else " " * 8


class TestEqOrder:
    """
    Tests for eq and order related methods.
    """

    #########
    # eq
    #########
    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), cmp_data, ids=cmp_ids
    )
    def test_equal_same_type(self, cls, requires_same_type):
        """
        Equal objects are detected as equal.
        """
        assert cls(1) == cls(1)
        assert not (cls(1) != cls(1))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), cmp_data, ids=cmp_ids
    )
    def test_unequal_same_type(self, cls, requires_same_type):
        """
        Unequal objects of correct type are detected as unequal.
        """
        assert cls(1) != cls(2)
        assert not (cls(1) == cls(2))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), cmp_data, ids=cmp_ids
    )
    def test_equal_different_type(self, cls, requires_same_type):
        """
        Equal values of different types are detected appropriately.
        """
        assert (cls(1) == cls(1.0)) == (not requires_same_type)
        assert not (cls(1) != cls(1.0)) == (not requires_same_type)

    #########
    # lt
    #########
    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), eq_data, ids=eq_ids
    )
    def test_lt_unorderable(self, cls, requires_same_type):
        """
        TypeError is raised if class does not implement __lt__.
        """
        with pytest.raises(TypeError):
            cls(1) < cls(2)

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_lt_same_type(self, cls, requires_same_type):
        """
        Less-than objects are detected appropriately.
        """
        assert cls(1) < cls(2)
        assert not (cls(2) < cls(1))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_not_lt_same_type(self, cls, requires_same_type):
        """
        Not less-than objects are detected appropriately.
        """
        assert cls(2) >= cls(1)
        assert not (cls(1) >= cls(2))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_lt_different_type(self, cls, requires_same_type):
        """
        Less-than values of different types are detected appropriately.
        """
        if requires_same_type:
            # Unlike __eq__, NotImplemented will cause an exception to be
            # raised from __lt__.
            with pytest.raises(TypeError):
                cls(1) < cls(2.0)
        else:
            assert cls(1) < cls(2.0)
            assert not (cls(2) < cls(1.0))

    #########
    # le
    #########
    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), eq_data, ids=eq_ids
    )
    def test_le_unorderable(self, cls, requires_same_type):
        """
        TypeError is raised if class does not implement __le__.
        """
        with pytest.raises(TypeError):
            cls(1) <= cls(2)

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_le_same_type(self, cls, requires_same_type):
        """
        Less-than-or-equal objects are detected appropriately.
        """
        assert cls(1) <= cls(1)
        assert cls(1) <= cls(2)
        assert not (cls(2) <= cls(1))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_not_le_same_type(self, cls, requires_same_type):
        """
        Not less-than-or-equal objects are detected appropriately.
        """
        assert cls(2) > cls(1)
        assert not (cls(1) > cls(1))
        assert not (cls(1) > cls(2))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_le_different_type(self, cls, requires_same_type):
        """
        Less-than-or-equal values of diff. types are detected appropriately.
        """
        if requires_same_type:
            # Unlike __eq__, NotImplemented will cause an exception to be
            # raised from __le__.
            with pytest.raises(TypeError):
                cls(1) <= cls(2.0)
        else:
            assert cls(1) <= cls(2.0)
            assert cls(1) <= cls(1.0)
            assert not (cls(2) <= cls(1.0))

    #########
    # gt
    #########
    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), eq_data, ids=eq_ids
    )
    def test_gt_unorderable(self, cls, requires_same_type):
        """
        TypeError is raised if class does not implement __gt__.
        """
        with pytest.raises(TypeError):
            cls(2) > cls(1)

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_gt_same_type(self, cls, requires_same_type):
        """
        Greater-than objects are detected appropriately.
        """
        assert cls(2) > cls(1)
        assert not (cls(1) > cls(2))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_not_gt_same_type(self, cls, requires_same_type):
        """
        Not greater-than objects are detected appropriately.
        """
        assert cls(1) <= cls(2)
        assert not (cls(2) <= cls(1))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_gt_different_type(self, cls, requires_same_type):
        """
        Greater-than values of different types are detected appropriately.
        """
        if requires_same_type:
            # Unlike __eq__, NotImplemented will cause an exception to be
            # raised from __gt__.
            with pytest.raises(TypeError):
                cls(2) > cls(1.0)
        else:
            assert cls(2) > cls(1.0)
            assert not (cls(1) > cls(2.0))

    #########
    # ge
    #########
    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), eq_data, ids=eq_ids
    )
    def test_ge_unorderable(self, cls, requires_same_type):
        """
        TypeError is raised if class does not implement __ge__.
        """
        with pytest.raises(TypeError):
            cls(2) >= cls(1)

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_ge_same_type(self, cls, requires_same_type):
        """
        Greater-than-or-equal objects are detected appropriately.
        """
        assert cls(1) >= cls(1)
        assert cls(2) >= cls(1)
        assert not (cls(1) >= cls(2))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_not_ge_same_type(self, cls, requires_same_type):
        """
        Not greater-than-or-equal objects are detected appropriately.
        """
        assert cls(1) < cls(2)
        assert not (cls(1) < cls(1))
        assert not (cls(2) < cls(1))

    @pytest.mark.parametrize(
        ("cls", "requires_same_type"), order_data, ids=order_ids
    )
    def test_ge_different_type(self, cls, requires_same_type):
        """
        Greater-than-or-equal values of diff. types are detected appropriately.
        """
        if requires_same_type:
            # Unlike __eq__, NotImplemented will cause an exception to be
            # raised from __ge__.
            with pytest.raises(TypeError):
                cls(2) >= cls(1.0)
        else:
            assert cls(2) >= cls(2.0)
            assert cls(2) >= cls(1.0)
            assert not (cls(1) >= cls(2.0))


class TestDundersUnnamedClass:
    """
    Tests for dunder attributes of unnamed classes.
    """

    cls = cmp_using(eq=lambda a, b: a == b)

    def test_class(self):
        """
        Class name and qualified name should be well behaved.
        """
        assert self.cls.__name__ == "Comparable"
        assert self.cls.__qualname__ == "Comparable"

    def test_eq(self):
        """
        __eq__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__eq__
        assert method.__doc__.strip() == "Return a == b.  Computed by attrs."
        assert method.__name__ == "__eq__"

    def test_ne(self):
        """
        __ne__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__ne__
        assert method.__doc__.strip() == (
            "Check equality and either forward a NotImplemented or\n"
            f"{'' if PY_3_13_PLUS else ' ' * 4}return the result negated."
        )
        assert method.__name__ == "__ne__"


class TestTotalOrderingException:
    """
    Test for exceptions related to total ordering.
    """

    def test_eq_must_specified(self):
        """
        `total_ordering` requires `__eq__` to be specified.
        """
        with pytest.raises(ValueError) as ei:
            cmp_using(lt=lambda a, b: a < b)

        assert ei.value.args[0] == (
            "eq must be define is order to complete ordering from "
            "lt, le, gt, ge."
        )


class TestNotImplementedIsPropagated:
    """
    Test related to functions that return NotImplemented.
    """

    def test_not_implemented_is_propagated(self):
        """
        If the comparison function returns NotImplemented,
        the dunder method should too.
        """
        C = cmp_using(eq=lambda a, b: NotImplemented if a == 1 else a == b)

        assert C(2) == C(2)
        assert C(1) != C(1)


class TestCycleSafeEq:
    def test_self_loop(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        left = Node(1)
        left.link = left
        right = Node(1)
        right.link = right

        assert left == right
        assert not hasattr(eq_cycle_context, "left_to_right")

    def test_two_node_loop(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            previous: object = None
            next: object = None

        def make_loop(first, second):
            left = Node(first)
            right = Node(second)
            left.previous = left.next = right
            right.previous = right.next = left
            return left

        assert make_loop(1, 2) == make_loop(1, 2)
        assert not hasattr(eq_cycle_context, "left_to_right")

    def test_classic_api_supports_cycle_safe_eq(self):
        @attr.s(auto_attribs=True, cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        left = Node(1)
        left.link = left
        right = Node(1)
        right.link = right

        assert left == right

    def test_self_loop_is_not_two_node_loop(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            previous: object = None
            next: object = None

        single = Node(1)
        single.previous = single.next = single

        first = Node(1)
        second = Node(2)
        first.previous = first.next = second
        second.previous = second.next = first

        assert single != first
        assert first != single

    def test_unequal_value_in_loop(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        left = Node(1)
        left.link = left
        right = Node(2)
        right.link = right

        assert left != right

    def test_shared_child_node_compares_by_value(self):
        @attrs.define(cycle_safe_eq=True)
        class Child:
            value: int

        @attrs.define(cycle_safe_eq=True)
        class Parent:
            value: int
            left: Child
            right: Child

        shared = Child(1)
        left = Parent(0, shared, shared)

        right = Parent(0, Child(1), Child(1))

        assert left == right

    def test_eq_false_field_is_ignored(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object
            ignored: int = attrs.field(default=0, eq=False)

        left = Node(1, None)
        right = Node(1, None, 2)

        assert left == right

    def test_eq_key_is_used_for_cycle(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: str = attrs.field(eq=str.lower)
            link: object = None

        left = Node("A")
        left.link = left
        right = Node("a")
        right.link = right

        assert left == right

    def test_different_type_returns_notimplemented(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int

        class Other:
            pass

        assert Node(1).__eq__(Other()) is NotImplemented
        assert not hasattr(eq_cycle_context, "left_to_right")

    def test_field_comparator_notimplemented_is_used(self):
        comparator = cmp_using(
            eq=lambda a, b: NotImplemented if a == 1 else a == b,
            require_same_type=False,
        )

        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int = attrs.field(eq=comparator)

        assert Node(1) != Node(1)
        assert Node(2) == Node(2)

    def test_exception_clears_state(self):
        def compare(left, right):
            raise ValueError

        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None
            checked: object = attrs.field(default=None, eq=cmp_using(compare))

        left = Node(1)
        left.link = left
        right = Node(1)
        right.link = right

        with pytest.raises(ValueError):
            left == right

        assert not hasattr(eq_cycle_context, "left_to_right")
        clean = attrs.make_class(
            "CleanNode",
            {"value": attr.ib(), "link": attr.ib(default=None)},
            cycle_safe_eq=True,
        )
        clean_left = clean(1)
        clean_left.link = clean_left
        clean_right = clean(1)
        clean_right.link = clean_right

        assert clean_left == clean_right

    def test_threads_have_independent_state(self):
        entered = threading.Event()
        release = threading.Event()
        errors = []

        def block_compare(left, right):
            entered.set()
            release.wait(5)
            return left == right

        @attrs.define(cycle_safe_eq=True)
        class BlockingNode:
            value: int
            link: object = None
            checked: object = attrs.field(
                default=None, eq=cmp_using(block_compare)
            )

        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        def blocked_comparison():
            left = BlockingNode(1)
            left.link = left
            right = BlockingNode(1)
            right.link = right

            try:
                assert left == right
            except BaseException as error:  # pragma: no cover
                errors.append(error)

        def independent_comparison():
            entered.wait(5)

            left = Node(2)
            left.link = left
            right = Node(2)
            right.link = right

            try:
                assert left == right
                assert not hasattr(eq_cycle_context, "left_to_right")
            except BaseException as error:  # pragma: no cover
                errors.append(error)
            finally:
                release.set()

        first_thread = threading.Thread(target=blocked_comparison)
        second_thread = threading.Thread(target=independent_comparison)

        first_thread.start()
        second_thread.start()
        second_thread.join(5)
        first_thread.join(5)

        assert not first_thread.is_alive()
        assert not second_thread.is_alive()
        assert errors == []

    def test_mutable_class_remains_unhashable(self):
        @attrs.define(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        node = Node(1)
        node.link = node

        with pytest.raises(TypeError):
            hash(node)

    def test_frozen_cyclic_hash_is_not_supported_by_eq_mode(self):
        @attrs.frozen(cycle_safe_eq=True)
        class Node:
            value: int
            link: object = None

        node = Node(1)
        object.__setattr__(node, "link", node)

        with pytest.raises(RecursionError):
            hash(node)

        assert hash(Node(1, None)) == hash(Node(1, None))

    def test_cyclic_hash_requires_non_cyclic_hash_fields(self):
        @attrs.define(unsafe_hash=True, cycle_safe_eq=True)
        class Node:
            value: int
            link: object = attrs.field(default=None, hash=False)

        left = Node(1)
        left.link = left
        right = Node(1)
        right.link = right

        assert left == right
        assert hash(left) == hash(right)


class TestDundersPartialOrdering:
    """
    Tests for dunder attributes of classes with partial ordering.
    """

    cls = PartialOrderCSameType

    def test_class(self):
        """
        Class name and qualified name should be well behaved.
        """
        assert self.cls.__name__ == "PartialOrderCSameType"
        assert self.cls.__qualname__ == "PartialOrderCSameType"

    def test_eq(self):
        """
        __eq__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__eq__
        assert method.__doc__.strip() == "Return a == b.  Computed by attrs."
        assert method.__name__ == "__eq__"

    def test_ne(self):
        """
        __ne__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__ne__
        assert method.__doc__.strip() == (
            "Check equality and either forward a NotImplemented or\n"
            f"{'' if PY_3_13_PLUS else ' ' * 4}return the result negated."
        )
        assert method.__name__ == "__ne__"

    def test_lt(self):
        """
        __lt__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__lt__
        assert method.__doc__.strip() == "Return a < b.  Computed by attrs."
        assert method.__name__ == "__lt__"

    def test_le(self):
        """
        __le__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__le__
        assert method.__doc__.strip().startswith(
            "Return a <= b.  Computed by @total_ordering from"
        )
        assert method.__name__ == "__le__"

    def test_gt(self):
        """
        __gt__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__gt__
        assert method.__doc__.strip().startswith(
            "Return a > b.  Computed by @total_ordering from"
        )
        assert method.__name__ == "__gt__"

    def test_ge(self):
        """
        __ge__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__ge__
        assert method.__doc__.strip().startswith(
            "Return a >= b.  Computed by @total_ordering from"
        )
        assert method.__name__ == "__ge__"


class TestDundersFullOrdering:
    """
    Tests for dunder attributes of classes with full ordering.
    """

    cls = FullOrderCSameType

    def test_class(self):
        """
        Class name and qualified name should be well behaved.
        """
        assert self.cls.__name__ == "FullOrderCSameType"
        assert self.cls.__qualname__ == "FullOrderCSameType"

    def test_eq(self):
        """
        __eq__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__eq__
        assert method.__doc__.strip() == "Return a == b.  Computed by attrs."
        assert method.__name__ == "__eq__"

    def test_ne(self):
        """
        __ne__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__ne__
        assert method.__doc__.strip() == (
            "Check equality and either forward a NotImplemented or\n"
            f"{'' if PY_3_13_PLUS else ' ' * 4}return the result negated."
        )
        assert method.__name__ == "__ne__"

    def test_lt(self):
        """
        __lt__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__lt__
        assert method.__doc__.strip() == "Return a < b.  Computed by attrs."
        assert method.__name__ == "__lt__"

    def test_le(self):
        """
        __le__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__le__
        assert method.__doc__.strip() == "Return a <= b.  Computed by attrs."
        assert method.__name__ == "__le__"

    def test_gt(self):
        """
        __gt__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__gt__
        assert method.__doc__.strip() == "Return a > b.  Computed by attrs."
        assert method.__name__ == "__gt__"

    def test_ge(self):
        """
        __ge__ docstring and qualified name should be well behaved.
        """
        method = self.cls.__ge__
        assert method.__doc__.strip() == "Return a >= b.  Computed by attrs."
        assert method.__name__ == "__ge__"
