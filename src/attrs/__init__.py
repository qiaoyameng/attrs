# SPDX-License-Identifier: MIT

from attr import (
    NOTHING,
    Attribute,
    AttrsInstance,
    Converter,
    Factory,
    FieldTransformerConflict,
    FieldTransformerStage,
    NothingType,
    _make_getattr,
    assoc,
    cmp_using,
    combine_field_transformers,
    define,
    evolve,
    field,
    fields,
    fields_dict,
    frozen,
    has,
    make_class,
    mutable,
    resolve_types,
    validate,
)
from attr._make import ClassProps
from attr._next_gen import asdict, astuple, inspect

from . import exceptions, filters, setters


__all__ = [
    "NOTHING",
    "Attribute",
    "AttrsInstance",
    "ClassProps",
    "Converter",
    "Factory",
    "FieldTransformerConflict",
    "FieldTransformerStage",
    "NothingType",
    "__author__",
    "__copyright__",
    "__description__",
    "__doc__",
    "__email__",
    "__license__",
    "__title__",
    "__url__",
    "__version__",
    "__version_info__",
    "asdict",
    "assoc",
    "astuple",
    "cmp_using",
    "combine_field_transformers",
    "converters",
    "define",
    "evolve",
    "exceptions",
    "field",
    "fields",
    "fields_dict",
    "filters",
    "frozen",
    "has",
    "inspect",
    "make_class",
    "mutable",
    "resolve_types",
    "setters",
    "validate",
    "validators",
]

__getattr__ = _make_getattr(__name__)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
