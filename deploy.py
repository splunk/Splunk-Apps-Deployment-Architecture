import sys
import json
import os

from modules.splunkcloud import SplunkCloudConnector
from modules.aws_s3 import AwsS3Connector
from modules.apps_processing import AppFilesProcessor

# FOR LOCAL TESTING
# from dotenv import load_dotenv
# load_dotenv(dotenv_path="local.env")

SPLUNK_USERNAME = os.getenv("SPLUNK_USERNAME")
SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD")
SPLUNK_TOKEN = os.getenv("SPLUNK_TOKEN")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_yaml_file>")
        sys.exit(1)

    yaml_file_path = "environments/" + sys.argv[1] + "/deployment.yml"

    # Initiate deployment report
    deployment_report = {}

    # Initiate AppFilesProcessor object
    app_processor = AppFilesProcessor(yaml_file_path)

    ### 1. Validate data and retrieve all apps listed in deployment.yml from S3 ###
    data, private_apps, splunkbase_apps = app_processor.validate_data()
    # List all apps in yaml file and then their S3 bucket
    if private_apps:
        apps = data.get("apps", {}).keys()
        s3_buckets = [data["apps"][app]["s3-bucket"] for app in apps]
        app_directories = [data["apps"][app]["source"] for app in apps]
    target_url = data["target"]["url"]

    # Initiate AwsS3Connector object
    s3_connector = AwsS3Connector(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # Check for private apps
    if private_apps:
        print("Found private apps in deployment.yml, starting deployment...")
        # Loop through all apps
        for app, bucket, directory in zip(apps, s3_buckets, app_directories):
            object_name = directory
            file_name = f"{app}.tgz"
            # Donwload app from S3
            s3_connector.download_file_from_s3(bucket, object_name, file_name)

            ### 2. Upload_local_configuration ###
            # Check if the configuration exists for the app
            path = os.path.join("environments", sys.argv[1], app)
            print(path)
            if path:
                app_processor.unpack_merge_conf_and_meta_repack(app, path)
            else:
                print(f"No configuration found for app {app}. Skipping.")

            ### 3. Validate app for Splunk Cloud ###
            # Initiate SplunkCloudConnector object
            cloud_connector = SplunkCloudConnector(
                SPLUNK_USERNAME, SPLUNK_PASSWORD, SPLUNK_TOKEN, target_url
            )
            report, token = cloud_connector.cloud_validate_app(app)
            if report is None:
                print(f"App {app} failed validation.")
                deployment_report[app] = {"validation": "failed"}
                continue
            result = report["summary"]
            deployment_report[app] = report
            ### 4. If app is valid, distribute it ###
            if (
                result["error"] == 0
                and result["failure"] == 0
                and result["manual_check"] == 0
            ):
                distribution_status = cloud_connector.distribute_app(app, token)
                if distribution_status == 200:
                    print(f"App {app} successfully distributed.\n")
                    deployment_report[app]["distribution"] = "success"
                else:
                    print(f"App {app} failed distribution.")
                    deployment_report[app][
                        "distribution"
                    ] = f"failed with status code: {distribution_status}"
            else:
                print(f"App {app} failed validation. Skipping distribution.\n")
                deployment_report[app][
                    "distribution"
                ] = "failed due to app validation error"
    else:
        print("No private apps found in deployment.yml, skipping...")

    ### 5. Handle Splunkbase apps ###
    if splunkbase_apps:
        print("Found Splunkbase apps in deployment.yml, starting deployment...")
        splunkbase_apps_dict = data.get("splunkbase-apps", {})
        for splunkbase_app in splunkbase_apps_dict:
            app = splunkbase_apps_dict[splunkbase_app]
            app_name = splunkbase_app
            version = app["version"]
            app_id = cloud_connector.get_app_id(app_name)
            license = cloud_connector.get_license_url(app_name)
            install_status = cloud_connector.install_splunkbase_app(
                app_name, app_id, version, license
            )
            print(f"App {app_name} installation status: {install_status}")
            deployment_report[app_name] = {
                "splunkbase_installation": install_status,
                "version": version,
                "app_id": app_id,
            }
    else:
        print("No Splunkbase apps found in deployment.yml, skipping...")

    ### 6. Save deployment report to json file ###
    report_prefix = f"{sys.argv[1].split('/')[-2]}_{sys.argv[1].split('/')[-1]}"
    output_dir = "artifacts"
    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/{report_prefix}_deployment_report.json", "w") as file:
        json.dump(deployment_report, file)


if __name__ == "__main__":
    main()
