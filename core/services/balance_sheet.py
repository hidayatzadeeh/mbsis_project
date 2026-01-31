from datetime import date
from decimal import Decimal

from django.db.models import Sum

from core.models import Account


def _account_balance_until(acc, year):
    """
    Считает сальдо счета acc по всем проводкам
    с датой <= 31.12.year.
    Знак считается так же, как в Account.get_balance:
      - для ASSET и EXPENSE:  debit - credit
      - для остальных (LIABILITY, EQUITY, INCOME): credit - debit
    """
    cutoff = date(year, 12, 31)

    qs = acc.journalline_set.filter(entry__date__lte=cutoff)

    totals = qs.aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )
    total_debit = totals["total_debit"] or Decimal("0.00")
    total_credit = totals["total_credit"] or Decimal("0.00")

    if acc.type in (Account.ASSET, Account.EXPENSE):
        return total_debit - total_credit
    else:
        return total_credit - total_debit


def generate_balance(year):
    """
    Генерирует структуру бухгалтерского баланса на 31.12.<year>.

    В баланс включаются:
      - ASSET  → Varlıklar
      - LIABILITY → Borçlar
      - EQUITY → Öz Kaynaklar
    Доходы и расходы (INCOME, EXPENSE) в баланс не выводятся строками,
    но их чистый результат (gelir - gider) отражается
    отдельной строкой в Öz Kaynaklar: "Dönem Net Kâr/Zararı".
    """

    assets = []
    liabilities = []
    equities = []

    income_total = Decimal("0.00")
    expense_total = Decimal("0.00")

    for acc in Account.objects.all().order_by("code"):
        bal = _account_balance_until(acc, year)
        if bal == 0:
            continue

        if acc.type == Account.ASSET:
            assets.append({
                "code": acc.code,
                "name": acc.name,
                "balance": bal,
            })

        elif acc.type == Account.LIABILITY:
            liabilities.append({
                "code": acc.code,
                "name": acc.name,
                "balance": bal,
            })

        elif acc.type == Account.EQUITY:
            equities.append({
                "code": acc.code,
                "name": acc.name,
                "balance": bal,
            })

        elif acc.type == Account.INCOME:
            income_total += bal

        elif acc.type == Account.EXPENSE:
            expense_total += bal

    net_result = income_total - expense_total

    if net_result != 0:
        equities.append({
            "code": "DNET",
            "name": "Dönem Net Kâr/Zararı",
            "balance": net_result,
        })

    total_assets = sum(a["balance"] for a in assets) if assets else Decimal("0.00")
    total_liabilities = sum(l["balance"] for l in liabilities) if liabilities else Decimal("0.00")
    total_equity = sum(e["balance"] for e in equities) if equities else Decimal("0.00")

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equities": equities,
        "total_assets": total_assets,
        "total_liabilities_equity": total_liabilities + total_equity,
        "match": (total_assets == total_liabilities + total_equity),
        "net_result": net_result,
    }
