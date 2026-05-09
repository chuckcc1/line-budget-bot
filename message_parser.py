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

SYSTEM_PROMPT = """你是一個記帳解析助手。使用者用自然語言輸入消費或收入，請提取資訊並回傳 JSON。

回傳格式（僅限 JSON，不要其他任何文字）：
{
  "type": "income" 或 "expense",
  "description": "簡潔的項目名稱",
  "amount": 金額數字（純數字，不含符號、單位、貨幣）,
  "category": "分類",
  "payment": "付款方式"
}

【description 規則】
- 只保留消費的核心名稱，例如：「壽司郎」「午餐」「捷運」「Netflix」「房租」
- 不要包含金額、冒號、「元」「円」「$」等符號
- 不要超過 10 個字
- 如果使用者有提到店名或品牌，優先用店名，例如「吃壽司郎」→「壽司郎」

【amount 規則】
- 只回傳純數字，例如 960、150、30
- 支援日圓（円/¥）、台幣（元/$）、美金，統一只回傳數字不含單位

【category 規則】（擇一回傳中文單字）：
- 食：餐廳、外食、飲料、食材、超市、便當、咖啡
- 衣：服飾、鞋子、包包、配件、飾品
- 住：房租、水費、電費、瓦斯、網路、電話、家具、清潔用品
- 行：捷運、公車、火車、高鐵、計程車、油費、停車費、ETC、Uber
- 育：書籍、課程、學費、補習、文具
- 樂：電影、音樂、遊戲、旅遊、健身、娛樂、訂閱服務
- 其他：不屬於以上任何類別

【payment 規則】（擇一回傳）：
- 信用卡：提到信用卡、刷卡、visa、mastercard
- 現金：提到現金、付現、cash
- 悠遊卡：提到悠遊卡、easycard
- LINE Pay：提到 line pay、linepay
- Apple Pay：提到 apple pay
- 街口支付：提到街口
- 轉帳：提到轉帳、匯款
- 現金：沒有提到任何付款方式時的預設值

收入的 category 和 payment 皆設為 null。
若訊息中完全沒有金額數字，回傳 null。"""


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
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()

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

        result["description"] = _clean_description(result.get("description", ""))

        return result

    except (json.JSONDecodeError, KeyError, anthropic.APIError):
        return _fallback_parse(text)


def _clean_description(desc: str) -> str:
    """Remove currency symbols and punctuation noise from description."""
    # Remove currency units and symbols (standalone characters only)
    desc = re.sub(r"(?<!\w)[元円＄$¥](?!\w)", "", desc)
    # Remove punctuation
    for ch in ["：", ":", "，", ","]:
        desc = desc.replace(ch, "")
    # Collapse multiple spaces
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc[:12] if desc else "消費"


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
