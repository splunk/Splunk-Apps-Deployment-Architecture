import boto3


class AwsS3Connector:
    """Class to connect to AWS S3 and download files."""

    def __init__(self, aws_access_key_id, aws_secret_access_key):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    def download_file_from_s3(
        self, bucket_name: str, object_name: str, file_name: str
    ) -> None:
        """Download a file from an S3 bucket."""
        s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )
        try:
            s3.download_file(bucket_name, object_name, file_name)
            print(f"Downloaded {object_name} from {bucket_name} to {file_name}")
        except Exception as e:
            print(f"Error downloading {object_name} from {bucket_name}: {e}")
