from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
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
    except InvalidSignatureError:
        return 'Invalid signature', 400

    return 'OK', 200

# ✅ 加強版：簡單分析莊閒數量並增加容錯說明

def clean_input(text):
    return ''.join(c for c in text if c in '莊閒和')

def predict_next_bet(cards):
    banker = cards.count('莊')
    player = cards.count('閒')
    if banker > player:
        return '閒'
    elif player > banker:
        return '莊'
    else:
        return '平手局面，建議觀望'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    raw_input = event.message.text.strip()
    cards = clean_input(raw_input)

    if not cards:
        reply = TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒")
    else:
        suggestion = predict_next_bet(cards)
        reply = TextSendMessage(
            text=(
                f"🔍 你提供的牌路：{cards}\n"
                f"📊 統計 → 莊：{cards.count('莊')}，閒：{cards.count('閒')}，和：{cards.count('和')}\n"
                f"📌 建議下注方向：{suggestion}"
            )
        )

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
