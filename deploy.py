import sys
import json
import os

import yaml

from utils import *


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_yaml_file>")
        sys.exit(1)

    yaml_file_path = "environments/" + sys.argv[1] + "/deployment.yml"

    deployment_raport = {}

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
    target_url = data["target"]["url"]

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        object_name = directory
        file_name = f"{app}.tgz"
        # Donwload app from S3
        download_file_from_s3(bucket, object_name, file_name)

        ### 2. Upload_local_configuration ###
        # Check if the configuration exists for the app
        path = check_all_letter_cases(sys.argv[1], app)
        if path:
            unpack_merge_conf_and_repack(app, path)
        else:
            print(f"No configuration found for app {app}. Skipping.")

        ### 3. Validate app for Splunk Cloud ###
        raport, token = cloud_validate_app(app, SPLUNK_CLOUD_CONFIG)
        if raport is None:
            print(f"App {app} failed validation.")
            deployment_raport[app] = {"validation": "failed"}
            continue
        result = raport["summary"]
        deployment_raport[app] = raport
        ### 4. If app is valid, distribute it ###
        if (
            result["error"] == 0
            and result["failure"] == 0
            and result["manual_check"] == 0
        ):
            distribution_status = distribute_app(app, target_url, token)
            if distribution_status == 200:
                print(f"App {app} successfully distributed.")
                deployment_raport[app]["distribution"] = "success"
            else:
                print(f"App {app} failed distribution.")
                deployment_raport[app][
                    "distribution"
                ] = f"failed with status code: {distribution_status}"
        else:
            print(f"App {app} failed validation. Skipping distribution.")
            deployment_raport[app][
                "distribution"
            ] = "failed due to app validation error"

    ### 5. Save deployment raport to json file ###
    raport_prefix = f"{sys.argv[1].split('/')[-2]}_{sys.argv[1].split('/')[-1]}"
    output_dir = "artifacts"
    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/{raport_prefix}_deployment_raport.json", "w") as file:
        json.dump(deployment_raport, file)


if __name__ == "__main__":
    main()
