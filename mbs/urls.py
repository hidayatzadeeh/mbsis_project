from django.contrib import admin
from django.urls import path
from core.views import (
    AccountListView,
    JournalEntryListView,
    mizan,
    balance_sheet_view,
    income_statement_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', AccountListView.as_view(), name='account_list'),
    path('journal/', JournalEntryListView.as_view(), name='journal_list'),
    path('mizan/', mizan, name='mizan'),
    path('balance/<int:year>/', balance_sheet_view, name='balance_sheet'),
    path('gelir/<int:year>/', income_statement_view, name='income_statement'),
]
