import random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

activation_codes = {"VIA-A01": None, "VIA-A02": None, "VIA-A03": None}
activated_users = set()

user_memory = {
    'records': {},
    'last_suggestion': {},
    'cards': {},
    'settings': {},
    'game_count': {},
}

def clean_input(text):
    return ''.join(c for c in '莊閒和')

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last3 = cards[-3:]
    if all(c == last3[0] for c in last3):
        return last3[0]
    return '閒' if cards[-1] == '莊' else '莊'

def reverse_bet(suggestion):
    if suggestion == '莊': return '閒'
    if suggestion == '閒': return '莊'
    return '和'

def calculate_hit_rate(cards):
    if len(cards) <= 1: return 0
    return round(100 * sum(1 for i in range(1, len(cards)) if cards[i] != cards[i-1]) / (len(cards)-1), 1)

# 🔥 修正版 detect_streak（正確計算連開莊 or 閒）
def detect_streak(cards, threshold=4):
    if len(cards) < threshold:
        return None
    last = cards[-1]
    count = 1
    for c in reversed(cards[:-1]):
        if c == last:
            count += 1
        else:
            break
    if count >= threshold and last in ['莊', '閒']:
        return last
    return None

def generate_analysis_flex(cards, suggestion, hit_rate, logic_mode, games, wins, losses):
    mode_tip = f"⚙️ 當前模式：{logic_mode}"
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
                {"type": "text", "text": f"莊：{percent(count_z)}% 閒：{percent(count_x)}% 和：{percent(count_h)}%", "size": "sm"},
                {"type": "text", "text": f"🎯 命中率：{hit_rate}%", "size": "sm"},
                {"type": "text", "text": f"局數：{games}｜贏：{wins}｜輸：{losses}", "size": "sm"},
                {"type": "separator"},
                {"type": "text", "text": f"推薦下注：{suggestion}", "weight": "bold", "size": "xl", "color": color_map[suggestion], "margin": "md"},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "button", "action": {"type": "message", "label": "莊", "text": "莊"}, "style": "primary", "color": "#FF4444"},
                    {"type": "button", "action": {"type": "message", "label": "閒", "text": "閒"}, "style": "primary", "color": "#0000FF"},
                    {"type": "button", "action": {"type": "message", "label": "和", "text": "和"}, "style": "primary", "color": "#00C300"}
                ]}
            ]
        }
    }

@app.route('/', methods=['GET'])
def home():
    return 'LINE Baccarat Bot is running.', 200

@app.route('/callback', methods=['GET', 'POST'])
def callback():
    if request.method == 'GET':
        return 'Callback endpoint is alive.', 200
    signature = request.headers.get('X-Line-Signature', '')
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

    # 序號驗證
    if raw_input.startswith('序號：') or raw_input.startswith('序號:'):
        code = raw_input.replace('序號：', '').replace('序號:', '').strip()
        if code in activation_codes and activation_codes[code] is None:
            activation_codes[code] = user_id
            activated_users.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 序號驗證成功，功能已解鎖'))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='❌ 無效或已使用的序號'))
        return

    if user_id not in activated_users:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='🔒 請先輸入授權序號'))
        return

    # 初始化使用者資料
    user_memory['settings'].setdefault(user_id, {'logic': '正常邏輯'})
    user_memory.setdefault('cards', {}).setdefault(user_id, '')
    user_memory.setdefault('records', {}).setdefault(user_id, [])
    user_memory.setdefault('game_count', {}).setdefault(user_id, 0)

    # 下課指令
    if raw_input == '下課':
        for key in ['cards', 'records', 'last_suggestion', 'settings', 'game_count']:
            user_memory[key].pop(user_id, None)
        flex_message = {
            "type": "bubble",
            "body": {
                "type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ 已下課", "weight": "bold", "size": "xl", "align": "center"},
                    {"type": "text", "text": "所有紀錄已清除", "size": "md", "align": "center", "margin": "md"},
                    {"type": "text", "text": "感謝使用 🙏", "size": "sm", "align": "center", "margin": "md"}
                ]
            }
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="✅ 已下課", contents=flex_message))
        return

    # 切換邏輯
    if raw_input == '原始邏輯':
        user_memory['settings'][user_id]['logic'] = '正常邏輯'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 切換到正常預測邏輯'))
        return

    if raw_input == '反邏輯':
        user_memory['settings'][user_id]['logic'] = '反邏輯'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 切換到反邏輯模式'))
        return

    # 正常處理牌路
    if all(c in '莊閒和' for c in raw_input):
        if raw_input != '和':
            user_memory['cards'][user_id] += clean_input(raw_input)

        cards = user_memory['cards'][user_id]
        last = user_memory['last_suggestion'].get(user_id)

        if last and raw_input != '和':
            user_memory['records'][user_id].append({'suggestion': last, 'hit': last == raw_input})
            user_memory['game_count'][user_id] += 1

        logic_mode = user_memory['settings'][user_id]['logic']

        # 🧠 節奏轉判斷
        streak = detect_streak(cards)
        if streak:
            suggestion = streak
        else:
            suggestion = predict_next_bet(cards)
            if logic_mode == '反邏輯':
                suggestion = reverse_bet(suggestion)

        hit_rate = calculate_hit_rate(cards)
        user_memory['last_suggestion'][user_id] = suggestion

        wins = sum(1 for r in user_memory['records'][user_id] if r['hit'])
        losses = user_memory['game_count'][user_id] - wins
        games = user_memory['game_count'][user_id]

        analysis_flex = generate_analysis_flex(cards, suggestion, hit_rate, logic_mode, games, wins, losses)

        messages = []

        if raw_input != '和' and user_memory['records'][user_id]:
            last_record = user_memory['records'][user_id][-1]
            result_text = f"好耶！這局開「{raw_input}」✅ 命中！" if last_record['hit'] else f"這局開「{raw_input}」❌ 沒中～"
            total_profit = sum([100 if r['hit'] else -100 for r in user_memory['records'][user_id]])
            profit_text = f"累積獲利：{total_profit:+} 元"
            messages.append(TextSendMessage(text=result_text))
            messages.append(TextSendMessage(text=profit_text))

        messages.append(FlexSendMessage(alt_text='百家樂分析結果', contents=analysis_flex))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    # 非法輸入
    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text='⚠️ 請輸入正確的牌路，例如：莊閒莊莊閒'
    ))

if __name__ == '__main__':
    app.run(debug=True)
