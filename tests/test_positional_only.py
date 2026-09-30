# SPDX-License-Identifier: MIT

"""
Tests for positional-only fields (`positional_only=True`).
"""

import inspect
import pickle

import pytest

import attr
import attrs

from .utils import simple_class


class TestPositionalOnly:
    def test_signature_modern(self):
        """
        attrs.define generates a real positional-only parameter.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field()

        params = list(inspect.signature(C).parameters.values())

        assert ["x", "y"] == [p.name for p in params]
        assert inspect.Parameter.POSITIONAL_ONLY == params[0].kind
        assert inspect.Parameter.POSITIONAL_OR_KEYWORD == params[1].kind
        assert "(x, /, y) -> None" == str(inspect.signature(C))

    def test_signature_classic(self):
        """
        attr.s / attr.ib support positional-only parameters too.
        """

        @attr.s
        class C:
            x = attr.ib(positional_only=True)
            y = attr.ib(default=2)

        assert "(x, /, y=2) -> None" == str(inspect.signature(C))
        assert C(1).y == 2
        assert C(1, 3).y == 3

    def test_keyword_passing_rejected(self):
        """
        Python itself rejects passing positional-only fields by keyword.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field()

        with pytest.raises(TypeError) as ei:
            C(x=1, y=2)

        assert "positional-only" in str(ei.value)

        with pytest.raises(TypeError):
            C(1, x=1, y=2)

    def test_mixed_with_kw_only(self):
        """
        Positional-only, regular, and keyword-only fields can be mixed.
        """

        @attrs.define
        class C:
            a = attrs.field(positional_only=True)
            b = attrs.field(positional_only=True, default=2)
            c = attrs.field(default=3)
            d = attrs.field(kw_only=True)
            e = attrs.field(kw_only=True, default=5)

        assert "(a, b=2, /, c=3, *, d, e=5) -> None" == str(inspect.signature(C))

        inst = C(1, c=30, d=4)

        assert (1, 2, 30, 4, 5) == attrs.astuple(inst)

    def test_kw_only_between_positional_only(self):
        """
        kw_only fields may be declared between positional-only ones because
        they are moved to the end of the signature.
        """

        @attrs.define
        class C:
            a = attrs.field(positional_only=True)
            b = attrs.field(kw_only=True)
            c = attrs.field(positional_only=True)

        assert "(a, c, /, *, b) -> None" == str(inspect.signature(C))
        assert (1, 2, 3) == attrs.astuple(C(1, 3, b=2))

    def test_positional_only_after_regular_raises(self):
        """
        A positional-only field after a regular field raises at class build
        time.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x = attrs.field()
                y = attrs.field(positional_only=True)

        assert "No positional-only attributes allowed after a" in str(ei.value)

    def test_positional_only_after_regular_inherited_raises(self):
        """
        Inherited regular fields also block later positional-only fields.
        """

        @attrs.define
        class Base:
            x = attrs.field()

        with pytest.raises(ValueError) as ei:

            @attrs.define
            class Sub(Base):
                y = attrs.field(positional_only=True)

        assert "No positional-only attributes allowed after a" in str(ei.value)

    def test_positional_only_and_kw_only_raises(self):
        """
        A field cannot be both positional-only and keyword-only.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x = attrs.field(positional_only=True, kw_only=True)

        assert "cannot be both positional-only and keyword-only" in str(
            ei.value
        )

    def test_class_level_kw_only_does_not_override(self):
        """
        A positional-only field stays positional-only if the class sets
        kw_only=True.
        """

        @attrs.define(kw_only=True)
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field()

        assert "(x, /, *, y) -> None" == str(inspect.signature(C))
        assert (1, 2) == attrs.astuple(C(1, y=2))

    def test_mandatory_after_default_raises(self):
        """
        Mandatory fields after positional-only fields with defaults raise at
        class build time.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x = attrs.field(positional_only=True, default=1)
                y = attrs.field()

        assert "No mandatory attributes allowed after" in str(ei.value)

    def test_mandatory_positional_only_after_default_raises(self):
        """
        Mandatory positional-only fields after fields with defaults raise at
        class build time.
        """
        with pytest.raises(ValueError) as ei:

            @attrs.define
            class C:
                x = attrs.field(default=1)
                y = attrs.field(positional_only=True)

        assert "No mandatory attributes allowed after" in str(ei.value)

    def test_inheritance(self):
        """
        Positional-only fields are inherited and keep their place at the
        front of the signature.
        """

        @attrs.define
        class Base:
            x = attrs.field(positional_only=True)

        @attrs.define
        class Sub(Base):
            y = attrs.field()

        assert "(x, /, y) -> None" == str(inspect.signature(Sub))
        assert (1, 2) == attrs.astuple(Sub(1, 2))
        assert attrs.fields(Sub)[0].positional_only is True
        assert attrs.fields(Sub)[0].inherited is True

    def test_evolve(self):
        """
        evolve() accepts changes by field name and passes positional-only
        fields to __init__ positionally.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field(kw_only=True, default=3)

        inst = C(1, y=2)

        assert (10, 2) == attrs.astuple(attrs.evolve(inst, x=10))
        assert (1, 20) == attrs.astuple(attrs.evolve(inst, y=20))
        assert (10, 20) == attrs.astuple(attrs.evolve(inst, x=10, y=20))

    def test_evolve_private(self):
        """
        evolve() uses the alias of private positional-only fields.
        """

        @attrs.define
        class C:
            _x = attrs.field(positional_only=True)

        assert 2 == attrs.evolve(C(1), x=2)._x

    @pytest.mark.skipif(
        not hasattr(attrs.define(type("C", (), {})), "__replace__"),
        reason="__replace__ requires Python 3.13+",
    )
    def test_replace(self):
        """
        __replace__ works with positional-only fields.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field(default=2)

        assert (10, 20) == attrs.astuple(C(1).__replace__(x=10, y=20))

    def test_match_args(self):
        """
        __match_args__ contains positional-only and regular fields, but not
        keyword-only ones.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field()
            z = attrs.field(kw_only=True, default=3)

        assert ("x", "y") == C.__match_args__

        match C(1, 2):
            case C(a, b):
                assert (1, 2) == (a, b)
            case _:
                pytest.fail("did not match")

    def test_annotations(self):
        """
        Field types end up in the __init__ signature for positional-only
        fields.
        """

        @attrs.define
        class C:
            x: int = attrs.field(positional_only=True)
            y: str = attrs.field()

        params = inspect.signature(C).parameters

        assert params["x"].annotation is int
        assert params["y"].annotation is str

    def test_converter_annotation(self):
        """
        Converter parameter annotations are used for positional-only fields.
        """

        def to_int(val: int) -> int:
            return int(val)

        @attrs.define
        class C:
            x = attrs.field(positional_only=True, converter=to_int)

        assert inspect.signature(C).parameters["x"].annotation is int
        assert 3 == C("3").x

    def test_factory(self):
        """
        Positional-only fields can have factories.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True, factory=list)

        assert [] == C().x
        assert [1] == C([1]).x

    def test_frozen(self):
        """
        Positional-only fields work on frozen classes.
        """

        @attrs.frozen
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field(default=2)

        assert "(x, /, y=2) -> None" == str(inspect.signature(C))
        assert (1, 2) == attrs.astuple(C(1))

    def test_attribute_exposed(self):
        """
        Attribute.positional_only is exposed via fields() and survives
        Attribute.evolve() and pickling.
        """

        @attrs.define
        class C:
            x = attrs.field(positional_only=True)
            y = attrs.field()

        x, y = attrs.fields(C)

        assert x.positional_only is True
        assert y.positional_only is False
        assert x.evolve(positional_only=False).positional_only is False
        assert pickle.loads(pickle.dumps(x)).positional_only is True

    def test_unpickle_pre_26_2_attribute(self):
        """
        Attributes pickled before positional_only existed unpickle with
        positional_only=False.
        """
        a = attrs.fields(simple_class(True))[0]
        state = a.__getstate__()[:-1]  # drop positional_only

        restored = attr.Attribute.__new__(attr.Attribute)
        restored.__setstate__(state)

        assert restored.positional_only is False

    def test_field_transformer(self):
        """
        Field transformers can make fields positional-only.
        """

        def transformer(cls, fields):
            return [f.evolve(positional_only=True) for f in fields]

        @attrs.define(field_transformer=transformer)
        class C:
            x = attrs.field()
            y = attrs.field()

        assert "(x, y, /) -> None" == str(inspect.signature(C))
        assert (1, 2) == attrs.astuple(C(1, 2))
