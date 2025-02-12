import os
import requests
import time

import xml.etree.ElementTree as ET

# TODO remove following. Used for local testing only.
# from dotenv import load_dotenv
# load_dotenv(dotenv_path="local.env")


class SplunkCloudAccountConfig:
    username: str = os.getenv("SPLUNK_USERNAME")
    password: str = os.getenv("SPLUNK_PASSWORD")
    token: str = os.getenv("SPLUNK_TOKEN")

    @classmethod
    def to_dict(cls) -> dict:
        return cls.__dict__


class AppInspectService:
    base_url: str = "https://appinspect.splunk.com/v1"
    auth_url: str = "https://api.splunk.com/2.0/rest/login/splunk"
    report: dict = {}
    tags: str = "private_victoria"

    def __init__(self, cloud_type: str = "victoria"):
        self.account = SplunkCloudAccountConfig.to_dict()
        self.tags = f"private_{cloud_type}"

    def get_token(self) -> str:
        """
        Authenticate to the Splunk Cloud.

        get_token() -> token : str
        """
        try:
            response = requests.get(
                self.auth_url, auth=(self.account["username"], self.account["password"])
            )
            token = response.json()["data"]["token"]
            print("AppInspectService: get_token() - success")
            return token
        except requests.exceptions.RequestException as e:
            print(f"Error getting token: {e}")
            return None

    def _get_request_id(self, headers: dict, files: dict) -> str:
        """
        Helper function to make a validation request and return the request ID.

        _get_request_id(headers, files) -> request_id : str
        """
        url = f"{self.base_url}/app/validate"

        try:
            response = requests.post(url, headers=headers, files=files, timeout=120)
            response_json = response.json()
            request_id = response_json["request_id"]
        except requests.exceptions.RequestException as e:
            print(f"Error making app validation request: {e}")
            return None
        return request_id

    def validate(self, app: str) -> bool:
        """
        Validate the app for the Splunk Cloud.

        validate(app) -> is_valid: bool
        """
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}

        print(f"Validating app {app}...")
        with open(f"{app}.tgz", "rb") as file:
            request_id = self._get_request_id(headers, {"app_package": file})
            status_url = f"{self.base_url}/app/validate/status/{request_id}?included_tags={self.tags}"

            try:
                response = requests.get(status_url, headers=headers)
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}")
                return None, None

            max_retries = 60  # Maximum number of retries
            retries = 0
            response_json = response.json()

            while response_json["status"] != "SUCCESS" and retries < max_retries:
                response = requests.get(status_url, headers=headers)
                response_json = response.json()
                retries += 1
                if response_json["status"] == "FAILURE":
                    print(f"App {app} failed validation: {response_json['errors']}")
                    break
                else:
                    print(f"App {app} awaiting validation...")
                    print(f"Current status: {response_json['status']}")
                    if response_json["status"] == "SUCCESS":
                        break
                    time.sleep(10)
            if retries == max_retries:
                print(f"App {app} validation timed out.")
                return

            if response_json["status"] == "SUCCESS":
                print("App validation successful.")

            response = requests.get(
                f"{self.base_url}/app/report/{request_id}?included_tags=private_victoria",
                headers=headers,
            )
            self.report = response.json()
            summary = self.report["summary"]

            return (
                summary["error"] == 0
                and summary["failure"] == 0
                and summary["manual_check"] == 0
            )


class SplunkbaseService:
    base_url: str = "https://splunkbase.splunk.com/api/v1/app"
    auth_url: str = "https://splunkbase.splunk.com/api/account:login"
    token: str = None

    def __init__(self):
        self.account = SplunkCloudAccountConfig.to_dict()

    def get_app_info(self, app_name: str) -> dict:
        params = {"query": app_name, "limit": 1}
        response = requests.get(self.base_url, params=params)
        if len(response.json().get("results")) > 0:
            return response.json().get("results")[0]
        else:
            print(f"App {app_name} not found on Splunkbase.")
            return None

    def _authenticate(self) -> None:
        """
        Authenticate to Splunkbase.

        _authenticate() -> token : str
        """
        data = {
            "username": self.account["username"],
            "password": self.account["password"],
        }

        response = requests.post(self.auth_url, data=data)
        if response.ok:
            # Parse the XML response
            xml_root = ET.fromstring(response.text)
            # Extract the token from the <id> tag
            namespace = {"atom": "http://www.w3.org/2005/Atom"}  # Define the namespace
            splunkbase_token = xml_root.find(
                "atom:id", namespace
            ).text  # Find the <id> tag with the namespace
            self.token = splunkbase_token
        else:
            print("Splunkbase login failed!")
            print(f"Status code: {response.status_code}")
            print(response.text)

    def get_token(self):
        if not self.token:
            self._authenticate()
        return self.token


class SplunkCloudConnector:
    """Class for connecting to Splunk Cloud and Splunkbase."""

    def __init__(self, splunk_host: str = None, cloud_type: str = "victoria"):
        self.config = SplunkCloudAccountConfig.to_dict()
        self.appinspect = AppInspectService()
        self.splunkbase = SplunkbaseService()
        self.host = splunk_host
        if cloud_type == "classic":
            cloud_type = ""
        self.cloud_type = f"/{cloud_type}"

    def get_appinspect_handler(self):
        return self.appinspect

    def distribute(self, app: str) -> tuple:
        """
        Distribute a private app to the target URL.

        distribute(app) -> was_successful : bool, status_code: int
        """
        url = f"{self.host}/adminconfig/v2/apps{self.cloud_type}"
        print(f"Distributing {app} to {url}")
        headers = {
            "X-Splunk-Authorization": self.appinspect.get_token(),
            "Authorization": f"Bearer {self.config.get('token')}",
            "ACS-Legal-Ack": "Y",
        }
        try:
            with open(f"{app}.tgz", "rb") as file:
                response = requests.post(url, headers=headers, data=file)
            print(f"Distributed {app} to {url} with response: {response.status_code}")
        except Exception as e:
            print(f"Error distributing {app} to {url}: {e}")
            return False, 500

        return response.status_code == 200, response.status_code

    def install(self, app: str, version: str) -> str:
        """
        Install a Splunkbase app.

        install(app, version) -> status : str
        """
        token = self.splunkbase.get_token()
        url = f"{self.host}/adminconfig/v2/apps{self.cloud_type}?splunkbase=true"
        app_info = self.splunkbase.get_app_info(app)
        headers = {
            "X-Splunkbase-Authorization": token,
            "ACS-Licensing-Ack": app_info.get("license_url"),
            "Authorization": f"Bearer {self.config.get('token')}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"splunkbaseID": app_info.get("uid"), "version": version}

        response = requests.post(url, headers=headers, data=data)
        # Handle the case where the app is already installed
        if response.status_code == 409:
            print(f"App {app} is already installed.")
            app_name = app_info.get("appid")
            print(f"Updating app {app} ({app_name}) to version {version}...")
            # Update the app
            url = f"{self.host}/{app_name}"
            data = {"version": version}
            response = requests.patch(url, headers=headers, data=data)
            return "success - existing app updated"

        if response.ok:
            request_status = response.json()["status"]
            print(f"Request status: {request_status}")
            if request_status in ("installed", "processing"):
                print(f"App {app} version {version} installation successful.")
                return "success"
            else:
                print(f"App {app} version {version} installation failed.")
                return f"failed with status: {request_status} - {response.text}"

        print("Request failed!")
        print(f"Status code: {response.status_code}")
        print(response.text)
        return f"failed with status code: {response.status_code} - {response.text}"
