"""The module registry (modules.yaml): which apps Pantheon fronts, and where.

Everything else about a module is derived from its `name` — gateway path
`/<name>/`, systemd unit `<name>.service`, checkout `modules/<name>` — so an
entry is four fields.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


class ModuleEntry(BaseModel):
    name: str
    title: str
    port: int = Field(gt=0, lt=65536)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _url_safe(cls, value: str) -> str:
        if not _NAME.match(value):
            raise ValueError(f"module name {value!r} must match {_NAME.pattern}")
        return value

    @field_validator("title")
    @classmethod
    def _quote_safe(cls, value: str) -> str:
        # Interpolated into a quoted Caddyfile string by services/gateway.py.
        if not value.strip():
            raise ValueError("module title must not be empty")
        if any(c in value for c in '"\\\n\r'):
            raise ValueError(
                f"module title must not contain quotes, backslashes or newlines: {value!r}"
            )
        return value

    @property
    def path(self) -> str:
        """Gateway path, relative (no leading slash) per the module contract."""
        return f"{self.name}/"

    @property
    def unit(self) -> str:
        return f"{self.name}.service"


class ModulesConfig(BaseModel):
    modules: list[ModuleEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> "ModulesConfig":
        for attr in ("name", "port"):
            seen: set[object] = set()
            for module in self.modules:
                value = getattr(module, attr)
                if value in seen:
                    raise ValueError(f"duplicate module {attr}: {value}")
                seen.add(value)
        return self

    @property
    def enabled(self) -> list[ModuleEntry]:
        return [m for m in self.modules if m.enabled]
