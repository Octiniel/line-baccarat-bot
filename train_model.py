import joblib
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier

# 模擬資料（前5局 → 預測第6局）
samples = [
    list("莊閒莊閒莊"), list("閒莊閒莊閒"), list("莊莊閒閒莊"),
    list("閒閒莊莊閒"), list("莊閒閒莊莊"), list("閒莊莊閒閒"),
    list("莊莊莊閒閒"), list("閒閒閒莊莊"), list("莊閒莊閒閒"),
    list("閒莊閒莊莊"), list("莊莊閒閒閒"), list("閒閒莊莊莊"),
]
labels = ["閒", "莊", "莊", "閒", "閒", "莊", "莊", "閒", "莊", "閒", "莊", "閒"]

# 編碼文字為數字
encoder = LabelEncoder()
X = [encoder.fit_transform(x) for x in samples]
y = encoder.transform(labels)

# 模型訓練
model = DecisionTreeClassifier()
model.fit(X, y)

# 儲存模型與編碼器
joblib.dump((model, encoder), "ai_model.pkl")
