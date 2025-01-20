import os
import json
from typing import Union


class DeploymentReportGenerator:
    """Class for generating deployment report."""

    def __init__(self):
        self.deployment_report = {}

    def __str__(self) -> str:
        return str(self.deployment_report)

    def add_data(self, key: str, value: Union[tuple, dict]) -> None:
        """Add data to deployment report."""
        deployment_report = self.deployment_report
        if key not in deployment_report:
            deployment_report[key] = {}
        # Handle situation if passed value is a dictionary
        if isinstance(value, dict):
            deployment_report[key].update(value)
        # Handle situation if passed value is a tuple
        elif isinstance(value, tuple):
            deployment_report[key][value[0]] = value[1]
        else:
            raise ValueError("Value must be a tuple or a dictionary.")

    def generate_report(self) -> None:
        """Generate deployment report."""
        DEPLOYMENT_CONFIG_PATH = os.getenv("DEPLOYMENT_CONFIG_PATH")
        report_prefix = f"{DEPLOYMENT_CONFIG_PATH.split('/')[-2]}_{DEPLOYMENT_CONFIG_PATH.split('/')[-1]}"
        output_dir = "artifacts"

        os.makedirs(output_dir, exist_ok=True)
        with open(f"{output_dir}/{report_prefix}_deployment_report.json", "w") as file:
            json.dump(self.deployment_report, file)
