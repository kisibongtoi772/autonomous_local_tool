import os

# Default Paths
WORKSPACE_DIR = os.getenv("AUTOMATOR_WORKSPACE_DIR", "workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

WORKFLOW_FILE = os.getenv("AUTOMATOR_WORKFLOW_FILE", os.path.join(WORKSPACE_DIR, "workflow.json"))
TEMPLATES_DIR = os.getenv("AUTOMATOR_TEMPLATES_DIR", os.path.join(WORKSPACE_DIR, "templates"))
os.makedirs(TEMPLATES_DIR, exist_ok=True)

SNAPSHOTS_DIR = os.path.join(WORKSPACE_DIR, "snapshots")
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

VARIABLES_FILE = os.path.join(WORKSPACE_DIR, "variables.json")
RUN_HISTORY_FILE = os.path.join(WORKSPACE_DIR, "run_history.json")
SCHEDULES_FILE = os.path.join(WORKSPACE_DIR, "schedules.json")

# Screen Recording / Vision config
CONFIDENCE_THRESHOLD = float(os.getenv("AUTOMATOR_CONFIDENCE", "0.8"))
TEMPLATE_SIZE = int(os.getenv("AUTOMATOR_TEMPLATE_SIZE", "60"))
