import os
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv

from message_parser import parse_message
from sheets_handler import SheetsHandler
from report_generator import ReportGenerator

load_dotenv()

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])

sheets = SheetsHandler()
reporter = ReportGenerator(sheets)


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    reply = process_message(text)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


def process_message(text: str) -> str:
    # Report commands
    if text in ["報表", "本月報表", "月報", "月報表"]:
        return reporter.generate_monthly_report()
    if text in ["上月報表", "上個月報表", "上月"]:
        return reporter.generate_last_month_report()
    if text in ["本週", "週報", "本週報表"]:
        return reporter.generate_weekly_report()
    if text in ["說明", "help", "Help", "幫助", "使用說明"]:
        return get_help_text()
    if text in ["查詢", "最近記錄", "最近"]:
        return reporter.get_recent_records()

    # Parse as transaction
    result = parse_message(text)
    if result is None:
        return (
            "❓ 無法解析這則訊息\n\n"
            "範例格式：\n"
            "• 午餐 120\n"
            "• 收入 薪水 50000\n"
            "• 捷運 30\n\n"
            "輸入「說明」查看完整使用說明"
        )

    try:
        sheets.add_record(result)
    except Exception as e:
        return f"⚠️ 記錄失敗，請稍後再試\n錯誤：{e}"

    today = datetime.now().strftime("%m/%d")

    if result["type"] == "income":
        income_emoji = {
            "薪資": "💼", "獎金": "🎯", "投資": "📈",
            "兼職": "🛠", "租金": "🏠", "贈與": "🎁",
            "退款": "↩️", "其他收入": "💰",
        }.get(result.get("category", "其他收入"), "💰")
        cat = result.get("category") or "其他收入"
        return (
            f"✅ 已記錄收入｜{today}\n"
            f"{income_emoji} 分類：{cat}\n"
            f"💰 {result['description']}：${result['amount']:,.0f}"
        )
    else:
        cat_emoji = {
            "食": "🍜", "衣": "👗", "住": "🏠",
            "行": "🚌", "育": "📚", "樂": "🎉",
            "帳單": "🧾", "其他": "📦"
        }.get(result.get("category", "其他"), "📦")
        pay_emoji = {
            "信用卡": "💳", "現金": "💵", "悠遊卡": "🎫",
            "LINE Pay": "📱", "Apple Pay": "📱", "街口支付": "📱", "轉帳": "🏦"
        }.get(result.get("payment", "現金"), "💵")
        payment = result.get("payment") or "現金"
        return (
            f"✅ 已記錄支出｜{today}\n"
            f"{cat_emoji} 分類：{result.get('category', '其他')}\n"
            f"{pay_emoji} 付款：{payment}\n"
            f"💸 {result['description']}：${result['amount']:,.0f}"
        )


def get_help_text() -> str:
    return (
        "📖 使用說明\n"
        "─────────────────\n"
        "【記錄支出】\n"
        "直接輸入「項目 金額」\n"
        "例：午餐 120\n"
        "例：捷運票 30\n"
        "例：Netflix 300\n\n"
        "【記錄收入】\n"
        "輸入「收入 描述 金額」\n"
        "例：收入 薪水 50000\n"
        "例：收入 獎金 5000\n\n"
        "【查詢報表】\n"
        "• 本月報表 → 月度收支報告\n"
        "• 上月報表 → 上個月報告\n"
        "• 本週 → 本週小結\n"
        "• 最近 → 最近 10 筆\n\n"
        "【支出自動分類】\n"
        "🍜 食 🧥 衣 🏠 住\n"
        "🚌 行 📚 育 🎉 樂 📦 其他"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
