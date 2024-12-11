import sys
import time
import json
import os
import tarfile
import shutil

import yaml
import boto3
import requests
import itertools
import configparser


SPLUNK_CLOUD_CONFIG = {
    "token": os.getenv("SPLUNK_TOKEN"),
    "appinspect_base_url": "https://appinspect.splunk.com/v1",
}

def read_yaml(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, "r") as file:
        return yaml.safe_load(file)
    
def check_all_letter_cases(base_path, app_name):
    # Generate all case combinations of "app"
    case_variations = map("".join, itertools.product(*([char.lower(), char.upper()] for char in app_name)))
    
    # Check each variation in the path
    for variation in case_variations:
        path = os.path.join("environments", base_path, variation)
        if os.path.exists(path):
            print(f"Found: {path}")
            return path
    return None

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

def merge_or_copy_conf(source_path, dest_path):
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
        with open(dest_file, 'w') as file:
            dest_config.write(file)
        print(f"Merged configuration saved to {dest_file}")

def unpack_merge_conf_and_repack(app, path):
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
    app_dir = path
    # Copy all .conf files in app_dir to temp_dir of unpacked app
    for file in os.listdir(app_dir):
        if file.endswith(".conf"):
            source_path = os.path.join(app_dir, file)
            merge_or_copy_conf(source_path, default_dir)
    # Repack the app and place it in the root directory
    with tarfile.open(f"{app}.tgz", "w:gz") as tar:
        for root, _, files in os.walk(f"{temp_dir}/{app}"):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, temp_dir)
                tar.add(full_path, arcname=arcname)


def get_appinspect_token():
    """Authenticate to the Splunk Cloud."""
    url = "https://api.splunk.com/2.0/rest/login/splunk"
    username = os.getenv("SPLUNK_USERNAME")
    password = os.environ.get("SPLUNK_PASSWORD")

    response = requests.get(url, auth=(username, password))
    token = response.json()["data"]["token"]
    return token


def validation_request_helper(url, headers, files):
    try:
        response = requests.post(url, headers=headers, files=files, timeout=120)
        response_json = response.json()
        request_id = response_json["request_id"]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    return request_id


def cloud_validate_app(app, config):
    """Validate the app for the Splunk Cloud."""
    token = get_appinspect_token()
    base_url = config["appinspect_base_url"]
    url = f"{base_url}/app/validate"

    headers = {"Authorization": f"Bearer {token}"}
    app_file_path = f"{app}.tgz"

    print(f"Validating app {app}...")
    with open(app_file_path, "rb") as file:
        files = {"app_package": file}
        request_id = validation_request_helper(url, headers, files)
        headers = {"Authorization": f"Bearer {token}"}
        status_url = f"{base_url}/app/validate/status/{request_id}?included_tags=private_victoria"
        try:
            response_status = requests.get(status_url, headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None, None

        max_retries = 60  # Maximum number of retries
        retries = 0
        response_status_json = response_status.json()

        while response_status_json["status"] != "SUCCESS" and retries < max_retries:
            response_status = requests.get(status_url, headers=headers)
            response_status_json = response_status.json()
            retries += 1
            if response_status_json["status"] == "FAILURE":
                print(f"App {app} failed validation: {response_status_json['errors']}")
                break
            else:
                print(f"App {app} awaiting validation...")
                print(f"Current status: {response_status_json['status']}")
                time.sleep(10)
                response_status = requests.get(status_url, headers=headers)
                response_status_json = response_status.json()
                continue
        if retries == max_retries:
            print(f"App {app} validation timed out.")
            return

        print(f"Current status: {response_status_json['status']}")
        if response_status_json["status"] == "SUCCESS":
            print("App validation successful.")
            print("Installing app...")

        response_raport = requests.get(
            f"{base_url}/app/report/{request_id}?included_tags=private_victoria",
            headers=headers,
        )
        raport = response_raport.json()
        result = raport["summary"]
        print(result)

        return raport, token


def distribute_app(app, target_url, token):
    """Distribute the app to the target URL."""
    print(f"Distributing {app} to {target_url}")
    url = target_url
    admin_token = SPLUNK_CLOUD_CONFIG["token"]
    print(admin_token)
    headers = {
        "X-Splunk-Authorization": token,
        "Authorization": f"Bearer {admin_token}",
        "ACS-Legal-Ack": "Y",
    }
    file_path = f"{app}.tgz"
    try:
        with open(file_path, "rb") as file:
            response = requests.post(url, headers=headers, data=file)
        print(
            f"Distributed {app} to {target_url} with response: {response.status_code} {response.text}"
        )
    except Exception as e:
        print(f"Error distributing {app} to {target_url}: {e}")
        return 500

    return response.status_code