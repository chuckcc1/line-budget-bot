import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS_DETAIL = ["日期", "類型", "描述", "分類", "金額", "年月"]
HEADERS_MONTHLY = ["年月", "總收入", "總支出", "結餘", "食", "衣", "住", "行", "育", "樂", "其他"]


class SheetsHandler:
    def __init__(self):
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

        self._gc = gspread.authorize(creds)
        self._spreadsheet = self._gc.open_by_key(os.environ["GOOGLE_SPREADSHEET_ID"])
        self._ensure_sheets()

    # ── sheet access ──────────────────────────────────────────────────────────

    def _sheet(self, name: str) -> gspread.Worksheet:
        return self._spreadsheet.worksheet(name)

    def _ensure_sheets(self):
        existing = {ws.title for ws in self._spreadsheet.worksheets()}

        if "明細" not in existing:
            ws = self._spreadsheet.add_worksheet("明細", rows=5000, cols=6)
            ws.append_row(HEADERS_DETAIL)
            # Freeze header row
            ws.freeze(rows=1)

        if "月報" not in existing:
            ws = self._spreadsheet.add_worksheet("月報", rows=200, cols=11)
            ws.append_row(HEADERS_MONTHLY)
            ws.freeze(rows=1)

    # ── write ─────────────────────────────────────────────────────────────────

    def add_record(self, record: dict):
        now = datetime.now()
        row = [
            now.strftime("%Y-%m-%d %H:%M"),
            "收入" if record["type"] == "income" else "支出",
            record.get("description", ""),
            record.get("category", "") if record["type"] == "expense" else "收入",
            record["amount"],
            now.strftime("%Y-%m"),
        ]
        self._sheet("明細").append_row(row, value_input_option="USER_ENTERED")

    # ── read ──────────────────────────────────────────────────────────────────

    def get_monthly_records(self, year_month: str = None) -> list[dict]:
        if not year_month:
            year_month = datetime.now().strftime("%Y-%m")
        all_records = self._sheet("明細").get_all_records()
        return [r for r in all_records if r.get("年月") == year_month]

    def get_recent_records(self, n: int = 10) -> list[dict]:
        all_records = self._sheet("明細").get_all_records()
        return all_records[-n:] if len(all_records) >= n else all_records

    def get_all_records(self) -> list[dict]:
        return self._sheet("明細").get_all_records()
