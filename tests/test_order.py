# SPDX-License-Identifier: MIT

import math
import pickle

import pytest

import attr


@attr.s(order=True)
class LeaderboardEntry:
    score = attr.ib(order=attr.Order(descending=True))
    timestamp = attr.ib(order=attr.Order(none_last=True))


class TestOrder:
    def test_leaderboard_ordering(self):
        entries = [
            LeaderboardEntry(1, 3),
            LeaderboardEntry(2, None),
            LeaderboardEntry(2, 2),
            LeaderboardEntry(2, 1),
            LeaderboardEntry(3, None),
        ]

        assert sorted(entries) == [
            LeaderboardEntry(3, None),
            LeaderboardEntry(2, 1),
            LeaderboardEntry(2, 2),
            LeaderboardEntry(2, None),
            LeaderboardEntry(1, 3),
        ]

    @pytest.mark.parametrize("slots", [True, False])
    def test_inherited_field_can_be_overridden(self, slots):
        @attr.s(order=True)
        class Base:
            value = attr.ib(order=attr.Order(descending=True))

        @attr.s(slots=slots, order=True)
        class Child(Base):
            value = attr.ib(order=attr.Order())

        assert sorted(Child(value) for value in (2, 1, 3)) == [
            Child(1),
            Child(2),
            Child(3),
        ]

    def test_equal_order_keys_remain_equal(self):
        left = LeaderboardEntry(1, 1)
        right = LeaderboardEntry(1, 1)

        assert not (left < right)
        assert left <= right
        assert not (left > right)
        assert left >= right

    def test_eq_ignores_order_direction(self):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(order=attr.Order(descending=True))

        assert Ordered(1) == Ordered(1)
        assert Ordered(1) != Ordered(2)

    @pytest.mark.parametrize("operation", ["<", "<=", ">", ">="])
    def test_incomparable_values_raise_type_error(self, operation):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(order=attr.Order())

        with pytest.raises(TypeError):
            eval(f"Ordered(1) {operation} Ordered('1')")

    @pytest.mark.parametrize("operation", ["<", "<=", ">", ">="])
    def test_nan_follows_python_ordering(self, operation):
        @attr.s(order=True)
        class Nan:
            value = attr.ib()

        left = Nan(float("nan"))
        right = Nan(float("nan"))

        assert not eval(f"left {operation} right")
        assert math.isnan(left.value)
        assert math.isnan(right.value)

    @pytest.mark.parametrize("operation", ["<", "<=", ">", ">="])
    def test_nan_follows_descending_ordering(self, operation):
        @attr.s(order=True)
        class Nan:
            value = attr.ib(order=attr.Order(descending=True))

        left = Nan(float("nan"))
        right = Nan(float("nan"))

        assert not eval(f"left {operation} right")

    @pytest.mark.parametrize("operation", ["<", "<=", ">", ">="])
    def test_nan_with_equal_prefix_and_suffix(self, operation):
        @attr.s(order=True)
        class Nan:
            prefix = attr.ib()
            value = attr.ib(order=attr.Order(descending=True))
            suffix = attr.ib(order=attr.Order(none_last=True))

        left = Nan(1, float("nan"), 2)
        right = Nan(1, float("nan"), 2)

        assert not eval(f"left {operation} right")

    def test_existing_order_key_still_works(self):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(order=int)

        assert Ordered("10") > Ordered("2")

    def test_order_key_and_none_position(self):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(
                order=attr.Order(key=lambda item: item.get("score"))
            )

        assert Ordered({"score": 10}) > Ordered({"score": 2})

        @attr.s(order=True)
        class NullsFirst:
            value = attr.ib(order=attr.Order(none_first=True))

        assert sorted((NullsFirst(2), NullsFirst(None), NullsFirst(1))) == [
            NullsFirst(None),
            NullsFirst(1),
            NullsFirst(2),
        ]

    def test_ascending_alias(self):
        assert attr.Order(ascending=True).descending is False
        assert attr.Order(ascending=False).descending is True
        assert attr.Order(reverse=True).descending is True
        assert attr.Order(reverse=False).descending is False

        with pytest.raises(ValueError):
            attr.Order(ascending=False, descending=True)
        with pytest.raises(ValueError):
            attr.Order(reverse=True, descending=True)

    def test_nulls_aliases(self):
        assert attr.Order(nulls_last=True).none_last is True
        assert attr.Order(nulls_first=True).none_last is False
        assert attr.Order(nulls_first=True).none_first is True

        with pytest.raises(ValueError):
            attr.Order(none_last=True, nulls_last=True)

        with pytest.raises(ValueError):
            attr.Order(none_first=True, nulls_first=True)

    def test_direction_properties(self):
        order = attr.Order(descending=True)

        assert order.descending is True
        assert order.ascending is False
        assert order.reverse is True

    def test_equality_returns_not_implemented_for_other_types(self):
        assert attr.Order().__eq__(object()) is NotImplemented
        assert attr.Order() != object()

    def test_cmp_order_does_not_change_eq(self):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(cmp=attr.Order(descending=True))

        assert Ordered(1) == Ordered(1)
        assert Ordered(2) < Ordered(1)

    @pytest.mark.parametrize("none_last", [0, 1, "last"])
    def test_invalid_none_last(self, none_last):
        with pytest.raises(TypeError):
            attr.Order(none_last=none_last)

    def test_default_none_ordering_follows_python(self):
        @attr.s(order=True)
        class Ordered:
            value = attr.ib(order=attr.Order())

        with pytest.raises(TypeError):
            Ordered(None) < Ordered(1)

    def test_conflicting_none_positions(self):
        with pytest.raises(ValueError):
            attr.Order(none_last=True, none_first=True)

    def test_invalid_arguments(self):
        with pytest.raises(TypeError):
            attr.Order(descending=1)

        with pytest.raises(TypeError):
            attr.Order(key=1)

    def test_fields_keep_user_order_declaration(self):
        order = attr.Order(descending=True)

        @attr.s(order=True)
        class Ordered:
            first = attr.ib(order=order)
            second = attr.ib(order=order)

        first, second = attr.fields(Ordered)

        assert first.order_key is order
        assert second.order_key is order

    def test_reused_order_declaration_uses_field_specific_wrappers(self):
        order = attr.Order(descending=True)

        @attr.s(order=True)
        class Ordered:
            first = attr.ib(order=order)
            second = attr.ib(order=order)

        assert Ordered(1, 2) < Ordered(1, 1)
        assert Ordered(1, 2) > Ordered(2, 1)

    def test_fields_remain_pickleable(self):
        order = attr.Order(descending=True)

        @attr.s(order=True)
        class Ordered:
            value = attr.ib(order=order)

        field = attr.fields(Ordered).value

        assert pickle.loads(pickle.dumps(field)) == field
