import os
import requests
import time

import xml.etree.ElementTree as ET


class SplunkCloudConnector:
    """Class for connecting to Splunk Cloud and Splunkbase."""

    SPLUNK_AUTH_BASE_URL = "https://api.splunk.com/2.0/rest/login/splunk"
    SPLUNK_APPINSPECT_BASE_URL = "https://appinspect.splunk.com/v1"
    SPLUNKBASE_BASE_URL = "https://splunkbase.splunk.com/api/account:login"
    SPLUNKBASE_APP_URL = "https://splunkbase.splunk.com/api/v1/app"

    SPLUNK_CLOUD_APP_INSTALL_ENDPOINT = "/adminconfig/v2/apps/victoria"

    def __init__(
        self,
        splunk_username: str = None,
        splunk_password: str = None,
        splunk_token: str = None,
        splunk_host: str = None,
    ):
        self.splunk_username = splunk_username
        self.splunk_password = splunk_password
        self.splunk_token = splunk_token
        self.splunk_host = splunk_host

    def get_appinspect_token(self) -> str:
        """
        Authenticate to the Splunk Cloud.

        get_appinspect_token() -> token : str
        """
        url = self.SPLUNK_AUTH_BASE_URL
        username = self.splunk_username
        password = self.splunk_password

        response = requests.get(url, auth=(username, password))
        token = response.json()["data"]["token"]
        return token

    def validation_request_helper(self, url: str, headers: dict, files: dict) -> str:
        """
        Helper function to make a validation request and return the request ID.

        validation_request_helper(url, headers, files) -> request_id : str
        """
        try:
            response = requests.post(url, headers=headers, files=files, timeout=120)
            response_json = response.json()
            request_id = response_json["request_id"]
        except requests.exceptions.RequestException as e:
            print(f"Error making app validation request: {e}")
            return None
        return request_id

    def cloud_validate_app(self, app: str) -> tuple:
        """
        Validate the app for the Splunk Cloud.

        cloud_validate_app(app) -> report : dict, token : str
        """
        token = self.get_appinspect_token()
        base_url = self.SPLUNK_APPINSPECT_BASE_URL
        url = f"{base_url}/app/validate"

        headers = {"Authorization": f"Bearer {token}"}
        app_file_path = f"{app}.tgz"

        print(f"Validating app {app}...")
        with open(app_file_path, "rb") as file:
            files = {"app_package": file}
            request_id = self.validation_request_helper(url, headers, files)
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
                    print(
                        f"App {app} failed validation: {response_status_json['errors']}"
                    )
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

    def distribute_app(self, app: str, token: str) -> int:
        """
        Distribute the app to the target URL.

        distribute_app(app, target_url, token) -> status_code : int
        """
        print(f"Distributing {app} to {self.splunk_host}")
        base_url = self.splunk_host
        url = base_url + self.SPLUNK_CLOUD_APP_INSTALL_ENDPOINT
        admin_token = self.splunk_token
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
                f"Distributed {app} to {base_url} with response: {response.status_code} {response.text}"
            )
        except Exception as e:
            print(f"Error distributing {app} to {self.splunk_host}: {e}")
            return 500

        return response.status_code

    def authenticate_splunkbase(self) -> str:
        """
        Authenticate to Splunkbase.

        authenticate_splunkbase() -> token : str
        """
        url = self.SPLUNKBASE_BASE_URL
        data = {"username": self.splunk_username, "password": self.splunk_password}
        response = requests.post(url, data=data)

        if response.ok:
            # Parse the XML response
            xml_root = ET.fromstring(response.text)
            # Extract the token from the <id> tag
            namespace = {"atom": "http://www.w3.org/2005/Atom"}  # Define the namespace
            splunkbase_token = xml_root.find(
                "atom:id", namespace
            ).text  # Find the <id> tag with the namespace
            return splunkbase_token
        else:
            print("Splunkbase login failed!")
            print(f"Status code: {response.status_code}")
            print(response.text)
            return None

    def install_splunkbase_app(
        self, app: str, app_id: str, version: str, licence: str
    ) -> str:
        """
        Install a Splunkbase app.

        install_splunkbase_app(app, app_id, version, target_url, token, licence) -> status : str
        """
        # Authenticate to Splunkbase
        splunkbase_token = self.authenticate_splunkbase()
        # Install the app
        base_url = self.splunk_host
        target_url = base_url + self.SPLUNK_CLOUD_APP_INSTALL_ENDPOINT
        token = self.splunk_token

        url = f"{target_url}?splunkbase=true"

        headers = {
            "X-Splunkbase-Authorization": splunkbase_token,
            "ACS-Licensing-Ack": licence,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"splunkbaseID": app_id, "version": version}

        response = requests.post(url, headers=headers, data=data)
        # Handle the case where the app is already installed
        if response.status_code == 409:
            print(f"App {app} is already installed.")
            print(f"Updating app {app} to version {version}...")
            # Get app name
            url = f"https://splunkbase.splunk.com/api/v1/app/{app_id}"
            response = requests.get(url)
            app_name = response.json().get("appid")
            print(f"App name: {app_name}")
            # Update the app
            url = f"{target_url}/{app_name}"
            data = {"version": version}
            response = requests.patch(url, headers=headers, data=data)
            return "success - existing app updated"
        elif response.ok:
            request_status = response.json()["status"]
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

    def get_app_id(self, app_name: str) -> str:
        """
        Get the Splunkbase app ID.

        get_app_id(app_name) -> app_id : str
        """
        url = self.SPLUNKBASE_APP_URL
        params = {"query": app_name, "limit": 1}
        response = requests.get(url, params=params)
        if len(response.json().get("results")) > 0:
            app_id = response.json().get("results")[0].get("uid")
            return app_id
        else:
            print(f"App {app_name} not found on Splunkbase.")
            return None

    def get_license_url(self, app_name: str) -> str:
        """
        Get the licence URL for a Splunkbase app.

        get_licence_url(app_name) -> licence_url : str
        """
        url = self.SPLUNKBASE_APP_URL
        params = {"query": app_name, "limit": 1}
        response = requests.get(url, params=params)
        if len(response.json().get("results")) > 0:
            license_url = response.json().get("results")[0].get("license_url")
            return license_url
        else:
            print(f"App {app_name} not found on Splunkbase.")
            return None
