from typing import Union, List, Literal, Optional, Annotated
from pydantic import BaseModel, Field

class BaseAction(BaseModel):
    time_offset: float = Field(default=0.0, ge=0.0)

class ClickAction(BaseAction):
    type: Literal["click"]
    x: int
    y: int
    template_image: Optional[str] = None
    button: str = "left"
    clicks: int = 1

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

class ScrollAction(BaseAction):
    type: Literal["scroll"]
    amount: int

class ScreenshotAction(BaseAction):
    type: Literal["screenshot"]
    filename: str

class AssertTemplateAction(BaseAction):
    type: Literal["assert_template"]
    template: str

class ClipboardAction(BaseAction):
    """Set clipboard to a fixed text value then optionally paste it."""
    type: Literal["clipboard"]
    text: str = ""
    action: Literal["copy", "paste", "set"] = "set"

class IfTemplateAction(BaseAction):
    """Branch execution: if template is found on screen, run 'then_actions', else run 'else_actions'."""
    type: Literal["if_template"]
    template: str
    then_actions: List['ActionType'] = Field(default_factory=list)
    else_actions: List['ActionType'] = Field(default_factory=list)

ActionType = Annotated[
    Union[
        ClickAction, TypeAction, LoopAction, RunCommandAction,
        HotkeyAction, SleepAction, ScrollAction, ScreenshotAction,
        AssertTemplateAction, ClipboardAction, IfTemplateAction
    ],
    Field(discriminator='type')
]

class Workflow(BaseModel):
    workflow_name: str
    created_at: str
    actions: List[ActionType]
