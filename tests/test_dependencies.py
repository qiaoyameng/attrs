# SPDX-License-Identifier: MIT

"""
Tests for field dependency declarations via `Factory` and `Converter`
``depends_on``.
"""

import inspect
import pickle

import pytest

import attr
import attrs

from attr import Converter, Factory


@attrs.define
class Simple:
    """A class without dependency declarations, for regression checks."""

    x: int
    y: list = attrs.field(default=attrs.Factory(list))


class TestFactoryDependsOn:
    """
    Tests for `Factory(depends_on=...)`.
    """

    def test_factory_reads_later_declared_field(self):
        """
        A takes_self factory can read a field that is declared after it if
        the dependency is declared.
        """

        @attrs.define
        class C:
            doubled: int = attrs.field(
                default=Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=("base",),
                )
            )
            base: int = 21

        assert C().doubled == 42
        assert C(doubled=5).doubled == 5
        assert C(base=3).doubled == 6

    def test_signature_order_unchanged(self):
        """
        Dependency resolution changes the evaluation order, but not the
        __init__ parameter order.
        """

        @attrs.define
        class C:
            b: int = attrs.field(
                default=Factory(
                    lambda self: self.a + 1, takes_self=True, depends_on=("a",)
                )
            )
            a: int = 1

        params = list(inspect.signature(C.__init__).parameters)
        assert params == ["self", "b", "a"]

    def test_evaluation_order(self):
        """
        Factories are evaluated in dependency order, keeping the declaration
        order whenever possible.
        """
        log = []

        def make(name, value):
            def factory():
                log.append(name)
                return value

            return factory

        @attrs.define
        class C:
            c: int = attrs.field(
                default=Factory(make("c", 3), depends_on=("b",))
            )
            a: int = attrs.field(default=Factory(make("a", 1)))
            b: int = attrs.field(default=Factory(make("b", 2)))

        C()
        assert log == ["a", "b", "c"]

    def test_transitive_evaluation_order(self):
        """
        Transitive dependencies are resolved: a -> b -> c evaluates c first.
        """
        log = []

        @attrs.define
        class C:
            a: int = attrs.field(
                default=Factory(lambda: log.append("a") or 1, depends_on=("b",))
            )
            b: int = attrs.field(
                default=Factory(lambda: log.append("b") or 2, depends_on=("c",))
            )
            c: int = attrs.field(
                default=Factory(lambda: log.append("c") or 3)
            )

        C()
        assert log == ["c", "b", "a"]

    def test_factory_called_once(self):
        """
        The factory is called exactly once, even with dependencies.
        """
        calls = []

        @attrs.define
        class C:
            x: int = attrs.field(
                default=Factory(
                    lambda self: calls.append(1) or self.y * 2,
                    takes_self=True,
                    depends_on=("y",),
                )
            )
            y: int = 10

        assert C().x == 20
        assert calls == [1]

    def test_inherited_field_dependency(self):
        """
        A subclass field can depend on a field inherited from a base class.
        """

        @attrs.define
        class Base:
            base_value: int = 5

        @attrs.define
        class Child(Base):
            computed: int = attrs.field(
                default=Factory(
                    lambda self: self.base_value * 10,
                    takes_self=True,
                    depends_on=("base_value",),
                )
            )

        assert Child().computed == 50
        assert Child(base_value=2).computed == 20

    def test_init_false_factory_dependency(self):
        """
        An init=False field's factory can depend on a regular field.
        """

        @attrs.define
        class C:
            x: int = 3
            derived: int = attrs.field(
                init=False,
                default=Factory(
                    lambda self: self.x + 100,
                    takes_self=True,
                    depends_on=("x",),
                ),
            )

        assert C().derived == 103
        assert C(x=1).derived == 101

    def test_init_false_field_as_dependency(self):
        """
        A regular field can depend on an init=False field with a default.
        """

        @attrs.define
        class C:
            y: int = attrs.field(
                default=Factory(
                    lambda self: self.base + 1,
                    takes_self=True,
                    depends_on=("base",),
                )
            )
            base: int = attrs.field(init=False, default=7)

        assert C().y == 8

    def test_frozen_and_slots(self):
        """
        Dependencies work on frozen classes.
        """

        @attrs.frozen
        class C:
            doubled: int = attrs.field(
                default=Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=("base",),
                )
            )
            base: int = 4

        assert C().doubled == 8

    def test_kw_only_dependency(self):
        """
        Dependencies work with kw_only fields and the signature keeps them
        keyword-only.
        """

        @attrs.define
        class C:
            x: int = attrs.field(
                default=Factory(
                    lambda self: self.y * 3,
                    takes_self=True,
                    depends_on=("y",),
                ),
                kw_only=True,
            )
            y: int = 2

        c = C()
        assert C(x=9).x == 9
        assert c.x == 6
        params = inspect.signature(C.__init__).parameters
        assert params["x"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_classic_api(self):
        """
        Dependencies work with the classic attr.s/attr.ib API too.
        """

        @attr.s
        class C:
            doubled = attr.ib(
                default=Factory(
                    lambda self: self.base * 2,
                    takes_self=True,
                    depends_on=("base",),
                )
            )
            base = attr.ib(default=11)

        assert attr.asdict(C()) == {"doubled": 22, "base": 11}


class TestConverterDependsOn:
    """
    Tests for `Converter(depends_on=...)`.
    """

    def test_explicit_value_passes_through_converter(self):
        """
        An explicitly passed value still goes through a converter that
        declares dependencies, and the dependency is set first.
        """
        seen = []

        def convert(value, self):
            seen.append((value, self.unit))
            return f"{value}{self.unit}"

        @attrs.define
        class C:
            amount: str = attrs.field(
                converter=Converter(
                    convert, takes_self=True, depends_on=("unit",)
                ),
                default="5",
            )
            unit: str = "kg"

        assert C().amount == "5kg"
        assert C("7").amount == "7kg"
        assert seen == [("5", "kg"), ("7", "kg")]

    def test_converter_dependency_on_later_field(self):
        """
        A converter depending on a later-declared field runs after that
        field is initialized.
        """

        @attrs.define
        class C:
            total: int = attrs.field(
                converter=Converter(
                    lambda v, self: v + self.tax,
                    takes_self=True,
                    depends_on=("tax",),
                ),
                default=0,
            )
            tax: int = 10

        assert C().total == 10
        assert C(5).total == 15

    def test_factory_and_converter_dependencies_combined(self):
        """
        Dependencies from a field's factory and converter are both honored.
        """

        @attrs.define
        class C:
            x: int = attrs.field(
                default=Factory(
                    lambda self: self.a + 1, takes_self=True, depends_on=("a",)
                ),
                converter=Converter(
                    lambda v, self: v * self.b,
                    takes_self=True,
                    depends_on=("b",),
                ),
            )
            a: int = 1
            b: int = 10

        assert C().x == 20
        assert C(5).x == 50


class TestValidators:
    """
    Validators interact correctly with dependency-ordered initialization.
    """

    def test_validator_sees_complete_instance(self):
        """
        Validators run after all fields -- including reordered ones -- are
        initialized, so they see the complete instance.
        """
        seen = []

        def v_x(inst, attr_, value):
            seen.append(("x", inst.y))

        def v_y(inst, attr_, value):
            seen.append(("y", inst.x))

        @attrs.define
        class C:
            x: int = attrs.field(
                validator=v_x,
                default=Factory(
                    lambda self: self.y + 1, takes_self=True, depends_on=("y",)
                ),
            )
            y: int = attrs.field(validator=v_y, default=41)

        C()
        assert seen == [("x", 41), ("y", 42)]


class TestErrors:
    """
    Missing and circular dependencies are reported at class creation.
    """

    def test_missing_dependency(self):
        """
        Depending on a nonexistent field raises at class creation and names
        the chain.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x: int = attrs.field(default=Factory(list, depends_on=("nope",)))

        msg = str(ei.value)
        assert "'x' depends on unknown field 'nope'" in msg
        assert "x -> nope" in msg

    def test_missing_transitive_dependency(self):
        """
        The chain of a transitively missing dependency is reported.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(default=Factory(list, depends_on=("b",)))
                b: int = attrs.field(default=Factory(list, depends_on=("gone",)))

        assert "a -> b -> gone" in str(ei.value)

    def test_circular_dependency(self):
        """
        Circular dependencies raise at class creation with the cycle chain.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                a: int = attrs.field(default=Factory(list, depends_on=("b",)))
                b: int = attrs.field(default=Factory(list, depends_on=("a",)))

        msg = str(ei.value)
        assert "Circular dependency" in msg
        assert "a -> b -> a" in msg

    def test_self_dependency(self):
        """
        A field depending on itself is reported as a cycle.
        """
        with pytest.raises(ValueError, match=r"x -> x"):

            @attrs.define
            class C:
                x: int = attrs.field(default=Factory(list, depends_on=("x",)))

    def test_dependency_on_uninitialized_field(self):
        """
        Depending on an init=False field without a default raises at class
        creation.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x: int = attrs.field(default=Factory(list, depends_on=("y",)))
                y: int = attrs.field(init=False)

        msg = str(ei.value)
        assert "not initialized by __init__" in msg
        assert "x -> y" in msg


class TestNoDependenciesUnchanged:
    """
    Classes without dependency declarations use the original code path.
    """

    def test_generated_init_source_unchanged(self):
        """
        Classes without dependency declarations generate the same __init__
        source as before (declaration order).
        """

        @attrs.define
        class C:
            x: int = attrs.field(default=Factory(list))
            y: int = 1

        source = inspect.getsource(C.__init__)
        assert source.index("self.x = ") < source.index("self.y = ")

    def test_plain_class_still_works(self):
        assert Simple(1).x == 1
        assert Simple(1).y == []


class TestFactoryConverterObjects:
    """
    The depends_on attribute on Factory and Converter themselves.
    """

    def test_factory_depends_on_normalized(self):
        f = Factory(list, depends_on=["a", "b"])
        assert f.depends_on == ("a", "b")
        assert Factory(list).depends_on == ()

    def test_converter_depends_on_normalized(self):
        c = Converter(int, depends_on=["a"])
        assert c.depends_on == ("a",)
        assert Converter(int).depends_on == ()

    def test_factory_eq(self):
        assert Factory(list, depends_on=("a",)) == Factory(
            list, depends_on=("a",)
        )
        assert Factory(list) != Factory(list, depends_on=("a",))

    def test_converter_eq(self):
        assert Converter(int, depends_on=("a",)) == Converter(
            int, depends_on=("a",)
        )
        assert Converter(int) != Converter(int, depends_on=("a",))

    def test_factory_pickle(self):
        f = Factory(list, takes_self=True, depends_on=("a",))
        assert pickle.loads(pickle.dumps(f)) == f

    def test_factory_pickle_legacy_state(self):
        """
        State pickled before depends_on existed still loads.
        """
        f = Factory(list)
        f.__setstate__((list, True))
        assert f.factory is list
        assert f.takes_self is True
        assert f.depends_on == ()

    def test_converter_pickle(self):
        c = Converter(int, depends_on=("a",))
        assert pickle.loads(pickle.dumps(c)) == c

    def test_converter_pickle_legacy_state(self):
        """
        State pickled before depends_on existed still loads.
        """
        c = Converter(int)
        c.__setstate__(
            {"converter": int, "takes_self": False, "takes_field": False}
        )
        assert c.depends_on == ()
