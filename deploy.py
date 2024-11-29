import sys
import yaml

def read_yaml(file_path):
    """Read and return the contents of a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

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
    # 2. If config key is set in deployment.yml for each app, open tgz, merge configuration, repackage
    # 3. Distribute via ACS API to target url from deployment.yml

if __name__ == "__main__":
    main()