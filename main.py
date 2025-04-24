from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
import os

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
    banker = cards.count('莊')
    player = cards.count('閒')
    if banker > player:
        return '閒'
    elif player > banker:
        return '莊'
    else:
        return '平手局面，建議觀望'

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

def calculate_profit(cards, unit=100):
    profit = 0
    for outcome in cards:
        if outcome == '莊':
            profit += int(unit * 0.95)
        elif outcome == '閒':
            profit += unit
        elif outcome == '和':
            profit += 0
    return profit

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

    # ✅ 支援「接續」指令與逐字輸入牌路追加
    if raw_input == "接續":
        cards = user_memory.get(user_id, '')
    elif all(c in '莊閒和' for c in raw_input):
        cards = user_memory.get(user_id, '') + clean_input(raw_input)
        user_memory[user_id] = cards
    else:
        cards = ''

    if not cards:
        reply = TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒")
    else:
        cards = cards[-30:]  # ✅ 限制分析最近 30 局
        suggestion = predict_next_bet(cards)
        stats = calculate_win_rate(cards)
        profit = calculate_profit(cards)
        streak_note = detect_streak(cards)
        hit_rate = calculate_hit_rate(cards)

        contents = [
            {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "lg"},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": f"牌路：{cards}", "margin": "md"},
            {"type": "text", "text": f"莊：{stats['banker']} 次（{stats['banker_rate']}%）", "margin": "sm"},
            {"type": "text", "text": f"閒：{stats['player']} 次（{stats['player_rate']}%）"},
            {"type": "text", "text": f"和：{stats['draw']} 次（{stats['draw_rate']}%）"},
            {"type": "text", "text": f"🎯 命中率：{hit_rate}%"},
            {"type": "text", "text": f"💰 累積獲利：{profit} 元", "margin": "md"},
            {"type": "text", "text": f"✅ 建議下注：{suggestion}", "weight": "bold", "color": "#1DB446", "margin": "md"},
        ]
        if streak_note:
            contents.append({"type": "text", "text": streak_note, "wrap": True, "color": "#FF5555", "margin": "md"})

        flex_message = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#1DB446",
                        "action": {"type": "message", "label": "重新報牌", "text": "重新報牌"}
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {"type": "message", "label": "顯示統計", "text": "統計"}
                    }
                ]
            }
        }
        reply = FlexSendMessage(alt_text="百家樂分析建議", contents=flex_message)

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
