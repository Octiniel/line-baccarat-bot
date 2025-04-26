import random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

# 使用者記憶體
user_memory = {
    'records': {},
    'cards': {},
    'results': {},
    'profit': {},
    'last_suggestion': {}
}

def clean_input(text):
    return ''.join(c for c in '莊閒和')

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last = cards[-1]
    return '莊' if last == '閒' else '閒'

def generate_flex_suggestion(suggestion, win_rate, banker_rate, player_rate, tie_rate):
    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🎯 百家樂分析", "weight": "bold", "size": "lg"},
                {"type": "text", "text": f"莊:{banker_rate:.1f}% 閒:{player_rate:.1f}% 和:{tie_rate:.1f}%", "size": "sm"},
                {"type": "text", "text": f"命中率:{win_rate:.1f}%", "size": "sm"},
                {"type": "text", "text": f"建議下注：{suggestion}", "weight": "bold", "size": "xl", "color": "#0000FF", "margin": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "md",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "莊", "text": "莊"}, "style": "primary"},
                        {"type": "button", "action": {"type": "message", "label": "閒", "text": "閒"}, "style": "primary"},
                        {"type": "button", "action": {"type": "message", "label": "和", "text": "和"}, "style": "primary"}
                    ]
                }
            ]
        }
    }

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    # 初始化資料
    for key in user_memory:
        if user_id not in user_memory[key]:
            user_memory[key][user_id] = [] if key != 'profit' else 0

    # ✅ 下課指令
    if text == "下課":
        for key in user_memory:
            user_memory[key].pop(user_id, None)

        flex_message = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ 已下課", "weight": "bold", "size": "xl", "align": "center"},
                    {"type": "text", "text": "所有紀錄已清除", "size": "md", "align": "center", "margin": "md"},
                    {"type": "text", "text": "感謝使用 🙏", "size": "sm", "align": "center", "margin": "md"}
                ]
            }
        }

        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="✅ 已下課", contents=flex_message)
        )
        return

    # 🧹 清除紀錄指令
    if text == "清除紀錄":
        user_memory['cards'][user_id] = []
        user_memory['results'][user_id] = []
        user_memory['records'][user_id] = []
        user_memory['last_suggestion'][user_id] = None
        user_memory['profit'][user_id] = 0

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🧹 已清除紀錄，可以重新開始輸入牌路囉！")
        )
        return

    # 📋 顯示紀錄指令
    if text == "顯示紀錄":
        results = user_memory['results'][user_id]
        wins = results.count("贏")
        losses = results.count("輸")
        total = wins + losses
        win_rate = (wins / total) * 100 if total > 0 else 0
        profit = user_memory['profit'][user_id]

        reply = f"📊 紀錄統計：\n✅ 勝場：{wins}，❌ 敗場：{losses}\n🎯 命中率：{win_rate:.1f}%\n💰 累積損益：{profit} 元"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 🃏 正常輸入牌路
    clean_cards = clean_input(text)
    if clean_cards:
        cards = user_memory['cards'][user_id]
        for c in clean_cards:
            cards.append(c)

            suggestion = predict_next_bet(cards)
            user_memory['last_suggestion'][user_id] = suggestion

            # 第一局不計算
            if len(cards) <= 1:
                continue

            if c == '和':
                continue  # 和局不影響勝負
            elif c == suggestion:
                user_memory['results'][user_id].append("贏")
                user_memory['profit'][user_id] += 100
            else:
                user_memory['results'][user_id].append("輸")
                user_memory['profit'][user_id] -= 100

        # 更新 Flex 顯示
        count_b = cards.count('莊')
        count_p = cards.count('閒')
        count_t = cards.count('和')
        total = max(1, count_b + count_p + count_t)
        banker_rate = count_b / total * 100
        player_rate = count_p / total * 100
        tie_rate = count_t / total * 100
        win_count = user_memory['results'][user_id].count("贏")
        lose_count = user_memory['results'][user_id].count("輸")
        win_rate = (win_count / (win_count + lose_count)) * 100 if (win_count + lose_count) else 0

        flex = generate_flex_suggestion(suggestion, win_rate, banker_rate, player_rate, tie_rate)
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="下注建議", contents=flex)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ 請輸入正確的牌路，例如：莊閒莊和")
        )

# 🏠 預設首頁，防止 404
@app.route("/", methods=['GET'])
def home():
    return "✅ LINE百家樂機器人運作中"

# 📩 Line Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400

    return 'OK'

if __name__ == "__main__":
    app.run()
