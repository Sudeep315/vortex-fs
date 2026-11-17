from typing import List, Optional
from pydantic import BaseModel, Field
from vortex.core.types import ValueType


class Entity(BaseModel):
    """
    Represents a primary business domain entity (e.g. User, Merchant, Device)
    used as join keys across feature views.
    """
    name: str = Field(..., description="Unique logical name of the entity, e.g. 'user'")
    join_keys: List[str] = Field(default_factory=list, description="Keys in events/tables used to join (e.g. ['user_id'])")
    description: str = Field("", description="Human-readable description of this entity")
    value_type: ValueType = Field(default=ValueType.STRING, description="Data type of the entity primary key")

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entity):
            return self.name == other.name
        return False
