from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Sum


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class FiscalPeriod(models.Model):
    year = models.IntegerField(db_index=True)
    month = models.IntegerField(db_index=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        unique_together = ("year", "month")
        verbose_name = "Muhasebe Dönemi"
        verbose_name_plural = "Muhasebe Dönemleri"
        ordering = ["-year", "-month"]

    def __str__(self):
        status = "Kapalı" if self.is_closed else "Açık"
        return f"{self.year}-{self.month:02d} ({status})"


class Account(models.Model):
    ASSET = "AS"
    LIABILITY = "LI"
    EQUITY = "EQ"
    INCOME = "IN"
    EXPENSE = "EX"

    TYPE_CHOICES = [
        (ASSET, "Varlık"),
        (LIABILITY, "Yükümlülük"),
        (EQUITY, "Öz Kaynak"),
        (INCOME, "Gelir"),
        (EXPENSE, "Gider"),
    ]

    code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        validators=[RegexValidator(r"^\d{3,6}$", "Kod 3-6 rakam olmalı")],
        help_text="Örn: 100, 102, 320, 500",
    )
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, default=ASSET)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        help_text="İsteğe bağlı: üst hesap",
    )

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["type"]),
        ]
        verbose_name = "Hesap"
        verbose_name_plural = "Hesaplar"

    def __str__(self):
        return f"{self.code} — {self.name}"

    def get_balance(self, year=None, month=None):
        
        qs = self.journalline_set.all()

        if year is not None:
            qs = qs.filter(entry__date__year=year)
        if month is not None:
            qs = qs.filter(entry__date__month=month)

        totals = qs.aggregate(
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
        )

        total_debit = totals["total_debit"] or Decimal("0.00")
        total_credit = totals["total_credit"] or Decimal("0.00")

        if self.type in (self.ASSET, self.EXPENSE):
            
            return total_debit - total_credit
        else:
            
            return total_credit - total_debit



class JournalEntry(TimeStampedModel):
    DRAFT = "D"
    POSTED = "P"

    STATUS_CHOICES = [
        (DRAFT, "Taslak"),
        (POSTED, "Onaylı"),
    ]

    date = models.DateField(db_index=True)
    description = models.CharField(max_length=200)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=DRAFT)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Yevmiye Kaydı"
        verbose_name_plural = "Yevmiye Kayıtları"
        indexes = [
            models.Index(fields=["date", "status"]),
        ]

    @property
    def total_debit(self):
        return sum(line.debit for line in self.lines.all())

    @property
    def total_credit(self):
        return sum(line.credit for line in self.lines.all())

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit

    @property
    def balance(self):
        return self.total_debit - self.total_credit

    def clean(self):
        if self.date:
            per = FiscalPeriod.objects.filter(year=self.date.year, month=self.date.month).first()
            if per and per.is_closed:
                raise ValidationError("Bu dönem kapalı (muhasebe).")

        if not self.pk:
            return

        if self.status == JournalEntry.POSTED and self.total_debit != self.total_credit:
            raise ValidationError("Kayıt dengede değil: toplam borç ve alacak eşit olmalı.")

    def __str__(self):
        return f"{self.date} — {self.description}"


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, db_index=True)

    line_no = models.PositiveIntegerField(default=1)

    debit = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    credit = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["entry_id", "line_no", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(~models.Q(debit__gt=0) | models.Q(credit=0)),
                name="chk_no_both_positive_debit_credit",
            ),
            models.CheckConstraint(
                condition=(~models.Q(credit__gt=0) | models.Q(debit=0)),
                name="chk_no_both_positive_credit_debit",
            ),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0) | models.Q(credit__gt=0)),
                name="chk_must_have_amount",
            ),
        ]
        indexes = [
            models.Index(fields=["entry", "account"]),
            models.Index(fields=["account"]),
        ]
        verbose_name = "Yevmiye Satırı"
        verbose_name_plural = "Yevmiye Satırları"

    def __str__(self):
        return f"[{self.entry_id}] {self.line_no}. {self.account.code}: {self.debit} / {self.credit}"


class AccountBalance(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, db_index=True)
    year = models.IntegerField(db_index=True)
    month = models.IntegerField(db_index=True)
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        unique_together = ("account", "year", "month")
        ordering = ["-year", "-month", "account__code"]
        verbose_name = "Hesap Bakiye (Aylık)"
        verbose_name_plural = "Hesap Bakiyeleri (Aylık)"

    @property
    def balance(self):
        return self.debit - self.credit

    def __str__(self):
        return f"{self.year}-{self.month:02d} {self.account.code} ({self.debit}/{self.credit})"
