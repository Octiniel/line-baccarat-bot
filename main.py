import random
import os
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage

# 初始化 Flask
app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))

# 序號池（key: 序號, value: 綁定 user_id）
activation_codes = {
    "VIA-A01": None,
    "VIA-A02": None,
    "VIA-A03": None
}

# 已啟用的使用者
activated_users = set()

# 使用者記憶資料
user_memory = {
    'cards': {},
    'records': {},
    'last_suggestion': {},
    'settings': {},
    'game_count': {}
}

# 最近10局牌路紀錄
recent_results = []

# 總統計
stats = {
    'total_bets': 0,
    'hit_bets': 0,
    'profit': 0
}
# 清理輸入，只保留莊閒和
def clean_input(text):
    return ''.join(c for c in text if c in '莊閒和')

# 預測下一局下注方向
def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last3 = cards[-3:]
    if all(c == last3[0] for c in last3):
        return last3[0]
    return '閒' if cards[-1] == '莊' else '莊'

# 反邏輯下注方向
def reverse_bet(suggestion):
    if suggestion == '莊': return '閒'
    if suggestion == '閒': return '莊'
    return '和'

# 計算命中率
def calculate_hit_rate(cards):
    if len(cards) <= 1:
        return 0
    return round(100 * sum(1 for i in range(1, len(cards)) if cards[i] != cards[i-1]) / (len(cards)-1), 1)

# 偵測四連單邊
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

# 最近10局記錄
def add_new_result(result):
    global recent_results
    if result not in ['莊', '閒', '和']:
        return
    recent_results.append(result)
    if len(recent_results) > 10:
        recent_results.pop(0)

# 主路盤型分析
def detect_panxing():
    if len(recent_results) < 10:
        return "資料不足，繼續收集中"
    if recent_results[-3:] == ['莊', '莊', '莊'] or recent_results[-3:] == ['閒', '閒', '閒']:
        return "長龍盤，建議跟龍"
    alternated = True
    for i in range(1, 6):
        if recent_results[-i] == recent_results[-i-1]:
            alternated = False
            break
    if alternated:
        return "單跳盤，建議跟跳"
    if recent_results[-5:-2] == ['莊', '莊', '莊'] and recent_results[-2:] == ['閒', '閒']:
        return "轉勢盤，建議跟閒"
    if recent_results[-5:-2] == ['閒', '閒', '閒'] and recent_results[-2:] == ['莊', '莊']:
        return "轉勢盤，建議跟莊"
    mixed = False
    for i in range(5):
        if recent_results[-(i+2)] == recent_results[-(i+1)]:
            mixed = True
            break
    if not mixed:
        return "亂盤，建議觀望"
    return "目前無明確型態，繼續觀察"

# 主路分析文字
def generate_reply_with_confidence(panxing):
    if panxing == "長龍盤，建議跟龍":
        return "📈 主路分析：長龍盤！建議跟龍 ➡️ 信心80%"
    elif panxing == "單跳盤，建議跟跳":
        return "📈 主路分析：單跳盤！建議跟跳 ➡️ 信心70%"
    elif "轉勢盤" in panxing:
        return "📈 主路分析：轉勢盤！建議跟新方向 ➡️ 信心65%"
    elif panxing == "亂盤，建議觀望":
        return "📈 主路分析：亂盤！建議觀望 ➡️ 信心低"
    else:
        return "📈 主路分析：資料收集中，請持續觀察。"

# 更新統計
def update_stats(suggest, actual):
    global stats
    stats['total_bets'] += 1
    if suggest == actual:
        stats['hit_bets'] += 1
        stats['profit'] += 100
    else:
        stats['profit'] -= 100

# 計算命中率
def get_hit_rate():
    if stats['total_bets'] == 0:
        return 0
    return round(stats['hit_bets'] / stats['total_bets'] * 100, 2)

