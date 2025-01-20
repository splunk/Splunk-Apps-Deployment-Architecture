import os
import boto3

from modules.splunkcloud import SplunkCloudConnector
from modules.apps_processing import AppFilesProcessor, DeploymentParser
from modules.report_generator import DeploymentReportGenerator

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

DEPLOYMENT_CONFIG_PATH = os.getenv("DEPLOYMENT_CONFIG_PATH")


def main():
    # Initiate deployment report
    deployment_report = DeploymentReportGenerator()
    # Initiate AppFilesProcessor object
    app_processor = AppFilesProcessor()
    # Initiate DeploymentParser object
    deployment_parser = DeploymentParser()
    ### 1. Validate data and retrieve all apps listed in deployment.yml from S3 ###
    data, _, _ = deployment_parser.parse()
    target_url = data["target"]["url"]

    # Initiate AwsS3Connector object
    s3_connector = boto3.client("s3")
    # Check for private apps
    if deployment_parser.has_private_apps():
        print("Found private apps in deployment.yml, starting deployment...")
        # List all apps in yaml file and then their S3 buckets
        apps = deployment_parser.get_private_apps()
        s3_buckets = deployment_parser.get_s3_buckets()
        app_directories = deployment_parser.get_app_directories()
        # Loop through all apps
        for app, bucket, directory in zip(apps, s3_buckets, app_directories):
            object_name = directory
            file_name = f"{app}.tgz"
            # Donwload app from S3
            try:
                s3_connector.download_file(bucket, object_name, file_name)
            except Exception as e:
                raise Exception(f"Error downloading {object_name} from {bucket}: {e}")

            ### 2. Upload_local_configuration ###
            # Check if the configuration exists for the app
            path = os.path.join(DEPLOYMENT_CONFIG_PATH, app)
            if path:
                app_processor.unpack_merge_conf_and_meta_repack(app, path)
            else:
                print(f"No configuration found for app {app}. Skipping.")

            ### 3. Validate app for Splunk Cloud ###
            # Initiate SplunkCloudConnector object
            cloud_connector = SplunkCloudConnector(target_url)
            appinspect_handler = cloud_connector.get_appinspect_handler()
            is_valid = appinspect_handler.validate(app)
            if not is_valid:
                print(f"App {app} failed validation. Skipping distribution.\n")
                deployment_report.add_data(app, ("report", appinspect_handler.report))
                deployment_report.add_data(app, ("validation", "failed"))
                deployment_report.add_data(
                    app, ("distribution", "failed due to app validation error")
                )
            # App is valid
            deployment_report.add_data(app, ("report", appinspect_handler.report))
            ### 4. If app is valid, distribute it ###
            dist_succeeded, dist_status = cloud_connector.distribute(app)
            if dist_succeeded:
                print(f"App {app} successfully distributed.\n")
                deployment_report.add_data(app, ("distribution", "success"))
            else:
                print(f"App {app} failed distribution.")
                deployment_report.add_data(
                    app,
                    (
                        "distribution",
                        f"failed with status code: {dist_status}",
                    ),
                )

    else:
        print("No private apps found in deployment.yml, skipping...")

    ### 5. Handle Splunkbase apps ###
    if deployment_parser.has_splunkbase_apps():
        print("Found Splunkbase apps in deployment.yml, starting deployment...")
        splunkbase_apps_dict = deployment_parser.get_splunkbase_apps()
        for splunkbase_app in splunkbase_apps_dict:
            app = splunkbase_apps_dict[splunkbase_app]
            app_name = splunkbase_app
            version = app["version"]
            install_status = cloud_connector.install(app_name, version)
            print(f"App {app_name} installation status: {install_status}")
            deployment_report.add_data(
                app_name,
                {"splunkbase_installation": install_status, "version": version},
            )
    else:
        print("No Splunkbase apps found in deployment.yml, skipping...")

    ### 6. Save deployment report to json file ###
    deployment_report.generate_report()


if __name__ == "__main__":
    main()
