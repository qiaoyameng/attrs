# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime
import inspect

import pytest

import attr
from attr import NOTHING


class TestTransformHook:
    """
    Tests for `attrs(tranform_value_serializer=func)`
    """

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

    def test_combined_stages_run_in_declaration_order(self):
        calls = []

        def stage(name, value):
            def hook(cls, fields):
                calls.append(name)
                return [
                    a.evolve(**value) if a.name == "x" else a for a in fields
                ]

            hook.__name__ = name
            return hook

        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "type",
                stage("type", {"type": int}),
                overridable_attributes=("type",),
            ),
            stage(
                "validator",
                {"validator": attr.validators.instance_of(int)},
            ),
            stage("alias", {"alias": "renamed"}),
        )

        @attr.s(field_transformer=transformer)
        class C:
            x = attr.ib()

        field = attr.fields(C).x

        assert ["type", "validator", "alias"] == calls
        assert int is field.type
        assert isinstance(
            field.validator, attr.validators._InstanceOfValidator
        )
        assert "renamed" == field.alias
        assert ("renamed",) == tuple(inspect.signature(C).parameters)
        assert C(1) == C(1)
        with pytest.raises(TypeError):
            C("not-an-int")

    def test_combined_stage_conflict_reports_field_and_stages(self):
        def set_type(type):
            return lambda cls, fields: [
                a.evolve(type=type) for a in fields
            ]

        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage("first", set_type(int)),
            attr.FieldTransformerStage("second", set_type(str)),
        )

        with pytest.raises(
            attr.exceptions.FieldTransformerConflictError
        ) as exc_info:

            @attr.s(auto_attribs=True, field_transformer=transformer)
            class C:
                x: object

        error = exc_info.value

        assert "x" == error.field_name
        assert "type" == error.attribute_name
        assert "first" == error.first_stage
        assert "second" == error.second
        assert "x" in str(error)
        assert "type" in str(error)
        assert "first" in str(error)
        assert "second" in str(error)

    def test_combined_stage_can_allow_attribute_override(self):
        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "first",
                lambda cls, fields: [a.evolve(type=int) for a in fields],
            ),
            attr.FieldTransformerStage(
                "second",
                lambda cls, fields: [a.evolve(type=str) for a in fields],
                overridable_attributes=("type",),
            ),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: object

        assert str is attr.fields(C).x.type

    def test_combined_transformer_can_allow_all_overrides(self):
        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "first",
                lambda cls, fields: [a.evolve(type=int) for a in fields],
            ),
            attr.FieldTransformerStage(
                "second",
                lambda cls, fields: [a.evolve(type=str) for a in fields],
            ),
            overridable_attributes=("type",),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: object

        assert str is attr.fields(C).x.type

    def test_combined_stage_can_duplicate_an_active_field(self):
        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "duplicate",
                lambda cls, fields: [
                    *fields,
                    fields[0].evolve(name="copy"),
                ],
            ),
            attr.FieldTransformerStage(
                "type-copy",
                lambda cls, fields: [
                    a.evolve(type=int) if a.name == "copy" else a
                    for a in fields
                ],
            ),
        )

        @attr.s(auto_attribs=True, field_transformer=transformer)
        class C:
            x: object

        assert "object" == attr.fields(C).x.type
        assert int is attr.fields(C).copy.type

    def test_combined_stage_inheritance_applies_only_to_new_fields(self):
        class CountingConverter:
            def __init__(self, label):
                self.label = label
                self.calls = 0

            def __call__(self, value):
                self.calls += 1
                return f"{self.label}:{value}"

        base_converter = CountingConverter("base")

        def convert_new_fields(cls, fields):
            return [
                (
                    a.evolve(converter=CountingConverter(a.name))
                    if not a.inherited and a.converter is None
                    else a
                )
                for a in fields
            ]

        root_transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "root-converter",
                lambda cls, fields: [
                    a.evolve(converter=base_converter) for a in fields
                ],
            )
        )
        child_transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage("new-converter", convert_new_fields)
        )

        @attr.s(collect_by_mro=True, field_transformer=root_transformer)
        class Base:
            x = attr.ib()

        @attr.s(collect_by_mro=True, field_transformer=child_transformer)
        class Sub(Base):
            y = attr.ib()

        instance = Sub("1", "2")

        assert ["x", "y"] == [a.name for a in attr.fields(Sub)]
        assert ("x", "y") == tuple(inspect.signature(Sub).parameters)
        assert "base:1" == instance.x
        assert "y:2" == instance.y
        assert 1 == base_converter.calls

    def test_combined_stage_skip_on_inheritance(self):
        def rename_x(cls, fields):
            return [
                a.evolve(alias="renamed") if a.name == "x" else a
                for a in fields
            ]

        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage(
                "rename-x", rename_x, apply_on_inheritance=False
            )
        )

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class Base:
            x = attr.ib()

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class Sub(Base):
            y = attr.ib()

        assert ("renamed",) == tuple(inspect.signature(Base).parameters)
        assert ("renamed", "y") == tuple(
            inspect.signature(Sub).parameters
        )

    def test_combined_stages_diamond_inheritance_and_field_changes(self):
        def add_converter(cls, fields):
            return [
                (
                    a.evolve(
                        converter=(
                            lambda value, name=a.name: f"{name}:{value}"
                        )
                    )
                    if not a.inherited and a.converter is None
                    else a
                )
                for a in fields
            ]

        def drop_y(cls, fields):
            return [a for a in fields if a.name != "y"]

        def add_extra(cls, fields):
            if any(a.name == "extra" for a in fields):
                return fields
            return [
                *fields,
                attr.Attribute(
                    name="extra",
                    default=NOTHING,
                    validator=None,
                    repr=True,
                    cmp=None,
                    hash=None,
                    init=True,
                    inherited=False,
                    metadata={},
                    type=None,
                    converter=lambda value: f"extra:{value}",
                    kw_only=False,
                    eq=True,
                    eq_key=None,
                    order=True,
                    order_key=None,
                    on_setattr=None,
                    alias="extra",
                    alias_is_default=False,
                ),
            ]

        transformer = attr.combine_field_transformers(
            attr.FieldTransformerStage("add-extra", add_extra),
            attr.FieldTransformerStage("drop-y", drop_y),
            attr.FieldTransformerStage("convert", add_converter),
        )

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class A:
            x = attr.ib()

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class B(A):
            y = attr.ib()

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class C(A):
            z = attr.ib()

        @attr.s(collect_by_mro=True, field_transformer=transformer)
        class D(B, C):
            d = attr.ib()

        assert ["x", "extra", "z", "d"] == [
            a.name for a in attr.fields(D)
        ]
        assert ("x", "extra", "z", "d") == tuple(
            inspect.signature(D).parameters
        )

        instance = D("X", "added-value", "Z", "D")

        assert "x:X" == instance.x
        assert "extra:added-value" == instance.extra
        assert "z:Z" == instance.z
        assert "d:D" == instance.d


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
