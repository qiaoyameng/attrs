# SPDX-License-Identifier: MIT

"""
Tests for field dependencies declared via `Factory(depends_on=...)` and
`Converter(depends_on=...)`.
"""

import inspect

import pytest

import attr
import attrs

from attr._make import _resolve_init_order


@attrs.define
class _Simple:
    """A class without any declared dependencies."""

    x: int = 1
    y: int = 2


class TestResolveInitOrder:
    def test_no_dependencies_returns_attrs_unchanged(self):
        """
        Classes that don't declare dependencies keep the original
        (declaration) order -- the same object is returned.
        """
        attrs_ = attr.fields(_Simple)

        assert _resolve_init_order(attrs_) is attrs_

    def test_stable_topological_order(self):
        """
        Dependencies are initialized before their dependents; otherwise the
        declaration order is preserved.
        """

        @attrs.define
        class C:
            a: int = attrs.field(
                default=attrs.Factory(lambda: 1, depends_on=["c"])
            )
            b: int = 2
            c: int = 3

        order = [a.name for a in _resolve_init_order(attr.fields(C))]

        assert order == ["c", "a", "b"]

    def test_transitive_dependencies(self):
        """
        Chains of dependencies are fully resolved.
        """

        @attrs.define
        class C:
            a: int = attrs.field(
                default=attrs.Factory(lambda: 1, depends_on=["b"])
            )
            b: int = attrs.field(
                default=attrs.Factory(lambda: 2, depends_on=["c"])
            )
            c: int = 3

        order = [a.name for a in _resolve_init_order(attr.fields(C))]

        assert order == ["c", "b", "a"]

    def test_missing_dependency_error_contains_chain(self):
        """
        A dependency on an unknown field raises at class creation time and
        the error message contains the field chain.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(
                    default=attrs.Factory(lambda: 1, depends_on=["missing"])
                )

        assert "a -> missing" in str(ei.value)

    def test_missing_dependency_from_converter(self):
        """
        Converters can declare dependencies too; unknown ones raise.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(
                    converter=attrs.Converter(int, depends_on=["missing"]),
                    default=1,
                )

        assert "a -> missing" in str(ei.value)

    def test_cycle_error_contains_chain(self):
        """
        Circular dependencies raise at class creation time and the error
        message contains the cycle as a field chain.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(
                    default=attrs.Factory(
                        lambda self: 1, takes_self=True, depends_on=["b"]
                    )
                )
                b: int = attrs.field(
                    default=attrs.Factory(
                        lambda self: 1, takes_self=True, depends_on=["c"]
                    )
                )
                c: int = attrs.field(
                    default=attrs.Factory(
                        lambda self: 1, takes_self=True, depends_on=["a"]
                    )
                )

        assert "a -> b -> c -> a" in str(ei.value)

    def test_self_dependency_error(self):
        """
        A field depending on itself is reported as a cycle.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(
                    default=attrs.Factory(lambda: 1, depends_on=["a"])
                )

        assert "a -> a" in str(ei.value)


class TestEvaluationOrder:
    def test_factory_evaluation_order_is_recorded(self):
        """
        Factories run in dependency order, not declaration order, and each
        factory is called exactly once.
        """
        calls = []

        @attrs.define
        class C:
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: calls.append("derived") or self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base: int = attrs.field(
                default=attrs.Factory(lambda: calls.append("base") or 21)
            )

        inst = C()

        assert calls == ["base", "derived"]
        assert inst.base == 21
        assert inst.derived == 42

    def test_signature_order_is_unchanged(self):
        """
        Dependency-based reordering does not change the __init__ parameter
        order.
        """

        @attrs.define
        class C:
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base: int = 1

        params = list(inspect.signature(C.__init__).parameters)

        assert params == ["self", "derived", "base"]
        # Positional passing still follows declaration order.
        inst = C(10, 2)
        assert inst.derived == 10
        assert inst.base == 2

    def test_explicit_value_still_goes_through_converter(self):
        """
        Explicitly passed values are converted, and the factory is not
        called in that case.
        """
        calls = []

        def factory():
            calls.append("factory")
            return 1

        def converter(value):
            calls.append(("converter", value))
            return value * 10

        @attrs.define
        class C:
            x: int = attrs.field(
                default=attrs.Factory(factory),
                converter=converter,
            )

        inst = C(5)

        assert calls == [("converter", 5)]
        assert inst.x == 50

    def test_explicit_value_for_dependent_field(self):
        """
        Passing an explicit value for a field whose factory declares
        dependencies skips the factory but keeps everything consistent.
        """
        calls = []

        @attrs.define
        class C:
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: calls.append("derived") or self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base: int = attrs.field(
                default=attrs.Factory(lambda: calls.append("base") or 21)
            )

        inst = C(derived=7)

        assert calls == ["base"]
        assert inst.derived == 7
        assert inst.base == 21

    def test_converter_depends_on_runs_after_dependency(self):
        """
        A converter with takes_self + depends_on sees its dependency already
        initialized, both for explicit values and for defaults.
        """
        seen = []

        def convert(value, self):
            seen.append((value, self.base))
            return value + self.base

        @attrs.define
        class C:
            x: int = attrs.field(
                converter=attrs.Converter(
                    convert, takes_self=True, depends_on=["base"]
                ),
                default=1,
            )
            base: int = 10

        assert C().x == 11
        assert C(x=5).x == 15
        assert seen == [(1, 10), (5, 10)]

    def test_validator_sees_complete_instance(self):
        """
        Validators run after all fields -- including reordered ones -- have
        been initialized.
        """
        snapshots = []

        def validator(inst, attribute, value):
            snapshots.append((attribute.name, dict(attr.asdict(inst))))

        @attrs.define
        class C:
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                ),
                validator=validator,
            )
            base: int = attrs.field(default=21, validator=validator)

        C()

        assert snapshots == [
            ("derived", {"derived": 42, "base": 21}),
            ("base", {"derived": 42, "base": 21}),
        ]

    def test_kw_only_and_mixed_fields(self):
        """
        Dependencies work across mandatory, defaulted, and kw-only fields.
        """

        @attrs.define
        class C:
            first: int
            total: int = attrs.field(
                kw_only=True,
                default=attrs.Factory(
                    lambda self: self.first + self.second,
                    takes_self=True,
                    depends_on=["first", "second"],
                ),
            )
            second: int = 2

        inst = C(1)

        assert inst.total == 3
        params = list(inspect.signature(C.__init__).parameters)
        assert params == ["self", "first", "second", "total"]


