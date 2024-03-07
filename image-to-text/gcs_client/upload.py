# GCSにファイルを保存するのでGCSのClientを利用
from google.cloud import storage


def gcs_upload_client(bucket_name, image, filename):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(image, content_type="image/png")

    return f"gs://{bucket_name}/{filename}"
