#!/usr/bin/env python3
"""Read-only capability registry; discovery never proves runtime provenance."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any
from parallel_manifest import ContractError

@dataclass(frozen=True)
class Capability:
    profile_id: str; model: str; effort: str; sandbox_mode: str; entrypoint: str; available: bool=True; source: str=""
    def as_dict(self): return {"profile_id":self.profile_id,"model":self.model,"effort":self.effort,"sandbox_mode":self.sandbox_mode,"entrypoint":self.entrypoint,"available":self.available,"source":self.source}

class CapabilityRegistry:
    def __init__(self, capabilities=()): self._items={c.profile_id:c for c in capabilities}
    @classmethod
    def from_profiles(cls, profile_dir: str|Path):
        items=[]
        for path in sorted(Path(profile_dir).glob("*.toml")):
            data=tomllib.loads(path.read_text(encoding="utf-8")); name=data.get("name"); model=data.get("model"); effort=data.get("model_reasoning_effort"); sandbox=data.get("sandbox_mode")
            if not all(isinstance(x,str) and x for x in (name,model,effort,sandbox)): raise ContractError("invalid profile metadata")
            items.append(Capability(name,model,effort,sandbox,"profile:"+name,True,str(path)))
        return cls(items)
    def get(self, profile_id): return self._items.get(profile_id)
    def require(self, profile_id, model, effort, sandbox_mode):
        item=self.get(profile_id)
        if item is None or not item.available: raise ContractError("capability unavailable")
        if (item.model,item.effort,item.sandbox_mode)!=(model,effort,sandbox_mode): raise ContractError("capability contract mismatch")
        return item
    def as_dict(self): return {key:value.as_dict() for key,value in sorted(self._items.items())}
