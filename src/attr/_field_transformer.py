# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple, TypeAlias

from .exceptions import FieldTransformerConflictError


_FieldTransformerType: TypeAlias = Callable[[type, list[Any]], Any]

_FIELD_ATTRIBUTES = (
    "name",
    "default",
    "validator",
    "repr",
    "eq",
    "eq_key",
    "order",
    "order_key",
    "hash",
    "init",
    "metadata",
    "type",
    "converter",
    "kw_only",
    "on_setattr",
    "alias",
    "alias_is_default",
)


class FieldTransformerStage(NamedTuple):
    """
    A named stage in a field transformer pipeline.

    Args:
        name:
            Stage name used in conflict reports.
        transformer:
            Field transformer to run.
        apply_to_new_fields:
            Replay this stage on fields introduced by subclasses.
        allow_overrides:
            Allow this stage to override earlier stages.
    """

    name: str
    transformer: _FieldTransformerType
    apply_to_new_fields: bool = False
    allow_overrides: bool = False


class FieldTransformerConflict(NamedTuple):
    """
    A conflict between two field transformer stages.
    """

    field_name: str
    attribute_name: str
    first_stage: str
    second_stage: str


class _StagedFieldTransformer:
    __slots__ = ("allow_overrides", "stages")

    def __init__(self, stages, allow_overrides):
        self.stages = tuple(stages)
        self.allow_overrides = allow_overrides

    def __call__(self, cls, attributes):
        attributes = tuple(attributes)
        inherited = tuple(a for a in attributes if a.inherited)
        new_attributes = tuple(a for a in attributes if not a.inherited)

        if inherited:
            stages = tuple(
                stage
                for stage in self.stages
                if stage.apply_to_new_fields
            )
            current = new_attributes
        else:
            stages = self.stages
            current = attributes

        current = self._run_stages(cls, stages, current)
        return self._merge_inherited(inherited, current)

    def _run_stages(self, cls, stages, attributes):
        current = tuple(attributes)
        written = {}
        conflicts = []

        for stage in stages:
            before = {attribute.name: attribute for attribute in current}
            result = tuple(stage.transformer(cls, list(current)))
            self._validate_result(stage, result)
            after = {attribute.name: attribute for attribute in result}

            for field_name, attribute in after.items():
                previous_attribute = before.get(field_name)
                if previous_attribute is None:
                    written[(field_name, "name")] = stage.name
                    continue

                for attribute_name in _FIELD_ATTRIBUTES:
                    previous_value = getattr(
                        previous_attribute, attribute_name
                    )
                    current_value = getattr(attribute, attribute_name)
                    if previous_value == current_value:
                        continue

                    key = (field_name, attribute_name)
                    first_stage = written.get(key)
                    if first_stage is not None and not (
                        self.allow_overrides or stage.allow_overrides
                    ):
                        conflicts.append(
                            FieldTransformerConflict(
                                field_name,
                                attribute_name,
                                first_stage,
                                stage.name,
                            )
                        )

                    written[key] = stage.name

            for field_name in before.keys() - after.keys():
                for attribute_name in _FIELD_ATTRIBUTES:
                    written.pop((field_name, attribute_name), None)

            current = result

        if conflicts:
            raise FieldTransformerConflictError(conflicts)

        return current

    @staticmethod
    def _validate_result(stage, result):
        from ._make import Attribute

        seen = set()
        for attribute in result:
            if not isinstance(attribute, Attribute):
                msg = (
                    f"Field transformer stage {stage.name!r} returned a "
                    f"non-Attribute value: {attribute!r}."
                )
                raise TypeError(msg)

            if attribute.name in seen:
                msg = (
                    f"Field transformer stage {stage.name!r} returned "
                    f"duplicate field {attribute.name!r}."
                )
                raise ValueError(msg)
            seen.add(attribute.name)

    @staticmethod
    def _merge_inherited(inherited, new):
        inherited_names = {attribute.name for attribute in inherited}
        new_names = {attribute.name for attribute in new}
        duplicate = inherited_names & new_names
        if duplicate:
            msg = (
                "A field transformer returned inherited field(s): "
                f"{', '.join(sorted(duplicate))}."
            )
            raise ValueError(msg)

        return (*inherited, *new)


def combine_field_transformers(*stages, allow_overrides=False):
    """
    Combine field transformers into named, sequentially executed stages.

    Args:
        stages:
            Stages to apply in declaration order.
        allow_overrides:
            Allow every later stage to override field attributes written by an
            earlier stage.

    Returns:
        A field transformer suitable for the *field_transformer* argument.

    .. versionadded:: 26.2.0
    """
    prepared_stages = []
    names = set()
    for stage_number, stage in enumerate(stages, start=1):
        if callable(stage) and not isinstance(stage, FieldTransformerStage):
            stage = FieldTransformerStage(
                getattr(stage, "__name__", f"stage_{stage_number}"),
                stage,
            )

        if not isinstance(stage, FieldTransformerStage):
            msg = (
                "Field transformer stages must be FieldTransformerStage "
                f"instances, got {stage!r}."
            )
            raise TypeError(msg)
        if not isinstance(stage.name, str) or not stage.name:
            msg = "Field transformer stage names must be non-empty strings."
            raise ValueError(msg)
        if not callable(stage.transformer):
            msg = f"Field transformer stage {stage.name!r} must be callable."
            raise TypeError(msg)
        if stage.name in names:
            msg = f"Duplicate field transformer stage name: {stage.name!r}."
            raise ValueError(msg)
        if not isinstance(stage.apply_to_new_fields, bool):
            msg = "Field transformer stage apply_to_new_fields must be a bool."
            raise TypeError(msg)
        if not isinstance(stage.allow_overrides, bool):
            msg = "Field transformer stage allow_overrides must be a bool."
            raise TypeError(msg)

        names.add(stage.name)
        prepared_stages.append(stage)

    return _StagedFieldTransformer(prepared_stages, allow_overrides)
