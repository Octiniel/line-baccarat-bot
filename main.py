from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from baccarat_logic import get_prediction
import os

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()
    if "牌路：" in user_input:
        cards = user_input.replace("牌路：", "").strip()
        prediction = get_prediction(cards)
        reply = TextSendMessage(text=prediction)
    else:
        reply = TextSendMessage(text="請輸入格式：牌路：莊閒莊閒閒")
    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    app.run()
