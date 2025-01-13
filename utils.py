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
import xml.etree.ElementTree as ET


SPLUNK_APPINSPECT_BASE_URL = "https://appinspect.splunk.com/v1"
SPLUNKBASE_BASE_URL = "https://splunkbase.splunk.com/api/account:login"
SPLUNK_AUTH_BASE_URL = "https://api.splunk.com/2.0/rest/login/splunk"

def read_yaml(file_path: str) -> dict:
    """Read and return the contents of a YAML file."""
    with open(file_path, "r") as file:
        return yaml.safe_load(file)

def check_all_letter_cases(base_path: str, app_name: str) -> str:
    """Check all letter cases for the app configuration."""
    # Generate all case combinations of "app"
    case_variations = map("".join, itertools.product(*([char.lower(), char.upper()] for char in app_name)))

    # Check each variation in the path
    for variation in case_variations:
        path = os.path.join("environments", base_path, variation)
        if os.path.exists(path):
            print(f"Found: {path}")
            return path
    return None

def validate_data(data: dict) -> tuple:
    """
    Validate the data in the YAML file.

    Return boolean values for private_apps and splunkbase_apps presence in the environment configuration

    validate_data(data) -> (bool, bool)
    """
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

    return private_apps, splunkbase_apps

def download_file_from_s3(bucket_name: str, object_name: str, file_name: str) -> None:
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

def merge_or_copy_conf(source_path: str, dest_path: str) -> None:
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

def unpack_merge_conf_and_repack(app: str, path: str) -> None:
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


def get_appinspect_token() -> str:
    """
    Authenticate to the Splunk Cloud.

    get_appinspect_token() -> token : str
    """
    url = SPLUNK_AUTH_BASE_URL
    username = os.getenv("SPLUNK_USERNAME")
    password = os.getenv("SPLUNK_PASSWORD")

    response = requests.get(url, auth=(username, password))
    token = response.json()["data"]["token"]
    return token


def validation_request_helper(url: str, headers: dict , files: dict) -> str:
    """
    Helper function to make a validation request and return the request ID.

    validation_request_helper(url, headers, files) -> request_id : str
    """
    try:
        response = requests.post(url, headers=headers, files=files, timeout=120)
        response_json = response.json()
        request_id = response_json["request_id"]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    return request_id


def cloud_validate_app(app: str) -> tuple:
    """
    Validate the app for the Splunk Cloud.

    cloud_validate_app(app) -> report : dict, token : str
    """
    token = get_appinspect_token()
    base_url = SPLUNK_APPINSPECT_BASE_URL
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

        response_report = requests.get(
            f"{base_url}/app/report/{request_id}?included_tags=private_victoria",
            headers=headers,
        )
        report = response_report.json()
        result = report["summary"]
        print(result)

        return report, token


def distribute_app(app: str, target_url: str, token: str) -> int:
    """
    Distribute the app to the target URL.

    distribute_app(app, target_url, token) -> status_code : int
    """
    print(f"Distributing {app} to {target_url}")
    url = target_url
    admin_token = os.getenv("SPLUNK_TOKEN")
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

def authenticate_splunkbase() -> str:
    """
    Authenticate to Splunkbase.

    authenticate_splunkbase() -> token : str
    """
    url = SPLUNKBASE_BASE_URL
    data = {
        'username': os.getenv("SPLUNK_USERNAME"),
        'password': os.getenv("SPLUNK_PASSWORD")
    }
    response = requests.post(url, data=data)

    if response.ok:
        # Parse the XML response
        xml_root = ET.fromstring(response.text)
        # Extract the token from the <id> tag
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}  # Define the namespace
        splunkbase_token = xml_root.find('atom:id', namespace).text  # Find the <id> tag with the namespace
        return splunkbase_token
    else:
        print("Splunkbase login failed!")
        print(f"Status code: {response.status_code}")
        print(response.text)
        return None

def install_splunkbase_app(app: str, app_id: str, version: str, target_url: str, token: str, licence: str) -> str:
    """
    Install a Splunkbase app.

    install_splunkbase_app(app, app_id, version, target_url, token, licence) -> status : str
    """
    # Authenticate to Splunkbase
    splunkbase_token = authenticate_splunkbase()
    # Install the app
    url = f"{target_url}?splunkbase=true"

    headers = {
        'X-Splunkbase-Authorization': splunkbase_token,
        'ACS-Licensing-Ack': licence,
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    data = {
        'splunkbaseID': app_id,
        'version': version
    }

    response = requests.post(url, headers=headers, data=data)
    # Handle the case where the app is already installed
    if response.status_code == 409:
        print(f"App {app} is already installed.")
        print(f"Updating app {app} to version {version}...")
        # Get app name
        url = f"https://splunkbase.splunk.com/api/v1/app/{app_id}"
        response = requests.get(url)
        app_name = response.json().get('appid')
        print(f"App name: {app_name}")
        # Update the app
        url = f"{target_url}/{app_name}"
        data = {
            'version': version
        }
        response = requests.patch(url, headers=headers, data=data)
        return "success - existing app updated"
    elif response.ok:
        request_status = response.json()['status']
        print(f"Request status: {request_status}")
        if request_status in ("installed", "processing"):
            print(f"App {app} version {version} installation successful.")
            return "success"
        else:
            print(f"App {app} version {version} installation failed.")
            return f"failed with status: {request_status} - {response.text}"
    else:
        print("Request failed!")
        print(f"Status code: {response.status_code}")
        print(response.text)
        return f"failed with status code: {response.status_code} - {response.text}"
    
def get_app_id(app_name: str) -> str:
    """
    Get the Splunkbase app ID.

    get_app_id(app_name) -> app_id : str
    """
    url = f"https://splunkbase.splunk.com/api/v1/app"
    params = {
        "query": app_name,
        "limit": 1
    }
    response = requests.get(url, params=params)
    if len(response.json().get('results')) > 0:
        app_id = response.json().get('results')[0].get('uid')
        return app_id
    else:
        print(f"App {app_name} not found on Splunkbase.")
        return None
    
def get_license_url(app_name: str) -> str:
    """
    Get the licence URL for a Splunkbase app.

    get_licence_url(app_name) -> licence_url : str
    """
    url = f"https://splunkbase.splunk.com/api/v1/app"
    params = {
        "query": app_name,
        "limit": 1
    }
    response = requests.get(url, params=params)
    if len(response.json().get('results')) > 0:
        license_url = response.json().get('results')[0].get('license_url')
        return license_url
    else:
        print(f"App {app_name} not found on Splunkbase.")
        return None
