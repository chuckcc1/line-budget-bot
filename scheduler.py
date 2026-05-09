"""
Monthly report push notification scheduler.
Run this as a separate process: python scheduler.py
It pushes a monthly report to the configured LINE user ID on the 1st of each month.
"""
import os
import schedule
import time
from datetime import datetime
from linebot import LineBotApi
from linebot.models import TextSendMessage
from dotenv import load_dotenv

from sheets_handler import SheetsHandler
from report_generator import ReportGenerator

load_dotenv()

line_bot_api = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
sheets = SheetsHandler()
reporter = ReportGenerator(sheets)

TARGET_USER_ID = os.environ.get("LINE_TARGET_USER_ID", "")


def push_monthly_report():
    if not TARGET_USER_ID:
        print("LINE_TARGET_USER_ID not set — skipping push")
        return

    # Generate last month's report
    today = datetime.now()
    from datetime import timedelta
    last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    report = reporter.generate_monthly_report(last_month)

    try:
        line_bot_api.push_message(TARGET_USER_ID, TextSendMessage(text=report))
        print(f"[{today}] Monthly report pushed for {last_month}")
    except Exception as e:
        print(f"[{today}] Failed to push report: {e}")


# Send on the 1st of every month at 08:00
schedule.every().day.at("08:00").do(
    lambda: push_monthly_report() if datetime.now().day == 1 else None
)

if __name__ == "__main__":
    print("Scheduler started. Will push monthly report on the 1st of each month at 08:00.")
    while True:
        schedule.run_pending()
        time.sleep(60)
