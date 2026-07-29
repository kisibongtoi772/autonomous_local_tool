import os

# Default Paths
WORKFLOW_FILE = os.getenv("AUTOMATOR_WORKFLOW_FILE", "workflow.json")
TEMPLATES_DIR = os.getenv("AUTOMATOR_TEMPLATES_DIR", "templates")

# Screen Recording / Vision config
CONFIDENCE_THRESHOLD = float(os.getenv("AUTOMATOR_CONFIDENCE", "0.8"))
TEMPLATE_SIZE = int(os.getenv("AUTOMATOR_TEMPLATE_SIZE", "60"))
