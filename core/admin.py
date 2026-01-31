from django.contrib import admin
from .models import Account

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

from .models import JournalEntry, JournalLine

class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2  
    fields = ("account", "debit", "credit")

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "description")
    list_filter = ("date",)
    search_fields = ("description",)
    inlines = [JournalLineInline]