class TestInitFalse:
    def test_field_depends_on_init_false_field(self):
        """
        An init=False field is initialized in dependency order too, so other
        fields can depend on it.
        """

        @attrs.define
        class C:
            doubled: int = attrs.field(
                default=attrs.Factory(
                    lambda self: self.internal * 2,
                    takes_self=True,
                    depends_on=["internal"],
                )
            )
            internal: int = attrs.field(
                init=False, default=attrs.Factory(lambda: 21)
            )

        inst = C()

        assert inst.internal == 21
        assert inst.doubled == 42

    def test_init_false_field_depends_on_regular_field(self):
        """
        An init=False field's factory can depend on a field that is declared
        later.
        """

        @attrs.define
        class C:
            internal: int = attrs.field(
                init=False,
                default=attrs.Factory(
                    lambda self: self.base + 1,
                    takes_self=True,
                    depends_on=["base"],
                ),
            )
            base: int = 41

        inst = C()

        assert inst.base == 41
        assert inst.internal == 42


class TestInheritance:
    def test_subclass_field_depends_on_inherited_field(self):
        """
        Fields may depend on inherited fields.
        """

        @attrs.define
        class Base:
            base: int = 2

        @attrs.define
        class Sub(Base):
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: self.base * 10,
                    takes_self=True,
                    depends_on=["base"],
                )
            )

        assert Sub().derived == 20

    def test_inherited_dependency_survives_field_override(self):
        """
        When a subclass overrides a field, the overridden field moves to the
        end of the field list, but dependency order is still honored and the
        __init__ signature keeps the (reordered) declaration order.
        """

        @attrs.define
        class Base:
            derived: int = attrs.field(
                default=attrs.Factory(
                    lambda self: self.base + 1,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base: int = 1

        @attrs.define
        class Sub(Base):
            base: int = 41

        inst = Sub()

        assert inst.base == 41
        assert inst.derived == 42

        params = list(inspect.signature(Sub.__init__).parameters)
        assert params == ["self", "derived", "base"]

    def test_missing_dependency_in_subclass(self):
        """
        Dependencies are validated against the full (inherited) field set.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class Base:
                a: int = attrs.field(
                    default=attrs.Factory(lambda: 1, depends_on=["b"])
                )

        assert "a -> b" in str(ei.value)


class TestClassFlavors:
    def test_frozen_slotted_class(self):
        """
        Dependency ordering works with frozen slotted classes (attr.s).
        """

        @attr.s(frozen=True)
        class C:
            derived = attr.ib(
                default=attr.Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base = attr.ib(default=21)

        inst = C()

        assert inst.base == 21
        assert inst.derived == 42

    def test_classic_attrs(self):
        """
        Dependency ordering works with the classic attr.s/attr.ib APIs.
        """
        calls = []

        @attr.s
        class C:
            derived = attr.ib(
                default=attr.Factory(
                    lambda self: calls.append("derived") or self.base * 2,
                    takes_self=True,
                    depends_on=["base"],
                )
            )
            base = attr.ib(
                default=attr.Factory(lambda: calls.append("base") or 21)
            )

        inst = C()

        assert calls == ["base", "derived"]
        assert (inst.base, inst.derived) == (21, 42)

    def test_factory_called_once_per_instance(self):
        """
        Each instance creation calls the factory exactly once.
        """
        calls = []

        @attrs.define
        class C:
            x: int = attrs.field(
                default=attrs.Factory(lambda: calls.append(1) or len(calls))
            )

        assert C().x == 1
        assert C().x == 2
        assert C(99).x == 99
        assert calls == [1, 1]


class TestDependsOnDeclaration:
    def test_string_dependency_is_normalized(self):
        """
        A single string depends_on is treated as one field name, not an
        iterable of characters.
        """
        factory = attrs.Factory(lambda: 1, depends_on="x")

        assert factory.depends_on == ("x",)

        converter = attrs.Converter(int, depends_on="x")

        assert converter.depends_on == ("x",)

    def test_default_is_empty_tuple(self):
        """
        Without depends_on, factories and converters have no dependencies.
        """
        assert attrs.Factory(list).depends_on == ()
        assert attrs.Converter(int).depends_on == ()

    def test_depends_on_in_repr_and_eq(self):
        """
        depends_on takes part in equality and hashing of Factory/Converter.
        """
        assert attrs.Factory(list, depends_on=["x"]) == attrs.Factory(
            list, depends_on=["x"]
        )
        assert attrs.Factory(list, depends_on=["x"]) != attrs.Factory(list)
        assert attrs.Converter(int, depends_on=["x"]) == attrs.Converter(
            int, depends_on=["x"]
        )
        assert "depends_on=('x',)" in repr(
            attrs.Factory(list, depends_on=["x"])
        )
