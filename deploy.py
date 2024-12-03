import sys
import time
import json
import os

import yaml
import boto3
import requests

SPLUNK_CLOUD_CONFIG = {
    "token": os.environ.get("SPLUNK_TOKEN"),
    "appinspect_base_url": "https://appinspect.splunk.com/v1"
}

def read_yaml(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def download_file_from_s3(bucket_name, object_name, file_name):
    """Download a file from an S3 bucket."""
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    try:
        s3.download_file(bucket_name, object_name, file_name)
        print(f"Downloaded {object_name} from {bucket_name} to {file_name}")
    except Exception as e:
        print(f"Error downloading {object_name} from {bucket_name}: {e}")

def get_splunk_cloud_token():
    """Authenticate to the Splunk Cloud."""
    url = "https://api.splunk.com/2.0/rest/login/splunk"
    username = os.getenv("SPLUNK_USERNAME")
    password = os.environ.get("SPLUNK_PASSWORD")

    response = requests.get(url, auth=(username, password))
    token = response.json()['data']['token']
    return token

def cloud_validate_app(app, config):
    """Validate the app for the Splunk Cloud."""
    token = get_splunk_cloud_token()
    base_url = config['appinspect_base_url']
    url = f"{base_url}/app/validate"

    headers = {"Authorization": f"Bearer {token}"}
    app_file_path = f"{app}.tgz"

    print(f"Validating app {app}...")
    with open(app_file_path, 'rb') as file:
        files = {"app_package": file}

        response = requests.post(url, headers=headers, files=files, timeout=120)
        response_json = response.json()
        request_id = response_json['request_id']

        headers = {"Authorization": f"Bearer {token}"}
        status_url = f"{base_url}/app/validate/status/{request_id}?included_tags=private_victoria"
        response_status = requests.get(status_url, headers=headers)

        max_retries = 60  # Maximum number of retries
        retries = 0
        response_status_json = response_status.json()

        while response_status_json['status'] != "SUCCESS" and retries < max_retries:
            response_status = requests.get(status_url, headers=headers)
            response_status_json = response_status.json()
            retries += 1
            if response_status_json['status'] == "FAILURE":
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
        if response_status_json['status'] == "SUCCESS":
            print("App validation successful.")
            print("Installing app...")

        response_raport = requests.get(f"{base_url}/app/report/{request_id}?included_tags=private_victoria", headers=headers)
        raport = response_raport.json()
        result = raport['summary']
        print(result)

        return raport, token

def distribute_app(app, target_url, token):
    """Distribute the app to the target URL."""
    print(f"Distributing {app} to {target_url}")
    url = target_url
    admin_token = SPLUNK_CLOUD_CONFIG['token']
    headers = {
        'X-Splunk-Authorization': token,
        'Authorization': f'Bearer {admin_token}',
        'ACS-Legal-Ack': 'Y'
    }
    file_path = f"{app}.tgz"
    with open(file_path, 'rb') as file:
        response = requests.post(url, headers=headers, data=file)
    print(f"Distributed {app} to {target_url} with response: {response.status_code} {response.text}")
    return response.status_code

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_yaml_file>")
        sys.exit(1)

    yaml_file_path =  sys.argv[1] + "/deployment.yml"

    deployment_raport = {}

    try:
        data = read_yaml(yaml_file_path)
        print("YAML file contents:")
        print(data)
    except FileNotFoundError:
        print(f"Error: The file '{yaml_file_path}' was not found.")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")

    # TODO NEXT
    # 1. Retrieve all apps listed in deployment.yml from S3

    # List all apps in yaml file and then their S3 bucket
    apps = [app for app in data['apps']]
    s3_buckets = [data['apps'][app]['source'] for app in apps]
    app_direcotires = [data['apps'][app]['directory'] for app in apps]
    target_url = data['target']['url']

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        print(f"App: {app}, Bucket: {bucket}, Directory: {directory}")

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        object_name = directory
        file_name = f"{app}.tgz"
        # Donwload app from S3
        download_file_from_s3(bucket, object_name, file_name)
        # Validate app for Splunk Cloud
        raport,token = cloud_validate_app(app, SPLUNK_CLOUD_CONFIG)
        result = raport['summary']
        deployment_raport[app] = raport
        # If app is valid, distribute it
        if result['error'] == 0 and result['failure'] == 0 and result['manual_check'] == 0:
            distribution_status = distribute_app(app, target_url, token)
            if distribution_status == 200:
                print(f"App {app} successfully distributed.")
                deployment_raport[app]['distribution'] = 'success'
            else:
                print(f"App {app} failed distribution.")
                deployment_raport[app]['distribution'] = f'failed with status code: {distribution_status}'
        else:
            print(f"App {app} failed validation. Skipping distribution.")
            deployment_raport[app]['distribution'] = 'failed due to app validation error'

    # Save deployment raport to json file
    raport_prefix = f"{sys.argv[1].split('/')[-2]}_{sys.argv[1].split('/')[-1]}"
    output_dir = "artifacts"
    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/{raport_prefix}_deployment_raport.json", 'w') as file:
            json.dump(deployment_raport, file)
    
    # 2. If config key is set in deployment.yml for each app, open tgz, merge configuration, repackage
    configs = [(app, data['apps'][app]['config']) for app in apps if 'config' in data['apps'][app]]

if __name__ == "__main__":
    main()
