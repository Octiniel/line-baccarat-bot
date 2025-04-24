def get_prediction(card_input):
    cards = [c for c in card_input if c in ['莊', '閒']]
    if not cards or len(cards) < 3:
        return "請至少提供 3 個以上的牌路資料（例如：牌路：莊閒莊閒閒）"
    
    last = cards[-1]
    prev = cards[-2]
    
    if last == prev:
        recommendation = last
    else:
        recommendation = '閒' if last == '莊' else '莊'

    return f"✅ 推薦下注：{recommendation}\\n💰 注碼建議：100 元（預設模式）"
