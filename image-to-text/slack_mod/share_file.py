import requests


def download_from_slack(download_url: str, auth: str):
    """Slackから画像をダウンロードする

    Args:
        download_url (str): 画像のURL
        auth (str): 画像の閲覧に必要なSlackの認証キー

    Returns:
        binary:
    """
    if download_url is None:
        return None

    img_data = requests.get(
        download_url,
        allow_redirects=True,
        headers={"Authorization": f"Bearer {auth}"},
        stream=True,
    ).content

    if len(img_data) > 0:
        return img_data
    else:
        return 0
