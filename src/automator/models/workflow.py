from typing import Union, List, Literal, Optional, Annotated
from pydantic import BaseModel, Field


class BaseAction(BaseModel):
    enabled: bool = Field(default=True, description="Whether this action should be executed")
    time_offset: float = Field(default=0.0, ge=0.0)
    # Reliability fields — optional on every action
    retry_count: int = Field(default=0, ge=0,
        description="How many times to retry this action if it fails (0 = no retry)")
    retry_delay: float = Field(default=0.5, ge=0.0,
        description="Seconds to wait between retries")


class CommentAction(BaseAction):
    """A visual separator or comment in the workflow."""
    type: Literal["comment"]
    text: str


class ClickAction(BaseAction):
    type: Literal["click"]
    x: int
    y: int
    template_image: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)
    offset_x: int = 0
    offset_y: int = 0
    move_duration: float = Field(default=0.0, ge=0.0, description="Seconds to smoothly move mouse before clicking")
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
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)


class ClipboardAction(BaseAction):
    """Set clipboard to a fixed text value then optionally paste it."""
    type: Literal["clipboard"]
    text: str = ""
    action: Literal["copy", "paste", "set"] = "set"


class IfTemplateAction(BaseAction):
    """Branch execution based on template presence."""
    type: Literal["if_template"]
    template: str
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)
    then_actions: List['ActionType'] = Field(default_factory=list)
    else_actions: List['ActionType'] = Field(default_factory=list)


class WaitForTemplateAction(BaseAction):
    """Poll screen until template appears or timeout is reached."""
    type: Literal["wait_for_template"]
    template: str
    timeout: float = Field(default=10.0, gt=0.0,
        description="Max seconds to wait before raising an error")
    interval: float = Field(default=0.5, gt=0.0,
        description="Polling interval in seconds")
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)
    on_timeout: Literal["error", "continue"] = Field(default="error",
        description="'error' stops the workflow; 'continue' logs a warning and moves on")


class RunWorkflowAction(BaseAction):
    """Invoke another workflow file as a subroutine (synchronous)."""
    type: Literal["run_workflow"]
    workflow_file: str = Field(
        description="Filename relative to workspace/ (e.g. setup_app.json)")


class PromptUserAction(BaseAction):
    """Pause workflow and ask user for confirmation or input."""
    type: Literal["prompt_user"]
    message: str = "Please confirm to continue."
    require_input: bool = False
    save_to_variable: Optional[str] = None


ActionType = Annotated[
    Union[
        ClickAction, TypeAction, LoopAction, RunCommandAction,
        HotkeyAction, SleepAction, ScrollAction, ScreenshotAction,
        AssertTemplateAction, ClipboardAction, IfTemplateAction,
        WaitForTemplateAction, RunWorkflowAction, PromptUserAction,
        CommentAction,
    ],
    Field(discriminator='type')
]


class Workflow(BaseModel):
    workflow_name: str
    created_at: str
    actions: List[ActionType]
