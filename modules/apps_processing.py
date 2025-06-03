import sys
import os
import yaml
import shutil
import configparser
import tarfile
import json
import ksconf
import subprocess
from io import StringIO
from schema import (
    Schema,
    SchemaError,
    Or,
    Optional,
    Regex
)


deployment_schema = Schema({
    "target": {
        "url": str,
        "experience": Or("classic", "victoria")
    },
    "apps": {
        Optional(str): {
            "s3-bucket": str,
            "source": str,
            Optional("config"): [
                str
            ]
        }
    },
    "splunkbase-apps": {
        Optional(str): {
            "version": Regex(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
        }
    }
})

class DeploymentParser:
    """Class for parsing the deployment configuration file."""
    private_apps: dict = {}
    splunkbase_apps: dict = {}
    target: dict = {}

    def __init__(self):
        # Read and parse data
        if not "DEPLOYMENT_CONFIG_PATH" in os.environ:
            raise Exception(
                f"Error - Environment variable DEPLOYMENT_CONFIG_PATH does not exist."
            )
        yml_path = os.path.join(os.getenv("DEPLOYMENT_CONFIG_PATH"), "deployment.yml")

        try:
            with open(yml_path, "r") as file:
                data = yaml.safe_load(file)
                deployment_schema.validate(data)

                self.private_apps = data.get("apps", {})
                self.splunkbase_apps = data.get("splunkbase-apps", {})
                self.target = data.get("target", {})
        except FileNotFoundError:
            raise Exception(f"File not found: {yml_path}")
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing YAML file: {e}")
        except SchemaError as se:
            raise Exception(f"Error validating {yml_path}: {se}")

    def has_private_apps(self) -> bool:
        """
        Check if private apps are present in the deployment configuration.

        has_private_apps() -> bool
        """
        return True if self.private_apps else False

    def has_splunkbase_apps(self) -> bool:
        """
        Check if Splunkbase apps are present in the deployment configuration.

        has_splunkbase_apps() -> bool
        """
        return True if self.splunkbase_apps else False

    @property
    def url(self) -> str:
        """
        Return the targeted url from the deployment configuration.
        """
        return self.target["url"]

    @property
    def cloud_experience(self) -> str:
        """
        Return the targeted platform cloud experience from the deployment configuration.
        """
        return self.target["experience"]

    def get_bucket(self, app: str) -> str:
        """
        Return the app S3 bucket from the deployment configuration.

        get_bucket(app) -> str
        """
        return self.private_apps[app]["s3-bucket"]

    def get_app_path(self, app: str) -> str:
        """
        Return the app path from the deployment configuration.

        get_app_path(app) -> str
        """
        return self.private_apps[app]["source"]

    def get_app_configs(self, app: str) -> list:
        """
        Return a list of app configuration paths from the deployment configuration.

        get_app_configs(app) -> list
        """
        return self.private_apps[app]["config"]

    def get_version(self, app: str) -> str:
        """
        Return the Splunkbase app version from the deployment configuration.

        get_version(app) -> str
        """
        return self.splunkbase_apps[app]["version"]


class AppFilesProcessor:
    """Class for handling local app files and configurations."""

    def __init__(self, deployment_parser: DeploymentParser):
        self.deployment_config = deployment_parser

    def merge_or_copy_conf(self, source_path: str, dest_path: str) -> None:
        """Function to copy local configuration files to default or merge them using ksconf"""
        # Get the filename from the source path
        filename = os.path.basename(source_path)
        dest_file = os.path.join(dest_path, filename)

        # Check if the file exists in the destination directory
        if not os.path.exists(dest_file):
            # If the file doesn't exist, copy it
            shutil.copy(source_path, dest_path)
            print(f"Copied {filename} to {dest_path}")
        else:
            # If the file exists, merge the configurations using ksconf command
            print(f"Merging {filename} with existing file in {dest_path}")
            command = ["ksconf", "promote", filename, dest_file]
            try:
                # Run the command and capture the output
                result = subprocess.run(
                    command,
                    capture_output=True,  # Capture stdout and stderr
                    text=True,            # Decode output as text (Python 3.6+)
                    check=True            # Raise an exception on non-zero exit code
                )
                print("Command succeeded:")
                print(result.stdout)
                return result
            except subprocess.CalledProcessError as e:
                print("Command failed with an error:")
                print(e.stderr)
                raise


            print(f"Merged configuration saved to {dest_file}")

    def unpack_merge_conf_and_meta_repack(self, app: str, path: str) -> None:
        """Unpack the app, load environment configuration files and repack the app."""
        temp_dir = "temp_unpack"
        os.makedirs(temp_dir, exist_ok=True)

        # Unpack the tar.gz file
        with tarfile.open(f"{app}.tgz", "r:gz") as tar:
            tar.extractall(path=temp_dir)
        # Create default directory for unpacked app
        base_default_dir = f"{temp_dir}/{app}"
        # Load the environment configuration files
        app_dir = path
        # Copy all .conf files in app_dir to temp_dir of unpacked app
        for file in os.listdir(app_dir):
            if file.endswith(".conf"):
                default_dir = base_default_dir + "/default"
                os.makedirs(default_dir, exist_ok=True)
                source_path = os.path.join(app_dir, file)
                self.merge_or_copy_conf(source_path, default_dir)
        # Repack the app and place it in the root directory
        with tarfile.open(f"{app}.tgz", "w:gz") as tar:
            for root, _, files in os.walk(f"{temp_dir}/{app}"):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_dir)
                    tar.add(full_path, arcname=arcname)
