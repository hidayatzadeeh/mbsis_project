from datetime import date
from decimal import Decimal

from django.db.models import Sum

from core.models import JournalLine, Account


def generate_income_statement(year: int) -> dict:
    """
    Basit gelir tablosu:
      - 6xx (veya Account.INCOME)  -> Gelirler
      - 7xx (veya Account.EXPENSE) -> Giderler

    Yıl içindeki tüm kayıtlar üzerinden hesaplar.
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    lines = (
        JournalLine.objects
        .select_related("entry", "account")
        .filter(entry__date__gte=start, entry__date__lte=end)
    )

    qs = (
        lines
        .values("account__code", "account__name", "account__type")
        .annotate(
            debit_sum=Sum("debit"),
            credit_sum=Sum("credit"),
        )
        .order_by("account__code")
    )

    incomes = []
    expenses = []
    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")

    for r in qs:
        code = r["account__code"]
        name = r["account__name"]
        acc_type = r["account__type"]

        d = r["debit_sum"] or Decimal("0.00")
        c = r["credit_sum"] or Decimal("0.00")

        is_income = (code and code.startswith("6")) or (acc_type == Account.INCOME)

        is_expense = (code and code.startswith("7")) or (acc_type == Account.EXPENSE)

        if not is_income and not is_expense:
            continue

        if is_income:
            amount = c - d  
            if amount == 0:
                continue
            incomes.append({
                "code": code,
                "name": name,
                "amount": amount,
            })
            total_income += amount

        elif is_expense:
            amount = d - c  
            if amount == 0:
                continue
            expenses.append({
                "code": code,
                "name": name,
                "amount": amount,
            })
            total_expense += amount

    net_result = total_income - total_expense  

    return {
        "year": year,
        "incomes": incomes,
        "expenses": expenses,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_result": net_result,
        "is_profit": net_result >= 0,
    }
