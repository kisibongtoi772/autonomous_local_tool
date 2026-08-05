from typing import Union, List, Literal, Optional, Annotated
from pydantic import BaseModel, Field


class BaseAction(BaseModel):
    enabled: bool = Field(default=True, description="Whether this action should be executed")
    breakpoint: bool = Field(default=False, description="Pause execution before this action")
    bookmark: bool = Field(default=False, description="Quick navigation bookmark marker")
    time_offset: float = Field(default=0.0, ge=0.0)
    # Reliability fields — optional on every action
    retry_count: int = Field(default=0, ge=0,
        description="How many times to retry this action if it fails (0 = no retry)")
    retry_delay: float = Field(default=0.5, ge=0.0,
        description="Seconds to wait between retries")
    color_tag: Optional[str] = Field(default=None, description="Visual badge color for UI")
    label: Optional[str] = Field(default=None, description="Custom name for this action")
    repeat: int = Field(default=1, ge=1, description="Number of times to repeat this action inline")


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
    search_region: Optional[list] = None
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
    condition_type: Literal["none", "while_found", "until_found"] = "none"
    condition_template: Optional[str] = None
    condition_confidence: float = 0.8
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
    search_region: Optional[list] = None


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
    search_region: Optional[list] = None
    then_actions: List['ActionType'] = Field(default_factory=list)
    else_actions: List['ActionType'] = Field(default_factory=list)


class WaitForTemplateAction(BaseAction):
    """Poll screen until template appears or timeout is reached."""
    type: Literal["wait_for_template"]
    template: str
    timeout: float = Field(default=10.0, gt=0.0,
        description="Max seconds to wait before raising an error")
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)
    search_region: Optional[list] = None
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


class AppFocusAction(BaseAction):
    """Bring an application to the foreground."""
    type: Literal["app_focus"]
    app_name: str
    launch_if_closed: bool = True


class NotificationAction(BaseAction):
    """Show an OS-level notification."""
    type: Literal["notification"]
    title: str = "Automator"
    message: str


class GroupAction(BaseAction):
    """A logical folder to group multiple actions together."""
    type: Literal["group"]
    name: str = "New Group"
    actions: List['ActionType'] = Field(default_factory=list)


class AssertColorAction(BaseAction):
    """Assert that a pixel has a specific HEX color."""
    type: Literal["assert_color"]
    x: int
    y: int
    color: str = Field(description="HEX color string (e.g. #FF0000)")
    tolerance: int = Field(default=10, ge=0, le=255, description="Allowed per-channel difference")


class IfColorAction(BaseAction):
    """Branch execution based on pixel color."""
    type: Literal["if_color"]
    x: int
    y: int
    color: str = Field(description="HEX color string (e.g. #FF0000)")
    tolerance: int = Field(default=10, ge=0, le=255)
    then_actions: List['ActionType'] = Field(default_factory=list)
    else_actions: List['ActionType'] = Field(default_factory=list)


ActionType = Annotated[
    Union[
        ClickAction, TypeAction, LoopAction, RunCommandAction,
        HotkeyAction, SleepAction, ScrollAction, ScreenshotAction,
        AssertTemplateAction, ClipboardAction, IfTemplateAction,
        WaitForTemplateAction, RunWorkflowAction, PromptUserAction,
        AppFocusAction, NotificationAction, CommentAction, GroupAction,
        AssertColorAction, IfColorAction,
    ],
    Field(discriminator='type')
]


class Workflow(BaseModel):
    workflow_name: str
    created_at: str
    actions: List[ActionType]
