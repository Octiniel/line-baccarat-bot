
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
import os
import random

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {}
user_memory['records'] = {}
user_memory['last_suggestion'] = {}

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

def calculate_hit_rate(cards):
    total = len(cards)
    correct = 0
    for i in range(1, total):
        if cards[i] != cards[i - 1] and cards[i] in '莊閒':
            correct += 1
    return round(correct / (total - 1) * 100, 1) if total > 1 else 0

def generate_analysis_flex(cards, suggestion, confidence, hit_rate):
    count_z = cards.count('莊')
    count_x = cards.count('閒')
    count_h = cards.count('和')
    total = len(cards)
    percent = lambda c: round(c / total * 100, 1) if total > 0 else 0
    color_map = {"莊": "#FF4444", "閒": "#0000FF", "和": "#00C300"}
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "lg"},
                {"type": "separator"},
                {"type": "text", "text": f"莊：{percent(count_z)}%", "size": "sm"},
                {"type": "text", "text": f"閒：{percent(count_x)}%", "size": "sm"},
                {"type": "text", "text": f"和：{percent(count_h)}%", "size": "sm"},
                {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "size": "sm"},
                {"type": "separator"},
                {"type": "text", "text": f"推薦下注：{suggestion}（信心 {confidence}%）", "weight": "bold", "color": color_map[suggestion], "size": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "莊", "text": "莊"}, "color": "#FF4444", "style": "primary"},
                        {"type": "button", "action": {"type": "message", "label": "閒", "text": "閒"}, "color": "#0000FF", "style": "primary"},
                        {"type": "button", "action": {"type": "message", "label": "和", "text": "和"}, "color": "#00C300", "style": "primary"}
                    ]
                }
            ]
        }
    }

def generate_record_flex(records):
    suggested = " → ".join([r['suggestion'] for r in records])
    results = " → ".join(["✅" if r['hit'] else "❌" for r in records])
    profits = " → ".join([f"{'+100' if r['hit'] else '-100'}" for r in records])
    total_profit = sum([100 if r['hit'] else -100 for r in records])
    hit_rate = round(100 * sum(1 for r in records if r['hit']) / len(records), 1) if records else 0
    return {
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

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    raw_input = event.message.text.strip()

    if raw_input in ["下課", "結束分析"]:
        user_memory[user_id] = ''
        user_memory['records'][user_id] = []
        user_memory['last_suggestion'][user_id] = ''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已結束分析，歡迎再次使用！"))
        return

    if raw_input == "清除紀錄":
        user_memory['records'][user_id] = []
        user_memory['last_suggestion'][user_id] = ''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已清除下注紀錄"))
        return

    if all(c in '莊閒和' for c in raw_input):
        cards = user_memory.get(user_id, '') + clean_input(raw_input)
        user_memory[user_id] = cards

        last = user_memory['last_suggestion'].get(user_id)
        if last and user_memory['records'].get(user_id) is not None and len(user_memory['records'][user_id]) > 0:
            user_memory['records'].setdefault(user_id, []).append({
                'suggestion': last,
                'hit': last == raw_input
            })
        elif last:
            user_memory['records'].setdefault(user_id, [])

        suggestion = predict_next_bet(cards)
        confidence = calculate_confidence(cards, suggestion)
        hit_rate = calculate_hit_rate(cards)
        user_memory['last_suggestion'][user_id] = suggestion

        analysis_flex = generate_analysis_flex(cards, suggestion, confidence, hit_rate)
        record_flex = generate_record_flex(user_memory['records'][user_id])
        line_bot_api.reply_message(event.reply_token, [
            FlexSendMessage(alt_text="百家樂分析結果", contents=analysis_flex),
            FlexSendMessage(alt_text="下注紀錄", contents=record_flex)
        ])

        last_record = user_memory['records'][user_id][-1] if user_memory['records'][user_id] else None
        if last_record:
            last_result = raw_input
            hit = last_record['hit']
            total_profit = sum([100 if r['hit'] else -100 for r in user_memory['records'][user_id]])
            if hit:
                result_text = f"好耶！這局開「{last_result}」✅ 命中！"
            else:
                result_text = f"這局開「{last_result}」❌ 沒中～"
            profit_text = f"累積獲利：{total_profit:+} 元"
            line_bot_api.push_message(user_id, [
                TextSendMessage(text=result_text),
                TextSendMessage(text=profit_text)
            ])
        return

    reply = TextSendMessage(text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒")
    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
