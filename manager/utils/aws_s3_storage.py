import boto3
import mimetypes
from django.conf import settings


def upload_to_s3(file, folder):
    """
    Upload a file to S3 in a specified folder.

    Args:
        file: The file object to upload.
        folder: The folder in the S3 bucket where the file should be stored.

    Returns:
        str: The public URL of the uploaded file.
    """
    file_key = f"{folder}/{file}"

    content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_STORAGE_REGION
    )
    bucket_name = settings.AWS_STORAGE_BUCKET

    try:
        s3_client.upload_fileobj(file,
                                 bucket_name,
                                 file_key,
                                 ExtraArgs={'ACL': 'public-read',
                                            'ContentType': content_type
                                            }
                                 )
        file_url = f"https://{bucket_name}.s3.{settings.AWS_STORAGE_REGION}.amazonaws.com/{file_key}"
        return file_url
    except Exception as e:
        raise Exception(f"Failed to upload file to STORAGE: {e}")


def get_s3_base_url(file_name: str):
    """
    Returns the base STORAGE URL for the configured bucket and region.
    """
    return f"https://{settings.AWS_STORAGE_BUCKET}.s3.{settings.AWS_STORAGE_REGION}.amazonaws.com/{file_name}"
