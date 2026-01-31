from django.db import migrations

def forwards(apps, schema_editor):
    JournalLine = apps.get_model("core", "JournalLine")
    current_entry = None
    counter = 0
    # стабильно сортируем по entry_id, потом по id строки
    for jl in JournalLine.objects.order_by("entry_id", "id").only("id", "entry_id"):
        if jl.entry_id != current_entry:
            current_entry = jl.entry_id
            counter = 1
        else:
            counter += 1
        JournalLine.objects.filter(id=jl.id).update(line_no=counter)

def backwards(apps, schema_editor):
    # откат не обязателен
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_accountbalance_fiscalperiod_alter_account_options_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