# 顯示統計
def show_stats():
    return f"""目前統計：
- 總下注：{stats['total_bets']} 局
- 命中次數：{stats['hit_bets']} 局
- 命中率：{get_hit_rate()}%
- 累積獲利：{stats['profit']} 元
"""
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

    # 🧩 序號驗證
    if raw_input.startswith('序號：') or raw_input.startswith('序號:'):
        code = raw_input.replace('序號：', '').replace('序號:', '').strip()
        if code in activation_codes and activation_codes[code] is None:
            activation_codes[code] = user_id
            activated_users.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 序號驗證成功，功能已解鎖'))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='❌ 無效或已使用的序號'))
        return

    # 🛡️ 沒授權不給用
    if user_id not in activated_users:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='🔒 請先輸入授權序號'))
        return

    # 初始化使用者資料
    user_memory['settings'].setdefault(user_id, {'logic': '正常邏輯'})
    user_memory.setdefault('cards', {}).setdefault(user_id, '')
    user_memory.setdefault('records', {}).setdefault(user_id, [])
    user_memory.setdefault('game_count', {}).setdefault(user_id, 0)

    # 🧹 下課指令
    if raw_input == '下課':
        for key in ['cards', 'records', 'last_suggestion', 'settings', 'game_count']:
            user_memory[key].pop(user_id, None)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已下課，所有紀錄已清除"))
        return

    # 模式切換
    if raw_input == '原始邏輯':
        user_memory['settings'][user_id]['logic'] = '正常邏輯'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 已切換到正常預測邏輯'))
        return

    if raw_input == '反邏輯':
        user_memory['settings'][user_id]['logic'] = '反邏輯'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='✅ 已切換到反邏輯模式'))
        return

    # 🧠 正式處理下注與記錄
    if all(c in '莊閒和' for c in raw_input):
        for c in clean_input(raw_input):
            if c != '和':
                user_memory['cards'][user_id] += c
                cards = user_memory['cards'][user_id]
                logic_mode = user_memory['settings'][user_id]['logic']

                # 優先偵測四連莊閒
                streak = detect_streak(cards)
                if streak:
                    suggestion = streak
                else:
                    suggestion = predict_next_bet(cards)
                    if logic_mode == '反邏輯':
                        suggestion = reverse_bet(suggestion)

                last = user_memory['last_suggestion'].get(user_id)
                messages = []

                # 記錄並判斷命中
                if last is not None:
                    user_memory['records'][user_id].append({'suggestion': last, 'hit': last == c})
                    user_memory['game_count'][user_id] += 1
                    update_stats(last, c)

                    result_text = f"好耶！這局開「{c}」✅ 命中！" if last == c else f"這局開「{c}」❌ 沒中～"
                    profit_text = f"累積獲利：{stats['profit']} 元"
                    messages.append(TextSendMessage(text=result_text))
                    messages.append(TextSendMessage(text=profit_text))

                # 更新最後一次建議
                user_memory['last_suggestion'][user_id] = suggestion

                # 更新主路紀錄
                add_new_result(c)
                panxing = detect_panxing()
                panxing_msg = generate_reply_with_confidence(panxing)
                messages.append(TextSendMessage(text=panxing_msg))

                # 推薦下注 Flex 卡片
                flex_message = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "paddingAll": "lg",
                        "contents": [
                            {"type": "text", "text": f"🎯 推薦下注：{suggestion}", "size": "xl", "weight": "bold"},
                            {"type": "separator"},
                            {"type": "text", "text": f"目前命中率：{calculate_hit_rate(cards)}%", "size": "md"},
                            {"type": "text", "text": f"總局數：{user_memory['game_count'][user_id]} 局", "size": "md"},
                            {"type": "text", "text": f"當前模式：{logic_mode}", "size": "sm", "color": "#888888"},
                        ]
                    }
                }
                messages.append(FlexSendMessage(alt_text="百家樂建議", contents=flex_message))

                line_bot_api.reply_message(event.reply_token, messages)
                return

    # 非法輸入
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text='⚠️ 請輸入正確牌路，例如：莊閒莊莊閒'))
if __name__ == '__main__':
    app.run(debug=True)
