import boto3
from botocore.config import Config
from flask import current_app

def get_s3_client():
    region = current_app.config.get('AWS_REGION')
    return boto3.client(
        's3',
        aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
        region_name=region,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'})
    )

def generate_presigned_url(object_name, expiration=3600):
    s3_client = get_s3_client()
    try:
        response = s3_client.generate_presigned_post(
            Bucket=current_app.config.get('S3_BUCKET_NAME'),
            Key=object_name,
            Fields={"acl": "public-read"},
            Conditions=[
                {"acl": "public-read"},
                ["starts-with", "$Content-Type", "image/"]
            ],
            ExpiresIn=expiration
        )
    except Exception as e:
        print(e)
        return None
    return response