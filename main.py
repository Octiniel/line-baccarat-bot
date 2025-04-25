from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os, random

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

user_memory = {'records': {}, 'last_suggestion': {}, 'cards': {}, 'settings': {}}

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
    if recent.count(suggestion) == 0: score += 20
    elif recent.count(suggestion) == 1: score += 10
    elif recent.count(suggestion) >= 4: score -= 20
    if len(set(recent)) == 1: score += 15
    return min(100, max(30, score))

def calculate_hit_rate(cards):
    if len(cards) <= 1: return 0
    return round(100 * sum(1 for i in range(1, len(cards)) if cards[i] != cards[i-1]) / (len(cards)-1), 1)

def generate_analysis_flex(cards, suggestion, confidence, hit_rate, logic_mode):
    count_z, count_x, count_h = cards.count('莊'), cards.count('閒'), cards.count('和')
    total = len(cards)
    percent = lambda c: round(c / total * 100, 1) if total else 0
    color_map = {"莊": "#FF4444", "閒": "#0000FF", "和": "#00C300"}
    return {
        "type": "bubble",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md", "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "lg"},
                {"type": "separator"},
                {"type": "text", "text": f"莊：{percent(count_z)}%", "size": "sm"},
                {"type": "text", "text": f"閒：{percent(count_x)}%", "size": "sm"},
                {"type": "text", "text": f"和：{percent(count_h)}%", "size": "sm"},
                {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "size": "sm"},
                {"type": "separator"},
                {"type": "text", "text": f"推薦下注：{suggestion}（{logic_mode}，信心 {confidence}%）", "weight": "bold", "color": color_map[suggestion]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "button", "action": {"type": "message", "label": "莊", "text": "莊"}, "color": "#FF4444", "style": "primary"},
                    {"type": "button", "action": {"type": "message", "label": "閒", "text": "閒"}, "color": "#0000FF", "style": "primary"},
                    {"type": "button", "action": {"type": "message", "label": "和", "text": "和"}, "color": "#00C300", "style": "primary"}
                ]}
            ]
        }
    }

@app.route("/", methods=["GET"])
def home():
    return "✅ 百家樂 LINE 機器人已部署成功！請透過 LINE 對話啟用。"

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    raw_input = event.message.text.strip()

    # 初始化設定
    user_memory['settings'].setdefault(user_id, {"logic": "正常邏輯"})
    user_memory.setdefault('cards', {}).setdefault(user_id, "")
    user_memory.setdefault('records', {}).setdefault(user_id, [])

    # ✅ 模式切換處理（支援簡寫與冒號）
    if raw_input in ["正常邏輯", "反邏輯"] or raw_input.startswith("設定模式：") or raw_input.startswith("設定模式:"):
        mode = raw_input.replace("設定模式：", "").replace("設定模式:", "")
        if mode in ["正常邏輯", "反邏輯"]:
            user_memory['settings'][user_id]["logic"] = mode
            print(f"目前 {user_id} 的下注邏輯模式：{mode}")  # 可選：console log
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ 已切換為「{mode}」模式"))
            return

    # 指令處理
    if raw_input in ["下課", "結束分析"]:
        user_memory['cards'][user_id] = ""
        user_memory['records'][user_id] = []
        user_memory['last_suggestion'][user_id] = ""
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已結束分析，歡迎再次使用！"))
        return

    if raw_input == "清除紀錄":
        user_memory['cards'][user_id] = ""
        user_memory['records'][user_id] = []
        user_memory['last_suggestion'][user_id] = ""
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已清除下注紀錄"))
        return

    if all(c in "莊閒和" for c in raw_input):
        if raw_input != "和":
            user_memory['cards'][user_id] += clean_input(raw_input)

        cards = user_memory['cards'][user_id]
        last = user_memory['last_suggestion'].get(user_id)

        if last and raw_input != "和":
            user_memory['records'][user_id].append({
                "suggestion": last,
                "hit": last == raw_input
            })

        suggestion = predict_next_bet(cards)

        # 🧠 根據邏輯模式反轉 suggestion
        logic_mode = user_memory['settings'][user_id]["logic"]
        if logic_mode == "反邏輯":
            suggestion = "莊" if suggestion == "閒" else "閒"

        confidence = calculate_confidence(cards, suggestion)
        hit_rate = calculate_hit_rate(cards)
        user_memory['last_suggestion'][user_id] = suggestion

        analysis_flex = generate_analysis_flex(cards, suggestion, confidence, hit_rate, logic_mode)

        messages = []
        if raw_input != "和" and user_memory['records'][user_id]:
            last_record = user_memory['records'][user_id][-1]
            result_text = f"好耶！這局開「{raw_input}」✅ 命中！" if last_record['hit'] else f"這局開「{raw_input}」❌ 沒中～"
            total_profit = sum([100 if r['hit'] else -100 for r in user_memory['records'][user_id]])
            profit_text = f"累積獲利：{total_profit:+} 元"
            messages.append(TextSendMessage(text=result_text))
            messages.append(TextSendMessage(text=profit_text))

        messages.append(FlexSendMessage(alt_text="百家樂分析結果", contents=analysis_flex))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    # 非法輸入提醒
    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒\n也可輸入：反邏輯 / 正常邏輯 切換模式"
    ))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
