from typing import Union, List, Literal, Optional, Annotated
from pydantic import BaseModel, Field

class BaseAction(BaseModel):
    time_offset: float = Field(default=0.0, ge=0.0)

class ClickAction(BaseAction):
    type: Literal["click"]
    button: str
    x: int
    y: int
    template_image: Optional[str] = None

class TypeAction(BaseAction):
    type: Literal["type"]
    key: str

ActionType = Annotated[Union[ClickAction, TypeAction], Field(discriminator='type')]

class Workflow(BaseModel):
    workflow_name: str
    created_at: str
    actions: List[ActionType]
