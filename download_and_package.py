import sys
import time
import json
import os
import tarfile
import shutil

import yaml
import boto3
import requests


SPLUNK_CLOUD_CONFIG = {
    "token": os.getenv("SPLUNK_TOKEN"),
    "appinspect_base_url": "https://appinspect.splunk.com/v1",
}


def read_yaml(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def download_file_from_s3(bucket_name, object_name, file_name):
    """Download a file from an S3 bucket."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    try:
        s3.download_file(bucket_name, object_name, file_name)
        print(f"Downloaded {object_name} from {bucket_name} to {file_name}")
    except Exception as e:
        print(f"Error downloading {object_name} from {bucket_name}: {e}")


def unpack_load_conf_and_repack(app):
    """Unpack the app, load environment configuration files and repack the app."""
    temp_dir = "temp_unpack"
    os.makedirs(temp_dir, exist_ok=True)

    # Unpack the tar.gz file
    with tarfile.open(f"{app}.tgz", "r:gz") as tar:
        tar.extractall(path=temp_dir)
    # Create default directory for unpacked app
    default_dir = f"{temp_dir}/{app}/default"
    os.makedirs(default_dir, exist_ok=True)
    # Load the environment configuration files
    app_dir = f"environments/{sys.argv[1]}/{app}"
    # Copy all .conf files in app_dir to temp_dir of unpacked app
    for file in os.listdir(app_dir):
        if file.endswith(".conf"):
            shutil.copy(f"{app_dir}/{file}", default_dir)
    # Repack the app and place it in the root directory
    with tarfile.open(f"{app}.tgz", "w:gz") as tar:
        for root, _, files in os.walk(f"{temp_dir}/{app}"):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, temp_dir)
                tar.add(full_path, arcname=arcname)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_yaml_file>")
        sys.exit(1)

    yaml_file_path = "environments/" + sys.argv[1] + "/deployment.yml"

    try:
        data = read_yaml(yaml_file_path)
    except FileNotFoundError:
        print(f"Error: The file '{yaml_file_path}' was not found.")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")

    # TODO NEXT
    ### 1. Retrieve all apps listed in deployment.yml from S3 ###

    # List all apps in yaml file and then their S3 bucket
    apps = [app for app in data["apps"]]
    s3_buckets = [data["apps"][app]["source"] for app in apps]
    app_direcotires = [data["apps"][app]["directory"] for app in apps]

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        object_name = directory
        file_name = f"downloaded_app/{app}.tgz"
        # Donwload app from S3
        download_file_from_s3(bucket, object_name, file_name)

        ### 2. Upload_local_configurateion ###
        if os.path.exists(f"environments/{sys.argv[1]}/{app}"):
            unpack_load_conf_and_repack(app)
        else:
            print(f"No configuration found for app {app}. Skipping.")


if __name__ == "__main__":
    main()
