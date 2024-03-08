from datetime import datetime
import os
import re

from web import web_src
from slack_mod import share_file
from img_vertexai import img_text
from gcs_client import upload

from slack_bolt import App, Ack
from slack_bolt.adapter.socket_mode import SocketModeHandler


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
    query = str(re.sub("<@.*>", "", event['text']))
    files = event.get('files', [])

    thread_id = event['ts']
    if "thread_ts" in event:
        thread_id = event['thread_ts']

    say('処理中', thread_ts=thread_id)
    if not files:
        answer = web_src.run_query(query, filter_words=[])
        say(str(answer['result']), thread_ts=thread_id)
    else:
        early_response = count_files_msg(files=files)
        say(early_response, thread_ts=thread_id)

        bucket_name = os.environ.get("BUCKET_NAME", "")
        upload_files = []
        for file in files:
            mime_type = file.get('mimetype', None)
            if mime_type == "image/png":
                bucket_name = os.environ.get("BUCKET_NAME", "")
                download_file = file.get('url_private_download', None)
                image = share_file.download_from_slack(download_file, SLACK_BOT_TOKEN)

                original_file_name = file.get('name', "")
                user_name = event.get('user', "")
                original_file_name_part = original_file_name.replace(".png", "")
                upload_file_name = f"{original_file_name_part}_{user_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"

                gcs_uri = upload.gcs_upload_client(
                    bucket_name=bucket_name,
                    image=image,
                    filename=upload_file_name
                )

                upload_files.append(
                    {
                        'gcs_uri': gcs_uri,
                        'filename': original_file_name
                    }
                )

        thread_id = event['ts']
        for upload_file in upload_files:
            if "thread_ts" in event:
                thread_id = event['thread_ts']
            print(upload_file['gcs_uri'])
            result = img_text.img_to_text(
                query,
                upload_file['gcs_uri'],
                upload_file['filename']
            )
            say(result, thread_ts=thread_id)

    say('おわり', thread_ts=thread_id)


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
