import sys
import os
import yaml
import shutil
import configparser
import tarfile
from io import StringIO


class AppFilesProcessor:
    """Class for handling local app files and configurations."""

    def __init__(self, yml_path):
        self.yml_path = yml_path

    def _read_yaml(self) -> dict:
        """Read and return the contents of a YAML file."""
        file_path = self.yml_path
        with open(file_path, "r") as file:
            return yaml.safe_load(file)

    def validate_data(self) -> tuple:
        """
        Validate the data in the YAML file.

        Return boolean values for private_apps and splunkbase_apps presence in the environment configuration

        validate_data(data) -> (dict, bool, bool)
        """
        try:
            data = self._read_yaml()
        except FileNotFoundError:
            print(f"Error: The file '{self.yml_path}' was not found.")
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            sys.exit(1)

        if "apps" not in data:
            print("Error: The 'apps' key is missing in deploy.yml fime.")
            sys.exit(1)
        if "target" not in data:
            print("Error: The 'target' key is missing in deploy.yml file.")
            sys.exit(1)
        if "url" not in data["target"]:
            print("Error: The 'url' key is missing in the 'target' section.")
            sys.exit(1)
        if "splunkbase-apps" not in data:
            print("Error: The 'splunkbase-apps' key is missing.")
            sys.exit(1)

        app_dict = data.get("apps", {})
        splunkbase_dict = data.get("splunkbase-apps", {})

        private_apps = True if app_dict else False
        splunkbase_apps = True if splunkbase_dict else False

        return data, private_apps, splunkbase_apps

    def _preprocess_empty_headers(self, file_path: str) -> list:
        """
        Preprocess the file to handle empty section headers by replacing `[]` with a valid section name.
        """
        valid_lines = []
        with open(file_path, "r") as file:
            for line in file:
                # Replace empty section headers with a placeholder
                if line.strip() == "[]":
                    valid_lines.append("[DEFAULT]\n")  # Or any placeholder section name
                else:
                    valid_lines.append(line)
        return valid_lines

    def _replace_default_with_empty_header(self, file_path: str) -> None:
        """
        Replace '[DEFAULT]' header with '[]' in the specified file.
        """
        with open(file_path, "r") as file:
            lines = file.readlines()

        with open(file_path, "w") as file:
            for line in lines:
                # Replace '[DEFAULT]' with '[]'
                if line.strip() == "[DEFAULT]":
                    file.write("[]\n")
                else:
                    file.write(line)

    def merge_or_copy_conf(self, source_path: str, dest_path: str) -> None:
        # Get the filename from the source path
        filename = os.path.basename(source_path)
        dest_file = os.path.join(dest_path, filename)

        # Check if the file exists in the destination directory
        if not os.path.exists(dest_file):
            # If the file doesn't exist, copy it
            shutil.copy(source_path, dest_path)
            print(f"Copied {filename} to {dest_path}")
        else:
            # If the file exists, merge the configurations
            print(f"Merging {filename} with existing file in {dest_path}")

            # Read the source file
            source_config = configparser.ConfigParser()
            source_config.read(source_path)

            # Read the destination file
            dest_config = configparser.ConfigParser()
            dest_config.read(dest_file)

            # Merge source into destination
            for section in source_config.sections():
                if not dest_config.has_section(section):
                    dest_config.add_section(section)
                for option, value in source_config.items(section):
                    dest_config.set(section, option, value)

            # Write the merged configuration back to the destination file
            with open(dest_file, "w") as file:
                dest_config.write(file)
            print(f"Merged configuration saved to {dest_file}")

    def merge_or_copy_meta(self, local_meta_file: str, default_dir: str) -> None:
        """Merge local.meta with default.meta"""
        filename = os.path.basename(local_meta_file)
        dest_file = os.path.join(default_dir, "default.meta")

        # Check if the file exists in the destination directory
        if not os.path.exists(dest_file):
            # If the file doesn't exist, copy it
            shutil.copy(local_meta_file, dest_file)
            print(f"Copied {filename} to {dest_file}")
        else:
            # If the file exists, merge the configurations
            print(f"Merging {filename} with existing file in {dest_file}")

            # Preprocess the default file
            default_preprocessed_lines = self._preprocess_empty_headers(dest_file)
            default_preprocessed_content = StringIO("".join(default_preprocessed_lines))

            # Read the default.meta file
            default_meta = configparser.ConfigParser()
            default_meta.read_file(default_preprocessed_content)

            # Preprocess the local file
            local_preprocessed_lines = self._preprocess_empty_headers(local_meta_file)
            local_preprocessed_content = StringIO("".join(local_preprocessed_lines))

            # Read the local.meta file
            local_meta = configparser.ConfigParser()
            local_meta.read_file(local_preprocessed_content)

            # Merge local.meta into default.meta
            for section in local_meta.sections():
                if not default_meta.has_section(section):
                    default_meta.add_section(section)
                for option, value in local_meta.items(section):
                    if default_meta.has_option(section, option):
                        # Merge logic: Option exists in both, decide whether to overwrite
                        default_value = default_meta.get(section, option)
                        if value != default_value:
                            print(
                                f"Conflict detected: {section} {option} - {default_value} -> {value}"
                            )
                            # Overwrite the option in default.meta
                            default_meta.set(section, option, value)
                    default_meta.set(section, option, value)

            # Write the merged configuration back to the output file
            with open(dest_file, "w") as file:
                default_meta.write(file)

            # Replace '[DEFAULT]' with '[]' in the output file
            self._replace_default_with_empty_header(dest_file)

            print(f"Merged metadata saved to {dest_file}")

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
        # Copy all metadata files in app_dir to temp_dir of unpacked app
        for file in os.listdir(app_dir):
            if file.endswith(".meta"):
                default_dir = base_default_dir + "/metadata"
                os.makedirs(default_dir, exist_ok=True)
                source_path = os.path.join(app_dir, file)
                self.merge_or_copy_meta(source_path, default_dir)
        # Repack the app and place it in the root directory
        with tarfile.open(f"{app}.tgz", "w:gz") as tar:
            for root, _, files in os.walk(f"{temp_dir}/{app}"):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_dir)
                    tar.add(full_path, arcname=arcname)
