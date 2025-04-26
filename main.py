import random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

# 使用者記憶資料
user_memory = {
    'records': {},          # 每局記錄
    'last_suggestion': {},  # 上次建議
    'cards': {},            # 牌路
    'settings': {},         # 個人設定
    'results': {},          # 勝負紀錄
    'profit': {}            # 累積獲利
}

def clean_input(text):
    return ''.join(c for c in '莊閒和')

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last_three = cards[-3:]
    if last_three == ['莊', '閒', '莊']:
        return '閒'
    if last_three.count('莊') > last_three.count('閒'):
        return '閒'
    else:
        return '莊'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    # 初始化使用者資料
    if user_id not in user_memory['records']:
        user_memory['records'][user_id] = []
    if user_id not in user_memory['last_suggestion']:
        user_memory['last_suggestion'][user_id] = None
    if user_id not in user_memory['cards']:
        user_memory['cards'][user_id] = []
    if user_id not in user_memory['settings']:
        user_memory['settings'][user_id] = {}
    if user_id not in user_memory['results']:
        user_memory['results'][user_id] = []
    if user_id not in user_memory['profit']:
        user_memory['profit'][user_id] = 0

    # 🔵 下課指令
    if text == "下課":
        user_memory['records'].pop(user_id, None)
        user_memory['last_suggestion'].pop(user_id, None)
        user_memory['cards'].pop(user_id, None)
        user_memory['settings'].pop(user_id, None)
        user_memory['results'].pop(user_id, None)
        user_memory['profit'].pop(user_id, None)

        flex_message = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ 已下課", "weight": "bold", "size": "xl", "align": "center"},
                    {"type": "text", "text": "所有紀錄已清除！", "size": "md", "align": "center", "margin": "md"},
                    {"type": "text", "text": "感謝使用 🙏", "size": "sm", "align": "center", "margin": "md"}
                ]
            }
        }

        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="✅ 已下課", contents=flex_message)
        )
        return

    # 🔵 清除紀錄
    if text == "清除紀錄":
        user_memory['records'][user_id] = []
        user_memory['cards'][user_id] = []
        user_memory['last_suggestion'][user_id] = None
        user_memory['results'][user_id] = []
        user_memory['profit'][user_id] = 0

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🧹 已清除紀錄！可以重新開始輸入牌路～")
        )
        return

    # 🔵 顯示紀錄
    if text == "顯示紀錄":
        results = user_memory['results'][user_id]
        if not results:
            reply_text = "📋 目前沒有任何紀錄喔！"
        else:
            wins = results.count('贏')
            losses = results.count('輸')
            total = wins + losses
            win_rate = (wins / total) * 100 if total > 0 else 0
            profit = user_memory['profit'][user_id]

            reply_text = f"📋 歷史紀錄\n"
            reply_text += f"✅ 勝場：{wins}｜❌ 敗場：{losses}\n"
            reply_text += f"📈 命中率：{win_rate:.1f}%\n"
            reply_text += f"💰 累積獲利：{profit} 元"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return

    # 🔵 正常處理牌路輸入
    cards = user_memory['cards'][user_id]
    clean_cards = clean_input(text)

    if clean_cards:
        for c in clean_cards:
            cards.append(c)

        suggestion = predict_next_bet(cards)
        user_memory['last_suggestion'][user_id] = suggestion

        reply_text = f"🎲 建議下一把：{suggestion}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )

        # 自動紀錄
        for c in clean_cards:
            if c == suggestion:
                user_memory['results'][user_id].append('贏')
                user_memory['profit'][user_id] += 100
            elif c == '和':
                # 和局不計勝負，不影響 profit
                continue
            else:
                user_memory['results'][user_id].append('輸')
                user_memory['profit'][user_id] -= 100

        # 每局紀錄
        user_memory['records'][user_id].append(f"輸入：{text} ➡ 建議：{suggestion}")
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ 請輸入正確的牌路，例如：莊閒莊和")
        )

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature. Please check your channel access token/channel secret.', 400
    return 'OK'

if __name__ == "__main__":
    app.run()
