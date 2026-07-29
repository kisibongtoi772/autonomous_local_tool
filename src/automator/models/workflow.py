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

class LoopAction(BaseAction):
    type: Literal["loop"]
    count: int = Field(default=1, ge=1)
    actions: List['ActionType']

class RunCommandAction(BaseAction):
    type: Literal["run_command"]
    command: str
    wait: bool = False

class HotkeyAction(BaseAction):
    type: Literal["hotkey"]
    keys: List[str]

class SleepAction(BaseAction):
    type: Literal["sleep"]
    duration: float = Field(..., gt=0.0)

ActionType = Annotated[Union[ClickAction, TypeAction, LoopAction, RunCommandAction, HotkeyAction, SleepAction], Field(discriminator='type')]

class Workflow(BaseModel):
    workflow_name: str
    created_at: str
    actions: List[ActionType]
