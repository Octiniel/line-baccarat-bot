
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, QuickReply, QuickReplyButton, MessageAction
)
import os
import random

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {}
if 'records' not in user_memory:
    user_memory['records'] = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK', 200

def clean_input(text):
    return ''.join(c for c in text if c in '莊閒和')

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last3 = cards[-3:]
    if all(c == last3[0] for c in last3):
        return last3[0]
    return '閒' if cards[-1] == '莊' else '莊'

def calculate_confidence(cards, suggestion):
    score = 50
    recent = cards[-5:]
    if recent.count(suggestion) == 0:
        score += 20
    elif recent.count(suggestion) == 1:
        score += 10
    elif recent.count(suggestion) >= 4:
        score -= 20
    if len(set(recent)) == 1:
        score += 15
    return min(100, max(30, score))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    raw_input = event.message.text.strip()

    if raw_input in ["下課", "結束", "結束分析"]:
        user_memory[user_id] = ''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已結束分析，歡迎再次使用！"))
        return

    if raw_input == "清除紀錄":
        user_memory['records'][user_id] = []
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已清除下注紀錄"))
        return

    if raw_input == "顯示紀錄":
        records = user_memory['records'].get(user_id, [])
        if not records:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="尚無紀錄可顯示"))
            return

        suggested = " → ".join([r['suggestion'] for r in records])
        results = " → ".join(["✅" if r['hit'] else "❌" for r in records])
        profits = " → ".join([f"{'+100' if r['hit'] else '-100'}" for r in records])
        total_profit = sum([100 if r['hit'] else -100 for r in records])
        hit_rate = round(100 * sum(1 for r in records if r['hit']) / len(records), 1)

        flex_msg = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "🎲 最近紀錄", "weight": "bold", "size": "lg"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"建議：{suggested}", "size": "sm"},
                    {"type": "text", "text": f"結果：{results}", "size": "sm"},
                    {"type": "text", "text": f"獲利：{profits}", "size": "sm"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"💰 總損益：{total_profit}", "weight": "bold", "color": "#00C851"},
                    {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "weight": "bold"}
                ]
            }
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="下注紀錄", contents=flex_msg))
        return

    if all(c in '莊閒和' for c in raw_input):
        cards = user_memory.get(user_id, '') + clean_input(raw_input)
        user_memory[user_id] = cards
    else:
        cards = ''

    if not cards:
        reply = TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒")
    else:
        suggestion = predict_next_bet(cards)
        confidence = calculate_confidence(cards, suggestion)

        user_memory['records'].setdefault(user_id, []).append({
            'suggestion': suggestion,
            'hit': suggestion == cards[-1]
        })
        user_memory['records'][user_id] = user_memory['records'][user_id][-5:]

        reply = TextSendMessage(text=f"🔮 推薦下注：{suggestion}（信心 {confidence}%）")

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
