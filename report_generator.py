from collections import defaultdict
from datetime import datetime, timedelta

CAT_EMOJI = {
    "食": "🍜", "衣": "👗", "住": "🏠",
    "行": "🚌", "育": "📚", "樂": "🎉", "其他": "📦",
}

# Alert when a single category exceeds this fraction of total income
ALERT_RATIO = 0.30
# Alert when total expense-to-income ratio exceeds this
OVERSPEND_RATIO = 0.90


class ReportGenerator:
    def __init__(self, sheets_handler):
        self.sheets = sheets_handler

    # ── monthly ───────────────────────────────────────────────────────────────

    def generate_monthly_report(self, year_month: str = None) -> str:
        if not year_month:
            year_month = datetime.now().strftime("%Y-%m")
        return self._build_monthly_report(year_month)

    def generate_last_month_report(self) -> str:
        today = datetime.now()
        first_day = today.replace(day=1)
        last_month = (first_day - timedelta(days=1)).strftime("%Y-%m")
        return self._build_monthly_report(last_month)

    def _build_monthly_report(self, year_month: str) -> str:
        records = self.sheets.get_monthly_records(year_month)
        if not records:
            return f"📊 {year_month} 尚無任何記錄"

        total_income = 0.0
        total_expense = 0.0
        categories: dict[str, float] = defaultdict(float)

        for r in records:
            try:
                amount = float(r.get("金額", 0))
            except (ValueError, TypeError):
                continue
            if r.get("類型") == "收入":
                total_income += amount
            else:
                total_expense += amount
                cat = r.get("分類", "其他") or "其他"
                categories[cat] += amount

        balance = total_income - total_expense
        balance_icon = "😊" if balance >= 0 else "😟"

        lines = [
            f"📊 {year_month} 月度報表",
            "─" * 22,
            f"💰 總收入：${total_income:>10,.0f}",
            f"💸 總支出：${total_expense:>10,.0f}",
            f"{balance_icon} 結　餘：${balance:>10,.0f}",
        ]

        if categories:
            lines += ["", "📂 支出分類明細："]
            for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                emoji = CAT_EMOJI.get(cat, "📦")
                pct = amount / total_expense * 100 if total_expense else 0
                alert = _income_alert(amount, total_income)
                lines.append(f"  {emoji} {cat}：${amount:,.0f}（{pct:.1f}%）{alert}")

        # Alerts section
        alerts = _build_alerts(total_income, total_expense, balance, categories)
        if alerts:
            lines += ["", "🔔 提醒事項："]
            lines += [f"  {a}" for a in alerts]

        return "\n".join(lines)

    # ── weekly ────────────────────────────────────────────────────────────────

    def generate_weekly_report(self) -> str:
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        all_records = self.sheets.get_all_records()
        week_records = []
        for r in all_records:
            try:
                date_str = str(r.get("日期", ""))[:10]
                if datetime.strptime(date_str, "%Y-%m-%d") >= week_start:
                    week_records.append(r)
            except (ValueError, TypeError):
                continue

        if not week_records:
            return "📊 本週尚無記錄"

        income = sum(float(r.get("金額", 0)) for r in week_records if r.get("類型") == "收入")
        expense = sum(float(r.get("金額", 0)) for r in week_records if r.get("類型") == "支出")
        categories: dict[str, float] = defaultdict(float)
        for r in week_records:
            if r.get("類型") == "支出":
                cat = r.get("分類", "其他") or "其他"
                categories[cat] += float(r.get("金額", 0))

        lines = [
            f"📊 本週小結（{week_start.strftime('%m/%d')} 起）",
            "─" * 22,
            f"💰 收入：${income:,.0f}",
            f"💸 支出：${expense:,.0f}",
            f"📝 共 {len(week_records)} 筆記錄",
        ]

        if categories:
            lines += ["", "📂 支出分類："]
            for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  {CAT_EMOJI.get(cat, '📦')} {cat}：${amount:,.0f}")

        return "\n".join(lines)

    # ── recent records ────────────────────────────────────────────────────────

    def get_recent_records(self, n: int = 10) -> str:
        records = self.sheets.get_recent_records(n)
        if not records:
            return "📝 目前尚無記錄"

        lines = [f"📝 最近 {len(records)} 筆記錄", "─" * 22]
        for r in reversed(records):
            icon = "💰" if r.get("類型") == "收入" else "💸"
            cat = f"[{r.get('分類', '')}] " if r.get("類型") == "支出" else ""
            date = str(r.get("日期", ""))[:10]
            try:
                amount = f"${float(r.get('金額', 0)):,.0f}"
            except (ValueError, TypeError):
                amount = str(r.get("金額", ""))
            lines.append(f"{icon} {date} {cat}{r.get('描述', '')} {amount}")

        return "\n".join(lines)


# ── helpers ───────────────────────────────────────────────────────────────────

def _income_alert(amount: float, total_income: float) -> str:
    if total_income > 0 and amount / total_income > ALERT_RATIO:
        return " ⚠️"
    return ""


def _build_alerts(
    total_income: float,
    total_expense: float,
    balance: float,
    categories: dict[str, float],
) -> list[str]:
    alerts = []

    if balance < 0:
        alerts.append(f"🚨 本月超支 ${abs(balance):,.0f}，請立即檢視支出！")
    elif total_income > 0 and total_expense / total_income > OVERSPEND_RATIO:
        alerts.append(f"⚠️ 支出已達收入的 {total_expense/total_income*100:.0f}%，接近預算上限")

    if total_income > 0:
        for cat, amount in categories.items():
            if amount / total_income > ALERT_RATIO:
                alerts.append(
                    f"⚠️ 「{cat}」支出偏高（佔收入 {amount/total_income*100:.1f}%），建議控制在 30% 以內"
                )

    return alerts
