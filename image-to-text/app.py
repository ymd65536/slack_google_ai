from datetime import datetime
import os

from slack_mod import share_file
from img_vertexai import img_text
from gcs_client import upload

from slack_bolt import App, Ack
from slack_bolt.adapter.socket_mode import SocketModeHandler


project_id = os.environ.get("PROJECT_ID", "")
APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
PORT = os.environ.get("PORT", 8080)
app = App(
    token=SLACK_BOT_TOKEN,
    process_before_response=True
)


def _count_files(files):
    return len(files)


def count_files_msg(files):
    file_count = _count_files(files)
    return f"画像を{file_count}枚受信しました"


def handle_mention(event, say):
    files = event.get('files', [])

    if not files:
        thread_id = event['ts']
        say('画像が添付されていません！', thread_ts=thread_id)
    else:
        early_response = count_files_msg(files=files)
        say(early_response, thread_ts=thread_id)

        thread_id = event['ts']

        for file in files:
            mime_type = file.get('mimetype', None)
            download_file = file.get('url_private_download', None)
            upload_file_name = file.get('name', None)

            image = share_file.download_from_slack(download_file, SLACK_BOT_TOKEN)

            if "thread_ts" in event:
                thread_id = event['thread_ts']

            if image is None or not mime_type == "image/png":
                say(f"画像リンクから画像が読み取れませんでした。{upload_file_name}", thread_ts=thread_id)
            else:
                bucket_name = os.environ.get("BUCKET_NAME", "")
                filename = f"slack_{upload_file_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"

                gcs_file_name = upload.gcs_upload_client(
                    bucket_name=bucket_name,
                    image=image,
                    filename=filename
                )

                res = img_text.img_to_text(gcs_file_name, filename, project_id)
                say(res, thread_ts=thread_id)

    say("チェック終了！", thread_ts=thread_id)


def slack_ack(ack: Ack):
    ack()


app.event("app_mention")(ack=slack_ack, lazy=[handle_mention])


# アプリを起動します
if __name__ == "__main__":
    if APP_ENVIRONMENT == "prod":
        app.start(port=int(PORT))
    else:
        print("SocketModeHandler")
        SocketModeHandler(app, SLACK_APP_TOKEN).start()
