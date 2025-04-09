import os
import boto3

from modules.splunk_cloud import SplunkCloudConnector
from modules.apps_processing import AppFilesProcessor, DeploymentParser
from modules.report_generator import DeploymentReportGenerator

DEPLOYMENT_CONFIG_PATH = os.getenv("DEPLOYMENT_CONFIG_PATH")


def main():
    # Initiate deployment report
    deployment_report = DeploymentReportGenerator()
    # Initiate AwsS3Connector object
    s3_connector = boto3.client("s3")
    # Initiate DeploymentParser object
    config = DeploymentParser()
    # Initiate AppFilesProcessor object
    app_processor = AppFilesProcessor(config)
    # Initiate SplunkCloudConnector object
    cloud_connector = SplunkCloudConnector(config.url, config.cloud_experience)

    # Check for private apps
    if config.has_private_apps():
        print("Found private apps, starting deployment...")
        # Loop through all apps
        for app in config.private_apps.keys():
            bucket = config.get_bucket(app)
            app_path = config.get_app_path(app)
            file_name = f"{app}.tgz"
            # Donwload app from S3
            try:
                s3_connector.download_file(bucket, app_path, file_name)
            except Exception as e:
                raise Exception(f"Error downloading {app_path} from {bucket}: {e}")

            ### Upload_local_configuration ###
            # Check whether the app needs specific configs for this env
            path = os.path.join(DEPLOYMENT_CONFIG_PATH, app)
            if len(config.get_app_configs(app)) > 0:
                app_processor.unpack_merge_conf_and_meta_repack(app, path)
            else:
                print(f"No configurations needed for app {app}. Skipping.")

            ### Validate app for Splunk Cloud ###
            appinspect_handler = cloud_connector.get_appinspect_handler()
            is_valid = appinspect_handler.validate(app)
            if not is_valid:
                print(f"App {app} failed validation. Skipping distribution.\n")
                deployment_report.add_data(app, ("report", appinspect_handler.report))
                deployment_report.add_data(app, ("validation", "failed"))
                deployment_report.add_data(
                    app, ("distribution", "failed due to app validation error")
                )
                continue
            ### App is valid: distribute it ###
            deployment_report.add_data(app, ("report", appinspect_handler.report))
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
        print("No private apps found, skipping...")

    ### Handle Splunkbase apps ###
    if config.has_splunkbase_apps():
        print("Found Splunkbase apps, starting deployment...")
        for splunkbase_app in config.splunkbase_apps.keys():
            version = config.get_version(splunkbase_app)
            install_status = cloud_connector.install(splunkbase_app, version)
            print(f"App {splunkbase_app} installation status: {install_status}")
            deployment_report.add_data(
                splunkbase_app,
                {"splunkbase_installation": install_status, "version": version},
            )
    else:
        print("No Splunkbase apps found, skipping...")

    ### Save deployment report to json file ###
    deployment_report.generate_report()


if __name__ == "__main__":
    main()
