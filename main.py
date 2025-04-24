from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import os
import random

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {}
user_records = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

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

def calculate_win_rate(cards):
    total = len(cards)
    banker = cards.count('莊')
    player = cards.count('閒')
    draw = cards.count('和')
    return {
        'banker': banker,
        'player': player,
        'draw': draw,
        'banker_rate': round(banker / total * 100, 1) if total else 0,
        'player_rate': round(player / total * 100, 1) if total else 0,
        'draw_rate': round(draw / total * 100, 1) if total else 0
    }

def calculate_hit_rate(cards):
    total = len(cards)
    correct = 0
    for i in range(1, len(cards)):
        if cards[i] != cards[i - 1] and cards[i] in '莊閒':
            correct += 1
    hit_rate = round(correct / (total - 1) * 100, 1) if total > 1 else 0
    return hit_rate

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    raw_input = event.message.text.strip()

    if raw_input == "接續":
        cards = user_memory.get(user_id, '')
    elif all(c in '莊閒和' for c in raw_input):
        cards = user_memory.get(user_id, '') + clean_input(raw_input)
        user_memory[user_id] = cards
    elif raw_input in ["下課", "結束", "結束分析"]:
        user_memory[user_id] = ''
        user_records[user_id] = []
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已結束分析，歡迎再次使用！"))
        return
    elif raw_input == "顯示紀錄":
        records = user_records.get(user_id, [])
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
    else:
        cards = ''

    if not cards:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒"))
        return

    cards = cards[-30:]
    suggestion = predict_next_bet(cards)
    confidence = calculate_confidence(cards, suggestion)
    stats = calculate_win_rate(cards)
    hit_rate = calculate_hit_rate(cards)

    suggestion_color = "#FF4444" if suggestion == "莊" else "#0000FF" if suggestion == "閒" else "#00C300"

    user_records.setdefault(user_id, []).append({
        'suggestion': suggestion,
        'hit': suggestion == cards[-1]
    })
    user_records[user_id] = user_records[user_id][-5:]

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "xl"},
                {"type": "separator", "margin": "md"},
                {"type": "box", "layout": "vertical", "spacing": "sm", "margin": "md", "contents": [
                    {"type": "text", "text": f"🏦 莊：{stats['banker_rate']}%", "size": "sm"},
                    {"type": "text", "text": f"🧑‍💼 閒：{stats['player_rate']}%", "size": "sm"},
                    {"type": "text", "text": f"🤝 和：{stats['draw_rate']}%", "size": "sm"},
                    {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "size": "sm"}
                ]},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"🔮 推薦下注：{suggestion}（信心 {confidence}%）", "weight": "bold", "color": suggestion_color, "size": "md", "margin": "md"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#FF4444", "action": {"type": "message", "label": "莊", "text": "莊"}},
                {"type": "button", "style": "primary", "color": "#0000FF", "action": {"type": "message", "label": "閒", "text": "閒"}},
                {"type": "button", "style": "primary", "color": "#00C300", "action": {"type": "message", "label": "和", "text": "和"}}
            ]
        }
    }

    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="百家樂分析結果", contents=bubble))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
