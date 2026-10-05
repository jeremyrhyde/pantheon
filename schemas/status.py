"""The optional module `GET /api/status` shape (docs/module-contract.md).

Pantheon renders it generically — it never interprets a label — so a module
can add stats without any Pantheon change.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Stat(BaseModel):
    label: str = Field(max_length=80)
    value: str | int | float | bool | None = None
    kind: Literal["number", "count", "time", "text", "percent"] = "number"
    warn: bool = False


class ModuleStatus(BaseModel):
    state: Literal["ok", "degraded", "error"]
    summary: str | None = Field(default=None, max_length=200)
    stats: list[Stat] = Field(default_factory=list, max_length=20)
