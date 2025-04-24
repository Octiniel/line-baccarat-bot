from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent,
    TextComponent, QuickReply, QuickReplyButton, MessageAction
)
import os
import random

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {}

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

def detect_special_patterns(cards):
    if len(cards) < 6:
        return None

    last = cards[-6:]

    if all(c == last[0] for c in last[-4:]):
        return f"🔁 偵測到長龍：{last[-1]} 連續 4 次以上"

    if len(last) >= 6 and all(last[i] != last[i+1] for i in range(5)):
        return "🔃 偵測到單跳路型（交錯重複）"

    if last[-5:] in ['莊閒閒莊閒', '閒莊莊閒莊']:
        return "🏠 偵測到一廳兩房路型"

    return None

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last3 = cards[-3:]
    if all(c == last3[0] for c in last3):
        return last3[0]  # 跟龍邏輯：連續 3 次相同就跟龍
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
    elif raw_input == "結束分析":
        user_memory[user_id] = ''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已結束分析，歡迎再次使用！"))
        return
    else:
        cards = ''

    if not cards:
        reply = TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒")
    else:
        cards = cards[-30:]
        suggestion = predict_next_bet(cards)
        confidence = calculate_confidence(cards, suggestion)
        stats = calculate_win_rate(cards)
        pattern_note = detect_special_patterns(cards)
        hit_rate = calculate_hit_rate(cards)

        suggestion_color = "#FF4444" if suggestion == "莊" else "#0000FF" if suggestion == "閒" else "#00C300"

        contents = [
            {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "lg"},
            {"type": "text", "text": f"莊：{stats['banker_rate']}% 閒：{stats['player_rate']}% 和：{stats['draw_rate']}%"},
            {"type": "text", "text": f"命中率：{hit_rate}%"},
            {"type": "text", "text": f"推薦：{suggestion}（信心 {confidence}%）", "weight": "bold", "color": suggestion_color}
        ]
        if pattern_note:
            contents.append({"type": "text", "text": pattern_note, "wrap": True, "color": "#FF4444"})

        bubble = {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": contents}
        }

        reply = FlexSendMessage(
            alt_text="百家樂分析結果",
            contents=bubble,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="莊", text="莊")),
                QuickReplyButton(action=MessageAction(label="閒", text="閒")),
                QuickReplyButton(action=MessageAction(label="和", text="和")),
                QuickReplyButton(action=MessageAction(label="結束分析", text="結束分析"))
            ])
        )

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
