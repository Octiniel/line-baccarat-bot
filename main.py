import random
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import os

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

# 🎟️ 一次性序號池
activation_codes = {
    "VIA-A01": None,
    "VIA-A02": None,
    "VIA-A03": None
}

# 🧠 啟動的使用者
activated_users = set()

# 使用者記憶資料
user_memory = {
    'records': {},            # 勝負紀錄
    'last_suggestion': {},     # 上一次建議
    'cards': {},               # 牌路紀錄
    'settings': {},            # 模式設定
    'game_count': {},          # 總局數
}

def clean_input(text):
    return ''.join(c for c in text if c in '莊閒和')

def predict_next_bet(cards):
    if len(cards) < 3:
        return random.choice(['莊', '閒'])
    last3 = cards[-3:]
    if all(c == last3[0] for c in last3):
        return last3[0]
    return '閒' if cards[-1] == '莊' else '莊'

def reverse_bet(suggestion):
    if suggestion == '莊':
        return '閒'
    elif suggestion == '閒':
        return '莊'
    else:
        return '和'  # 和不反

def calculate_hit_rate(cards):
    if len(cards) <= 1:
        return 0
    return round(100 * sum(1 for i in range(1, len(cards)) if cards[i] != cards[i-1]) / (len(cards)-1), 1)
