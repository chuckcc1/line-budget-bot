import os
import json
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


INCOME_KEYWORDS = ["收入", "薪水", "薪資", "獎金", "兼職", "副業", "紅包", "利息", "退款", "退稅"]

SYSTEM_PROMPT = """你是一個記帳解析助手。使用者會輸入記帳訊息，請提取資訊並回傳 JSON。

回傳格式（僅限 JSON，不要其他文字）：
{
  "type": "income" 或 "expense",
  "description": "簡短描述（10字以內）",
  "amount": 金額數字（正整數或小數，不含符號）,
  "category": "分類"
}

支出分類規則（擇一回傳中文單字）：
- 食：餐廳、外食、飲料、食材、超市食品、便當
- 衣：服飾、鞋子、包包、配件、飾品
- 住：房租、水費、電費、瓦斯、網路、電話、家具、清潔用品
- 行：捷運、公車、火車、高鐵、計程車、油費、停車費、ETC
- 育：書籍、課程、學費、補習、文具
- 樂：電影、音樂、遊戲、旅遊、健身、娛樂、訂閱服務
- 其他：不屬於以上任何類別

收入不需要 category（可設為 null）。
若無法判斷金額，回傳 null。"""


def parse_message(text: str):
    """Parse user message into a transaction record using Claude."""
    # Must contain a number to be a valid transaction
    if not re.search(r"\d+", text):
        return None

    try:
        client = get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text.strip()

        if raw.lower() == "null":
            return None

        result = json.loads(raw)

        if result is None:
            return None

        amount = result.get("amount")
        if not amount or float(amount) <= 0:
            return None

        result["amount"] = float(amount)

        if result["type"] == "expense" and not result.get("category"):
            result["category"] = "其他"

        return result

    except (json.JSONDecodeError, KeyError, anthropic.APIError):
        return _fallback_parse(text)


def _fallback_parse(text: str):
    """Rule-based fallback parser."""
    amount_match = re.search(r"(\d+(?:\.\d{1,2})?)", text)
    if not amount_match:
        return None

    amount = float(amount_match.group(1))

    if any(kw in text for kw in INCOME_KEYWORDS):
        desc = re.sub(r"\d+", "", text).strip() or "收入"
        return {"type": "income", "description": desc, "amount": amount, "category": None}

    # Simple keyword categorization
    category = _keyword_category(text)
    desc = re.sub(r"\d+", "", text).strip() or text[:10]
    return {"type": "expense", "description": desc, "amount": amount, "category": category}


def _keyword_category(text: str) -> str:
    rules = {
        "食": ["餐", "飯", "麵", "吃", "早餐", "午餐", "晚餐", "飲料", "咖啡", "便當", "超市", "全家", "7-11", "超商"],
        "衣": ["衣", "褲", "裙", "鞋", "包", "帽", "配件", "飾品"],
        "住": ["房租", "水費", "電費", "瓦斯", "網路", "電話", "家具", "清潔"],
        "行": ["捷運", "公車", "火車", "高鐵", "計程車", "油", "停車", "ETC", "Uber"],
        "育": ["書", "課程", "學費", "補習", "文具"],
        "樂": ["電影", "音樂", "遊戲", "旅遊", "健身", "Netflix", "Spotify", "訂閱"],
    }
    for cat, keywords in rules.items():
        if any(kw in text for kw in keywords):
            return cat
    return "其他"
