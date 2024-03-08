import os
import re
from web import web_src

from slack_bolt import App, Ack
from slack_bolt.adapter.socket_mode import SocketModeHandler

APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
PORT = os.environ.get("PORT", 8080)
app = App(token=SLACK_BOT_TOKEN)


def handle_mention(event, say):
    query = str(re.sub("<@.*>", "", event['text']))
    thread_id = event['ts']
    if "thread_ts" in event:
        thread_id = event['thread_ts']

    say('処理中', thread_ts=thread_id)

    answer = web_src.run_query(query, filter_words=[])
    say(str(answer['result']), thread_ts=thread_id)
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
