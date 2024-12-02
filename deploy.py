import sys
import yaml
import boto3

def read_yaml(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def download_file_from_s3(bucket_name, object_name, file_name):
    """Download a file from an S3 bucket."""
    s3 = boto3.client('s3')
    try:
        s3.download_file(bucket_name, object_name, file_name)
        print(f"Downloaded {object_name} from {bucket_name} to {file_name}")
    except Exception as e:
        print(f"Error downloading {object_name} from {bucket_name}: {e}")
        
def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_yaml_file>")
        sys.exit(1)

    yaml_file_path =  sys.argv[1] + "/deployment.yml"

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

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        print(f"App: {app}, Bucket: {bucket}, Directory: {directory}")

    # Download all apps from S3
    for app, bucket, directory in zip(apps, s3_buckets, app_direcotires):
        object_name = directory
        file_name = f"{app}.tgz"  # Adjust the path as needed
        download_file_from_s3(bucket, object_name, file_name)
    
    # 2. If config key is set in deployment.yml for each app, open tgz, merge configuration, repackage
    configs = [(app, data['apps'][app]['config']) for app in apps if 'config' in data['apps'][app]]
    for app, config in configs:
        print(f"App: {app}, Config: {config}")
    # 3. Distribute via ACS API to target url from deployment.yml
    target_url = data['target']['url']

if __name__ == "__main__":
    main()