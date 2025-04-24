from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
)
import os
import random

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {}  # ✅ 使用者牌路記憶區

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
    if len(cards) < 6:
        return random.choice(['莊', '閒'])
    last_five = cards[-5:]
    if last_five.count('莊') >= 4:
        return '閒'
    elif last_five.count('閒') >= 4:
        return '莊'
    else:
        return random.choice(['莊', '閒'])

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

def detect_streak(cards):
    if len(cards) < 2:
        return ""
    streak_type = cards[0]
    streak_len = 1
    max_streak = 1
    max_type = cards[0]
    for i in range(1, len(cards)):
        if cards[i] == cards[i - 1]:
            streak_len += 1
            if streak_len > max_streak:
                max_streak = streak_len
                max_type = cards[i]
        else:
            streak_len = 1
    if max_streak >= 3:
        return f"⚠️ 偵測到『{max_type}』連續 {max_streak} 次，請注意走勢變化"
    return ""

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
    elif raw_input == "重新分析":
        cards = user_memory.get(user_id, '')
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
        stats = calculate_win_rate(cards)
        streak_note = detect_streak(cards)
        hit_rate = calculate_hit_rate(cards)

        summary = (
            f"分析結果：\n"
            f"莊:{stats['banker_rate']}%\n"
            f"閒:{stats['player_rate']}%\n"
            f"和:{stats['draw_rate']}%\n\n"
            f"推薦：{suggestion}"
        )
        if streak_note:
            summary += f"\n{streak_note}"

        reply = TextSendMessage(
            text=summary,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="莊", text="莊")),
                QuickReplyButton(action=MessageAction(label="閒", text="閒")),
                QuickReplyButton(action=MessageAction(label="重新分析", text="重新分析")),
                QuickReplyButton(action=MessageAction(label="結束分析", text="結束分析"))
            ])
        )

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
