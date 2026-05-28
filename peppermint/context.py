from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Context:
    data: list[dict]
    artifacts: dict = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)

    @property
    def rows(self) -> list[dict]:
        return self.data

    def with_data(self, data: list[dict]) -> "Context":
        return Context(data=data, artifacts=self.artifacts, errors=self.errors)

    def with_artifact(self, name: str, value: Any) -> "Context":
        return Context(
            data=self.data,
            artifacts={**self.artifacts, name: value},
            errors=self.errors,
        )

    def with_error(self, row: dict) -> "Context":
        return Context(
            data=self.data,
            artifacts=self.artifacts,
            errors=[*self.errors, row],
        )

    def merge_errors(self, new_errors: list[dict]) -> "Context":
        return Context(
            data=self.data,
            artifacts=self.artifacts,
            errors=[*self.errors, *new_errors],
        )
