import boto3
import mimetypes
from django.conf import settings


def upload_to_s3(file, folder):
    """
    Uploads a file to an S3 bucket.

    This function uploads the provided file to a specified folder in an AWS S3 bucket. It sets the appropriate
    content type based on the file extension and grants public read access to the uploaded file.

    :param file: The file object to be uploaded. It should be a file-like object (e.g., a Django File).
    :param folder: The folder (or directory) within the S3 bucket where the file will be stored.

    :return: The URL of the uploaded file in the S3 bucket.

    :raises Exception: If there is an error during the file upload process, an exception is raised with a message.
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

    :param file_name: The name of the file stored in the S3 bucket.

    :return: A string representing the full URL to access the file in the S3 bucket.
    """
    return f"https://{settings.AWS_STORAGE_BUCKET}.s3.{settings.AWS_STORAGE_REGION}.amazonaws.com/{file_name}"
