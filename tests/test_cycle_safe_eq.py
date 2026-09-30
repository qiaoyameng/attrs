# SPDX-License-Identifier: MIT

"""
Tests for the opt-in cycle-safe equality mode (``cycle_safe_eq=True``).
"""

import threading

import pytest

import attr
import attrs

from attr._compat import cycle_safe_eq_context


@attrs.define(cycle_safe_eq=True)
class Node:
    """
    A doubly-linked list node.
    """

    value: int
    prev: "Node | None" = None
    next: "Node | None" = None


def make_ring(values):
    """
    Create a doubly-linked ring of *values* and return its nodes.
    """
    nodes = [Node(v) for v in values]
    for i, node in enumerate(nodes):
        node.prev = nodes[(i - 1) % len(nodes)]
        node.next = nodes[(i + 1) % len(nodes)]

    return nodes


def seen_pairs():
    """
    The in-progress comparison pairs of the current thread.
    """
    return getattr(cycle_safe_eq_context, "seen", set())


class TestCycleSafeEq:
    def test_self_loop_equal(self):
        """
        Two self-referential nodes with equal values compare equal.
        """
        n1 = Node(1)
        n1.prev = n1.next = n1
        n2 = Node(1)
        n2.prev = n2.next = n2

        assert n1 == n2
        assert not n1 != n2

    def test_self_loop_unequal_value(self):
        """
        Self-loops with different values are not equal.
        """
        n1 = Node(1)
        n1.prev = n1.next = n1
        n2 = Node(2)
        n2.prev = n2.next = n2

        assert n1 != n2

    def test_two_node_cycle_equal(self):
        """
        Two isomorphic two-node rings compare equal, starting from any node.
        """
        a = make_ring([1, 2])
        b = make_ring([1, 2])

        assert a[0] == b[0]
        assert a[1] == b[1]

    def test_cycle_unequal_value_inside(self):
        """
        Rings that differ in a value inside the cycle are not equal.
        """
        a = make_ring([1, 2, 3])
        b = make_ring([1, 2, 4])

        assert a[0] != b[0]
        assert a[2] != b[2]

    def test_longer_cycle_equal(self):
        """
        Longer isomorphic rings compare equal.
        """
        assert make_ring([1, 2, 3])[0] == make_ring([1, 2, 3])[0]

    def test_shared_child_nodes(self):
        """
        DAGs (no cycles) that share child nodes compare equal if and only
        if the shared children compare equal.
        """
        shared1 = Node(1)
        root1 = Node(0, shared1, shared1)
        shared2 = Node(1)
        root2 = Node(0, shared2, shared2)
        shared3 = Node(2)
        root3 = Node(0, shared3, shared3)

        assert root1 == root2
        assert root1 != root3

    def test_same_left_different_right_not_conflated(self):
        """
        Re-encountering the same left-hand object together with a *different*
        right-hand object must not be treated as a cycle: the pair (left,
        right) is the key, not the left object alone.

        ``left`` unfolds to 1, 1, 1, ... while ``r1`` unfolds to 1, 2, 2, ...
        so they must not compare equal -- but they would if (left, r2) were
        conflated with the in-progress (left, r1) pair.
        """
        left = Node(1)
        left.next = left

        r2 = Node(2)
        r2.next = r2
        r1 = Node(1, None, r2)

        assert left != r1
        assert r1 != left

    def test_different_types_not_implemented(self):
        """
        Comparing against a different type returns NotImplemented from
        __eq__ (and therefore False from ==).
        """
        node = Node(1)
        node.next = node

        assert node.__eq__(42) is NotImplemented
        assert not node == 42
        assert node != 42

    def test_eq_false_field_ignored(self):
        """
        Fields with eq=False are still excluded from comparison.
        """

        @attrs.define(cycle_safe_eq=True)
        class C:
            x: int
            cache: "C | None" = attrs.field(eq=False, default=None)

        c1 = C(1)
        c1.cache = c1
        c2 = C(1)
        c2.cache = C(2)
        c2.cache.cache = c2

        assert c1 == c2

    def test_eq_key_still_applied(self):
        """
        Key functions passed as eq are still used for their fields.
        """

        @attrs.define(cycle_safe_eq=True)
        class C:
            name: str = attrs.field(eq=str.lower)
            next: "C | None" = None

        c1 = C("foo")
        c1.next = c1
        c2 = C("FOO")
        c2.next = c2

        assert c1 == c2

    def test_state_cleaned_up_after_comparison(self):
        """
        No temporary state is left behind after a comparison.
        """
        a = make_ring([1, 2])
        b = make_ring([1, 2])

        assert a[0] == b[0]
        assert not seen_pairs()

    def test_state_cleaned_up_after_exception(self):
        """
        Temporary state is discarded even if a field's __eq__ raises, and
        later comparisons are unaffected.
        """

        class Exploding:
            def __eq__(self, other):
                raise RuntimeError("boom")

        @attrs.define(cycle_safe_eq=True)
        class C:
            value: object
            next: "C | None" = None

        c1 = C(Exploding())
        c1.next = c1
        c2 = C(Exploding())
        c2.next = c2

        with pytest.raises(RuntimeError, match="boom"):
            c1 == c2

        assert not seen_pairs()

        c1.value = c2.value = 1
        assert c1 == c2
        assert not seen_pairs()

    def test_threads_do_not_interfere(self):
        """
        Two threads comparing the same pair of (unequal) objects at the same
        time both get the correct result: each thread tracks its own
        in-progress pairs.
        """

        class GatedValue:
            """
            Blocks both threads inside the comparison once, ensuring their
            comparisons overlap.
            """

            barrier = threading.Barrier(2)

            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                self.barrier.wait(timeout=10)
                return self.value == other.value

        @attrs.define(cycle_safe_eq=True)
        class C:
            next: "C | None"
            value: object

        c1 = C(None, GatedValue(1))
        c1.next = c1
        c2 = C(None, GatedValue(2))
        c2.next = c2

        results = [None, None]

        def compare(index):
            results[index] = c1 == c2

        threads = [
            threading.Thread(target=compare, args=(i,)) for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # With shared (instead of thread-local) state, the second thread
        # would see the (c1, c2) pair as in-progress and wrongly get True.
        assert results == [False, False]
        assert not seen_pairs()

    def test_requires_eq(self):
        """
        cycle_safe_eq=True without eq being generated is an error.
        """
        with pytest.raises(TypeError, match="cycle_safe_eq"):

            @attrs.define(eq=False, cycle_safe_eq=True)
            class C:
                x: int

    def test_requires_eq_auto_detect(self):
        """
        cycle_safe_eq=True is an error if a custom __eq__ disables the
        generated one via auto_detect.
        """
        with pytest.raises(TypeError, match="cycle_safe_eq"):

            @attrs.define(cycle_safe_eq=True)
            class C:
                x: int

                def __eq__(self, other):
                    return NotImplemented

    def test_classic_api(self):
        """
        The classic attr.s / attr.ib API supports cycle_safe_eq too.
        """

        @attr.s(cycle_safe_eq=True)
        class C:
            value = attr.ib()
            next = attr.ib(default=None)

        c1 = C(1)
        c1.next = c1
        c2 = C(1)
        c2.next = c2

        assert c1 == c2

    def test_make_class(self):
        """
        make_class passes cycle_safe_eq through.
        """
        cls = attr.make_class(
            "C", {"value": attr.ib(), "next": attr.ib(default=None)},
            cycle_safe_eq=True,
        )

        c1 = cls(1)
        c1.next = c1
        c2 = cls(1)
        c2.next = c2

        assert c1 == c2

    def test_frozen(self):
        """
        attrs.frozen supports cycle_safe_eq.
        """

        @attrs.frozen(cycle_safe_eq=True)
        class C:
            value: int
            next: "C | None" = None

        c1 = C(1)
        object.__setattr__(c1, "next", c1)
        c2 = C(1)
        object.__setattr__(c2, "next", c2)

        assert c1 == c2


class TestCycleSafeEqHashing:
    def test_mutable_remains_unhashable(self):
        """
        cycle_safe_eq does not change the default hashability rules: a
        mutable class with eq is unhashable.
        """
        node = Node(1)
        node.next = node

        with pytest.raises(TypeError, match="unhashable"):
            hash(node)

    def test_hashable_if_cyclic_fields_excluded(self):
        """
        Hashing is only available under the usual conditions (here:
        unsafe_hash=True) and only works if the cyclic fields are excluded
        from the hash -- cycle_safe_eq alone does not make cyclic objects
        hashable.
        """

        @attrs.define(cycle_safe_eq=True, unsafe_hash=True)
        class C:
            value: int
            next: "C | None" = attrs.field(hash=False, default=None)

        c = C(1)
        c.next = c

        assert hash(c) == hash(C(1))
