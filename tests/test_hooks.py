# SPDX-License-Identifier: MIT

from __future__ import annotations

import inspect
from datetime import datetime

import pytest

import attr
from attr import (
    FieldTransformerStage,
    combine_field_transformers,
)
from attr.exceptions import FieldTransformerConflictError


class TestTransformHook:
    """
    Tests for `attrs(tranform_value_serializer=func)`
    """

    def test_staged_transformer_applies_in_declaration_order(self):
        calls = []

        def stage(name):
            def hook(cls, attribs):
                calls.append(name)
                return [
                    attribute.evolve(metadata={**attribute.metadata, name: True})
                    for attribute in attribs
                ]

            return hook

        transformer = combine_field_transformers(
            FieldTransformerStage("first", stage("first")),
            FieldTransformerStage("second", stage("second")),
            FieldTransformerStage("third", stage("third")),
            allow_overrides=True,
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: int

        attribute = attr.fields(C).x

        assert ["first", "second", "third"] == calls
        assert {"first": True, "second": True, "third": True} == dict(
            attribute.metadata
        )

    def test_staged_transformer_accepts_plain_callables(self):
        def change_type(cls, attribs):
            return [a.evolve(type=str) for a in attribs]

        def change_alias(cls, attribs):
            return [a.evolve(alias="alias") for a in attribs]

        transformer = combine_field_transformers(change_type, change_alias)

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: int

        assert str == attr.fields(C).x.type
        assert "alias" == attr.fields(C).x.alias

    def test_staged_transformer_reports_field_attribute_and_stages(self):
        def change_type_to_str(cls, attribs):
            return [a.evolve(type=str) for a in attribs]

        def change_type_to_float(cls, attribs):
            return [a.evolve(type=float) for a in attribs]

        transformer = combine_field_transformers(
            FieldTransformerStage("str_type", change_type_to_str),
            FieldTransformerStage("float_type", change_type_to_float),
        )

        with pytest.raises(FieldTransformerConflictError) as exc_info:

            @attr.s(auto_attribs=True, field_transformer=transformer)
            class C:
                x: int

        conflict = exc_info.value.conflicts[0]

        assert "x" == conflict.field_name
        assert "type" == conflict.attribute_name
        assert "str_type" == conflict.first_stage
        assert "float_type" == conflict.second_stage
        assert "'x'" in str(exc_info.value)
        assert "'type'" in str(exc_info.value)
        assert "'str_type'" in str(exc_info.value)
        assert "'float_type'" in str(exc_info.value)

    def test_staged_transformer_reports_all_conflicts(self):
        def first_stage(cls, attribs):
            return [a.evolve(type=str, init=False) for a in attribs]

        def second_stage(cls, attribs):
            return [a.evolve(type=float, init=True) for a in attribs]

        transformer = combine_field_transformers(
            FieldTransformerStage("first", first_stage),
            FieldTransformerStage("second", second_stage),
        )

        with pytest.raises(FieldTransformerConflictError) as exc_info:

            @attr.s(auto_attribs=True, field_transformer=transformer)
            class C:
                x: int

        assert [
            ("x", "init", "first", "second"),
            ("x", "type", "first", "second"),
        ] == list(exc_info.value.conflicts)

    def test_staged_transformer_composes_type_validator_and_alias(self):
        def convert_type(cls, attribs):
            return [
                a.evolve(type=str, converter=str) if a.name == "x" else a
                for a in attribs
            ]

        def add_validator(cls, attribs):
            def validate_not_empty(instance, attribute, value):
                if not value:
                    raise ValueError("must not be empty")

            return [
                a.evolve(
                    validator=validate_not_empty
                )
                for a in attribs
            ]

        def use_attribute_names_as_aliases(cls, attribs):
            return [
                a.evolve(alias=a.name) if a.alias_is_default else a
                for a in attribs
            ]

        transformer = combine_field_transformers(
            FieldTransformerStage("type", convert_type),
            FieldTransformerStage("validator", add_validator),
            FieldTransformerStage("alias", use_attribute_names_as_aliases),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: int
            _y: str

        assert ["x", "_y"] == list(inspect.signature(C).parameters)

        instance = C(1, _y="value")

        assert "1" == instance.x
        assert "value" == instance._y

        with pytest.raises(ValueError, match="must not be empty"):
            C(1, _y="")

    def test_staged_transformer_allow_overrides(self):
        def change_type_to_str(cls, attribs):
            return [a.evolve(type=str) for a in attribs]

        def change_type_to_float(cls, attribs):
            return [a.evolve(type=float) for a in attribs]

        transformer = combine_field_transformers(
            FieldTransformerStage("str_type", change_type_to_str),
            FieldTransformerStage(
                "float_type",
                change_type_to_float,
                allow_overrides=True,
            ),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: int

        assert float == attr.fields(C).x.type

    def test_staged_transformer_can_edit_field_added_by_previous_stage(self):
        def add_field(cls, attribs):
            return [
                *attribs,
                attribs[0].evolve(name="added", default="added"),
            ]

        def change_added_field_type(cls, attribs):
            return [
                a.evolve(type=bytes) if a.name == "added" else a
                for a in attribs
            ]

        transformer = combine_field_transformers(
            FieldTransformerStage("add", add_field),
            FieldTransformerStage("type", change_added_field_type),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: int

        added = attr.fields(C).added

        assert "added" == added.default
        assert bytes == added.type

    def test_staged_transformer_reapplies_only_marked_stages(self):
        seen = []

        converter_calls = []

        def convert_x(cls, attribs):
            def converter(value):
                converter_calls.append(value)
                return str(value)

            seen.append(("base", cls.__name__, [a.name for a in attribs]))
            return [a.evolve(converter=converter) for a in attribs]

        def subclass_stage(cls, attribs):
            seen.append(("subclass", cls.__name__, [a.name for a in attribs]))
            return [
                a.evolve(converter=int) if a.name == "y" else a
                for a in attribs
            ]

        transformer = combine_field_transformers(
            FieldTransformerStage("base", convert_x),
            FieldTransformerStage(
                "subclass",
                subclass_stage,
                apply_to_new_fields=True,
            ),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class Base:
            x: int

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class Sub(Base):
            y: int

        instance = Sub("1", "2")

        assert ("1", 2) == (instance.x, instance.y)
        assert int == attr.fields(Sub).y.converter
        assert ["1"] == converter_calls
        assert [
            ("base", "Base", ["x"]),
            ("subclass", "Base", ["x"]),
            ("subclass", "Sub", ["y"]),
        ] == seen

    def test_staged_transformer_diamond_inheritance_adds_and_removes(self):
        def remove_unused(cls, attribs):
            return [a for a in attribs if "unused" not in a.metadata]

        def add_source(cls, attribs):
            return [
                *attribs,
                attribs[0].evolve(
                    name=f"source_{cls.__name__.lower()}",
                    default=cls.__name__,
                    metadata={"added": True},
                    kw_only=True,
                ),
            ]

        transformer = combine_field_transformers(
            FieldTransformerStage(
                "remove_unused",
                remove_unused,
                apply_to_new_fields=True,
            ),
            FieldTransformerStage(
                "add_source",
                add_source,
                apply_to_new_fields=True,
            ),
        )

        @attr.s(auto_attribs=True, slots=False, field_transformer=transformer)
        class Base:
            root: int
            unused_root: int = attr.ib(metadata={"unused": True})

        @attr.s(auto_attribs=True, slots=False, field_transformer=transformer)
        class Left(Base):
            left: int
            unused_left: int = attr.ib(metadata={"unused": True})

        @attr.s(auto_attribs=True, slots=False, field_transformer=transformer)
        class Right(Base):
            right: int
            unused_right: int = attr.ib(metadata={"unused": True})

        @attr.s(auto_attribs=True, slots=False, field_transformer=transformer)
        class Diamond(Left, Right):
            diamond: int
            unused_diamond: int = attr.ib(metadata={"unused": True})

        names = [a.name for a in attr.fields(Diamond)]

        assert [
            "root",
            "source_base",
            "left",
            "source_left",
            "right",
            "source_right",
            "diamond",
            "source_diamond",
        ] == names
        assert "unused_root" not in names
        assert "unused_left" not in names
        assert "unused_right" not in names
        assert "unused_diamond" not in names
        parameters = inspect.signature(Diamond).parameters

        assert list(parameters) == [
            "root",
            "left",
            "right",
            "diamond",
            "source_base",
            "source_left",
            "source_right",
            "source_diamond",
        ]
        assert all(
            parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for name in ("root", "right", "left", "diamond")
        )
        assert all(
            parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
            and parameters[name].default == expected_default
            for name, expected_default in [
                ("source_base", "Base"),
                ("source_left", "Left"),
                ("source_right", "Right"),
                ("source_diamond", "Diamond"),
            ]
        )

        instance = Diamond(1, 2, 3, 4)

        assert (
            1,
            "Base",
            3,
            "Right",
            2,
            "Left",
            4,
            "Diamond",
        ) == (
            instance.root,
            instance.source_base,
            instance.right,
            instance.source_right,
            instance.left,
            instance.source_left,
            instance.diamond,
            instance.source_diamond,
        )

    def test_hook_applied(self):
        """
        The transform hook is applied to all attributes.  Types can be missing,
        explicitly set, or annotated.
        """
        results = []

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            results[:] = [(a.name, a.type) for a in attribs]
            return attribs

        @attr.s(field_transformer=hook)
        class C:
            x = attr.ib()
            y = attr.ib(type=int)
            z: float = attr.ib()

        assert [("x", None), ("y", int), ("z", float)] == results

    def test_hook_applied_auto_attrib(self):
        """
        The transform hook is applied to all attributes and type annotations
        are detected.
        """
        results = []

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            results[:] = [(a.name, a.type) for a in attribs]
            return attribs

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int
            y: str = attr.ib()

        assert [("x", int), ("y", str)] == results

    def test_hook_applied_modify_attrib(self):
        """
        The transform hook can modify attributes.
        """

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            return [a.evolve(converter=a.type) for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int = attr.ib(converter=int)
            y: float

        c = C(x="3", y="3.14")

        assert C(x=3, y=3.14) == c

    def test_hook_remove_field(self):
        """
        It is possible to remove fields via the hook.
        """

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            return [a for a in attribs if a.type is not int]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int
            y: float

        assert {"y": 2.7} == attr.asdict(C(2.7))

    def test_hook_add_field(self):
        """
        It is possible to add fields via the hook.
        """

        def hook(cls, attribs):
            a1 = attribs[0]
            a2 = a1.evolve(name="new")
            return [a1, a2]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int

        assert {"x": 1, "new": 2} == attr.asdict(C(1, 2))

    def test_hook_override_alias(self):
        """
        It is possible to set field alias via hook
        """

        def use_dataclass_names(cls, attribs):
            return [a.evolve(alias=a.name) for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=use_dataclass_names)
        class NameCase:
            public: int
            _private: int
            __dunder__: int

        assert NameCase(public=1, _private=2, __dunder__=3) == NameCase(
            1, 2, 3
        )

    def test_hook_reorder_fields(self):
        """
        It is possible to reorder fields via the hook.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        @attr.s(field_transformer=hook)
        class C:
            x: int = attr.ib(metadata={"field_order": 1})
            y: int = attr.ib(metadata={"field_order": 0})

        assert {"x": 0, "y": 1} == attr.asdict(C(1, 0))

    def test_hook_reorder_fields_before_order_check(self):
        """
        It is possible to reorder fields via the hook before order-based errors are raised.

        Regression test for #1147.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        @attr.s(field_transformer=hook)
        class C:
            x: int = attr.ib(metadata={"field_order": 1}, default=0)
            y: int = attr.ib(metadata={"field_order": 0})

        assert {"x": 0, "y": 1} == attr.asdict(C(1))

    def test_hook_conflicting_defaults_after_reorder(self):
        """
        Raises `ValueError` if attributes with defaults are followed by
        mandatory attributes after the hook reorders fields.

        Regression test for #1147.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        with pytest.raises(ValueError) as e:

            @attr.s(field_transformer=hook)
            class C:
                x: int = attr.ib(metadata={"field_order": 1})
                y: int = attr.ib(metadata={"field_order": 0}, default=0)

        assert (
            (
                "No mandatory attributes allowed after an attribute with a "
                "default value or factory.  Attribute in question: Attribute"
                "(name='x', default=NOTHING, validator=None, repr=True, "
                "eq=True, eq_key=None, order=True, order_key=None, "
                "hash=None, init=True, "
                "metadata=mappingproxy({'field_order': 1}), type='int', converter=None, "
                "kw_only=False, inherited=False, on_setattr=None, alias='x')"
            ),
        ) == e.value.args

    def test_hook_with_inheritance(self):
        """
        The hook receives all fields from base classes.
        """

        def hook(cls, attribs):
            assert ["x", "y"] == [a.name for a in attribs]
            # Remove Base' "x"
            return attribs[1:]

        @attr.s(auto_attribs=True)
        class Base:
            x: int

        @attr.s(auto_attribs=True, field_transformer=hook)
        class Sub(Base):
            y: int

        assert {"y": 2} == attr.asdict(Sub(2))

    def test_attrs_attrclass(self):
        """
        The list of attrs returned by a field_transformer is converted to
        "AttrsClass" again.

        Regression test for #821.
        """

        @attr.s(auto_attribs=True, field_transformer=lambda c, a: list(a))
        class C:
            x: int

        fields_type = type(attr.fields(C))
        assert "CAttributes" == fields_type.__name__
        assert issubclass(fields_type, tuple)

    def test_hook_generator(self):
        """
        field_transfromers can be a generators.

        Regression test for #1416.
        """

        def hook(cls, attribs):
            yield from attribs

        @attr.s(auto_attribs=True, field_transformer=hook)
        class Base:
            x: int

        assert ["x"] == [a.name for a in attr.fields(Base)]

    def test_hook_alias_available(self):
        """
        The field_transformer receives attributes with default aliases
        already resolved, not None.

        Regression test for #1479.
        """
        seen = []

        def hook(cls, attribs):
            seen[:] = [(a.name, a.alias, a.alias_is_default) for a in attribs]
            return attribs

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            _private: int
            _explicit: int = attr.ib(alias="_explicit")
            public: int

        assert [
            ("_private", "private", True),
            ("_explicit", "_explicit", False),
            ("public", "public", True),
        ] == seen

    def test_hook_evolve_name_updates_auto_alias(self):
        """
        When a field_transformer evolves a field's name, the alias is
        automatically updated if it was auto-generated.

        Regression test for #1479.
        """

        def hook(cls, attribs):
            return [a.evolve(name="renamed") for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            _original: int

        f = attr.fields(C).renamed

        assert "renamed" == f.alias
        assert f.alias_is_default is True

    def test_hook_evolve_name_keeps_explicit_alias(self):
        """
        When a field_transformer evolves a field's name but the field had
        an explicit alias, the alias is preserved.

        Regression test for #1479.
        """

        def hook(cls, attribs):
            return [a.evolve(name="renamed") for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            original: int = attr.ib(alias="my_alias")

        f = attr.fields(C).renamed

        assert "my_alias" == f.alias
        assert f.alias_is_default is False

    def test_hook_new_field_without_alias(self):
        """
        When a field_transformer adds a brand-new field without setting an
        alias, the post-transformer alias resolution fills it in.

        Regression test for #1479.
        """

        def hook(cls, attribs):
            return [
                *list(attribs),
                attr.Attribute(
                    name="_extra",
                    default=0,
                    validator=None,
                    repr=True,
                    cmp=None,
                    hash=None,
                    init=True,
                    metadata={},
                    type=int,
                    converter=None,
                    kw_only=False,
                    eq=True,
                    eq_key=None,
                    order=True,
                    order_key=None,
                    on_setattr=None,
                    alias=None,
                    inherited=False,
                ),
            ]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int

        f = attr.fields(C)._extra

        assert "extra" == f.alias
        assert f.alias_is_default is True

    def test_hook_explicit_alias_matching_default(self):
        """
        When a user explicitly sets an alias that happens to equal the
        auto-generated default, alias_is_default is still False.

        Regression test for #1479.
        """

        @attr.s(auto_attribs=True)
        class C:
            _private: int = attr.ib(alias="private")

        f = attr.fields(C)._private

        assert "private" == f.alias
        assert f.alias_is_default is False

    def test_hook_evolve_alias_sets_not_default(self):
        """
        When a field_transformer uses evolve() to set an explicit alias,
        alias_is_default becomes False.

        Regression test for #1479.
        """

        def hook(cls, attribs):
            return [a.evolve(alias="custom") for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int

        f = attr.fields(C).x

        assert "custom" == f.alias
        assert f.alias_is_default is False


class TestAsDictHook:
    def test_asdict(self):
        """
        asdict() calls the hooks in attrs classes and in other datastructures
        like lists or dicts.
        """

        def hook(inst, a, v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        @attr.dataclass
        class Child:
            x: datetime
            y: list[datetime]

        @attr.dataclass
        class Parent:
            a: Child
            b: list[Child]
            c: dict[str, Child]
            d: dict[str, datetime]

        inst = Parent(
            a=Child(1, [datetime(2020, 7, 1)]),
            b=[Child(2, [datetime(2020, 7, 2)])],
            c={"spam": Child(3, [datetime(2020, 7, 3)])},
            d={"eggs": datetime(2020, 7, 4)},
        )

        result = attr.asdict(inst, value_serializer=hook)
        assert {
            "a": {"x": 1, "y": ["2020-07-01T00:00:00"]},
            "b": [{"x": 2, "y": ["2020-07-02T00:00:00"]}],
            "c": {"spam": {"x": 3, "y": ["2020-07-03T00:00:00"]}},
            "d": {"eggs": "2020-07-04T00:00:00"},
        } == result

    def test_asdict_calls(self):
        """
        The correct instances and attribute names are passed to the hook.
        """
        calls = []

        def hook(inst, a, v):
            calls.append((inst, a.name if a else a, v))
            return v

        @attr.dataclass
        class Child:
            x: int

        @attr.dataclass
        class Parent:
            a: Child
            b: list[Child]
            c: dict[str, Child]

        inst = Parent(a=Child(1), b=[Child(2)], c={"spam": Child(3)})

        attr.asdict(inst, value_serializer=hook)
        assert [
            (inst, "a", inst.a),
            (inst.a, "x", inst.a.x),
            (inst, "b", inst.b),
            (inst.b[0], "x", inst.b[0].x),
            (inst, "c", inst.c),
            (None, None, "spam"),
            (inst.c["spam"], "x", inst.c["spam"].x),
        ] == calls
