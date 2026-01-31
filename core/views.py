from datetime import date

from django.http import HttpResponse
from django.views.generic import ListView
from django.shortcuts import render
from django.db.models import Sum
from django.utils.dateparse import parse_date

from core.services.income_statement import generate_income_statement
from core.services.balance_sheet import generate_balance
from .models import Account, JournalEntry, JournalLine


class AccountListView(ListView):
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"


class JournalEntryListView(ListView):
    """
    Yevmiye listesi + tarih filtresi (?start=YYYY-MM-DD&end=YYYY-MM-DD)
    """
    model = JournalEntry
    template_name = "core/journal_list.html"
    context_object_name = "entries"

    def get_queryset(self):
        qs = JournalEntry.objects.all().order_by("-date", "-id")

        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")

        start = parse_date(start_str) if start_str else None
        end = parse_date(end_str) if end_str else None

        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        start_str = self.request.GET.get("start", "")
        end_str = self.request.GET.get("end", "")

        entries_qs = ctx["entries"]
        entries = list(entries_qs)
        ctx["entries"] = entries

        entries_count = len(entries)
        sum_debit = 0
        sum_credit = 0
        for e in entries:
            sum_debit += e.total_debit
            sum_credit += e.total_credit

        ctx.update(
            {
                "start": start_str,
                "end": end_str,
                "entries_count": entries_count,
                "sum_debit": sum_debit,
                "sum_credit": sum_credit,
            }
        )
        return ctx


def ping(request):
    return HttpResponse("PING OK")


def mizan(request):
    """
    Mizan görünümü + tarih filtresi (?start=YYYY-MM-DD&end=YYYY-MM-DD)
    """
    today = date.today()
    first_day = today.replace(day=1)

    start_str = request.GET.get("start") or first_day.isoformat()
    end_str = request.GET.get("end") or today.isoformat()

    lines = JournalLine.objects.select_related("entry", "account")

    try:
        if start_str:
            d_start = date.fromisoformat(start_str)
            lines = lines.filter(entry__date__gte=d_start)
        if end_str:
            d_end = date.fromisoformat(end_str)
            lines = lines.filter(entry__date__lte=d_end)
    except ValueError:
        pass

    qs = (
        lines
        .values("account__code", "account__name")
        .annotate(
            debit_sum=Sum("debit"),
            credit_sum=Sum("credit"),
        )
        .order_by("account__code")
    )

    rows = []
    total_debit = 0
    total_credit = 0

    for r in qs:
        d = r["debit_sum"] or 0
        c = r["credit_sum"] or 0
        rows.append(
            {
                "code": r["account__code"],
                "name": r["account__name"],
                "debit": d,
                "credit": c,
                "balance": d - c,
            }
        )
        total_debit += d
        total_credit += c

    total_balance = total_debit - total_credit

    context = {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "total_balance": total_balance,
        "start": start_str,
        "end": end_str,
        "rows_count": len(rows),       
        "lines_count": lines.count(),  
    }
    return render(request, "core/mizan.html", context)


def balance_sheet_view(request, year: int):
    """
    Bilanço görünümü.
    Örnek URL: /balance/2026/
    """
    data = generate_balance(year)
    context = {
        "year": year,
        "data": data,
    }
    return render(request, "core/balance_sheet.html", context)


def income_statement_view(request, year: int):
    """
    Gelir tablosu görünümü.
    Örnek URL: /gelir/2026/
    """
    data = generate_income_statement(year)
    context = {
        "year": year,
        "data": data,
    }
    return render(request, "core/income_statement.html", context)
