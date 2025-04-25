from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os, random
import joblib

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

# 🧠 載入 AI 預測模型
model, encoder = joblib.load("ai_model.pkl")

# 🎟️ 一次性序號池（key: 序號, value: 綁定 user_id 或 None）
activation_codes = {
    "VIA-A01": None,
    "VIA-A02": None,
    "VIA-A03": None
}

# 🧠 記住已啟動的使用者
activated_users = set()

# 使用者記憶資料
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

def predict_ai(cards):
    if len(cards) < 5:
        return None  # 表示不夠預測，不建議下注
    last5 = cards[-5:]
    encoded = encoder.transform(last5).reshape(1, -1)
    prediction = model.predict(encoded)[0]
    return encoder.inverse_transform([prediction])[0]

def calculate_hit_rate(cards):
    if len(cards) <= 1: return 0
    return round(100 * sum(1 for i in range(1, len(cards)) if cards[i] != cards[i-1]) / (len(cards)-1), 1)

def analyze_pattern(cards):
    if len(cards) < 5:
        return None
    last5 = cards[-5:]
    if all(last5[i] != last5[i+1] for i in range(4)):
        return "🔁 出現單跳，建議觀望或進跳打法"
    if all(c == last5[0] for c in last5):
        return f"🔗 出現長龍（連續{len(last5)}次「{last5[0]}」），建議順勢壓注"
    if len(cards) >= 6 and all(c == cards[-6] for c in cards[-6:-1]) and cards[-1] != cards[-2]:
        return "🔄 轉勢出現，建議觀察是否變盤"
    return None

def generate_analysis_flex(cards, suggestion, hit_rate, logic_mode):
    mode_tip = f"⚙️ 當前預測模式：{logic_mode}（輸入 '原始邏輯' 或 'AI' 可切換）"
    count_z, count_x, count_h = cards.count('莊'), cards.count('閒'), cards.count('和')
    total = len(cards)
    percent = lambda c: round(c / total * 100, 1) if total else 0
    color_map = {"莊": "#FF4444", "閒": "#0000FF", "和": "#00C300"}
    return {
        "type": "bubble",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md", "paddingAll": "lg",
            "contents": [
                {"type": "text", "text": mode_tip, "size": "sm", "color": "#888888"},
                {"type": "text", "text": "📊 百家樂分析結果", "weight": "bold", "size": "lg"},
                {"type": "separator"},
                {"type": "text", "text": f"莊：{percent(count_z)}%", "size": "sm"},
                {"type": "text", "text": f"閒：{percent(count_x)}%", "size": "sm"},
                {"type": "text", "text": f"和：{percent(count_h)}%", "size": "sm"},
                {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "size": "sm"},
                {"type": "separator"},
                {"type": "text", "text": f"推薦下注：{suggestion}（{logic_mode}）", "weight": "bold", "color": color_map[suggestion]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "button", "action": {"type": "message", "label": "莊", "text": "莊"}, "color": "#FF4444", "style": "primary"},
                    {"type": "button", "action": {"type": "message", "label": "閒", "text": "閒"}, "color": "#0000FF", "style": "primary"},
                    {"type": "button", "action": {"type": "message", "label": "和", "text": "和"}, "color": "#00C300", "style": "primary"}
                ]}
            ]
        }
    }

# 💡 增加 AI 模式設定邏輯可用 "AI" 指令開啟，也可用 "原始邏輯" 切回基本預測
# 使用者輸入 "AI" → user_memory['settings'][user_id]["logic"] = "AI預測"
# 使用者輸入 "原始邏輯" → 切回 predict_next_bet(cards)
# 判斷方式:
# if user_memory['settings'][user_id]["logic"] == "AI預測": 使用 AI 預測，否則使用原始預測



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

    # 驗證授權
    if raw_input.startswith("序號：") or raw_input.startswith("序號:"):
        code = raw_input.replace("序號：", "").replace("序號:", "").strip()
        if code in activation_codes and activation_codes[code] is None:
            activation_codes[code] = user_id
            activated_users.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 序號驗證成功，功能已解鎖"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 無效或已使用的序號，請確認後重新輸入"))
        return

    if user_id not in activated_users:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="🔒 尚未啟用，請輸入授權序號才能使用功能"
        ))
        return

    # 初始化使用者資料
    user_memory['settings'].setdefault(user_id, {"logic": "正常邏輯"})
    user_memory.setdefault('cards', {}).setdefault(user_id, "")
    user_memory.setdefault('records', {}).setdefault(user_id, [])

    # 模式切換
    if raw_input == "AI":
        user_memory['settings'][user_id]["logic"] = "AI預測"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已切換為 AI 預測模式"))
        return
    if raw_input == "原始邏輯":
        user_memory['settings'][user_id]["logic"] = "原始邏輯"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已切換為原始預測邏輯"))
        return

    # 結束與清除
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

    # 處理有效牌路
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

        logic_mode = user_memory['settings'][user_id]["logic"]
        if logic_mode == "AI預測":
            suggestion = predict_ai(cards)
            if suggestion is None:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text="🔍 AI 模式需要至少 5 手牌路才能開始預測，請先輸入前 5 局開牌結果"
                ))
                return
        else:
            suggestion = predict_next_bet(cards)

        hit_rate = calculate_hit_rate(cards)
        user_memory['last_suggestion'][user_id] = suggestion

        analysis_flex = generate_analysis_flex(cards, suggestion, hit_rate, logic_mode)
        messages = []

        if raw_input != "和" and user_memory['records'][user_id]:
            last_record = user_memory['records'][user_id][-1]
            result_text = f"好耶！這局開「{raw_input}」✅ 命中！" if last_record['hit'] else f"這局開「{raw_input}」❌ 沒中～"
            total_profit = sum([100 if r['hit'] else -100 for r in user_memory['records'][user_id]])
            profit_text = f"累積獲利：{total_profit:+} 元"
            messages.append(TextSendMessage(text=result_text))
            messages.append(TextSendMessage(text=profit_text))

        pattern_tip = analyze_pattern(cards)
        if pattern_tip:
            messages.append(TextSendMessage(text=pattern_tip))

        messages.append(FlexSendMessage(alt_text="百家樂分析結果", contents=analysis_flex))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(
    text="請輸入包含『莊』『閒』『和』的牌路，例如：莊閒莊莊閒\n或輸入：AI / 原始邏輯 切換模式"
))

