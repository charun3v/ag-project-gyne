# Generated manually with safe database preservation and seeding

from django.db import migrations, models
import django.db.models.deletion


def seed_applicator_rules(apps, schema_editor):
    ApplicatorType = apps.get_model('radiotherapy', 'ApplicatorType')
    ApplicatorMeasurementDefinition = apps.get_model('radiotherapy', 'ApplicatorMeasurementDefinition')
    ApplicatorFieldRule = apps.get_model('radiotherapy', 'ApplicatorFieldRule')
    from django.db import connection

    # 1. Copy existing Ovoid_Size_mm to Legacy_Ovoid_Size_mm safely
    with connection.cursor() as cursor:
        try:
            cursor.execute("UPDATE tblBrachySessions SET Legacy_Ovoid_Size_mm = Ovoid_Size_mm WHERE Ovoid_Size_mm IS NOT NULL AND Legacy_Ovoid_Size_mm IS NULL;")
        except Exception as e:
            pass

    # 2. Measurement Definitions
    defs_data = [
        {
            'code': 'tandem_length_cm',
            'label': 'Tandem length',
            'data_type': 'decimal',
            'unit': 'cm',
            'minimum_value': 0.1,
            'maximum_value': 15.0,
            'display_order': 1,
            'active': True,
        },
        {
            'code': 'ovoid_diameter_mm',
            'label': 'Ovoid diameter',
            'data_type': 'decimal',
            'unit': 'mm',
            'minimum_value': 1.0,
            'maximum_value': 50.0,
            'display_order': 2,
            'active': True,
        },
        {
            'code': 'ovoid_length_mm',
            'label': 'Ovoid length',
            'data_type': 'decimal',
            'unit': 'mm',
            'minimum_value': 1.0,
            'maximum_value': 60.0,
            'display_order': 3,
            'active': True,
        },
        {
            'code': 'ring_diameter_mm',
            'label': 'Ring diameter',
            'data_type': 'decimal',
            'unit': 'mm',
            'minimum_value': 1.0,
            'maximum_value': 60.0,
            'display_order': 4,
            'active': True,
        },
        {
            'code': 'needle_count',
            'label': 'Number of needles',
            'data_type': 'integer',
            'unit': '',
            'minimum_value': 1,
            'maximum_value': 100,
            'display_order': 5,
            'active': True,
        },
    ]

    meas_defs = {}
    for item in defs_data:
        mdef, _ = ApplicatorMeasurementDefinition.objects.get_or_create(
            code=item['code'],
            defaults=item
        )
        meas_defs[item['code']] = mdef

    # 3. Ensure Default Applicator Types exist
    default_applicator_types = [
        ('Tandem only', 1),
        ('Tandem and Ovoids', 2),
        ('Ovoids only', 3),
        ('Tandem and Ring', 4),
        ('Tandem, Ring and Needles', 5),
        ('Tandem and Needles', 6),
        ('Interstitial needles only', 7),
    ]

    for app_name, order in default_applicator_types:
        app_obj = ApplicatorType.objects.filter(name=app_name).first()
        if not app_obj:
            from django.db.models import Max
            max_id = ApplicatorType.objects.aggregate(m=Max('id'))['m'] or 0
            ApplicatorType.objects.create(
                id=max_id + 1,
                name=app_name,
                active=True,
                display_order=order
            )

    # 4. Default Mappings
    mappings = {
        'Tandem only': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (False, False),
            'needle_count': (False, False),
        },
        'Tandem and Ovoids': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (True, True),
            'ovoid_length_mm': (True, True),
            'ring_diameter_mm': (False, False),
            'needle_count': (False, False),
        },
        'Ovoids only': {
            'tandem_length_cm': (False, False),
            'ovoid_diameter_mm': (True, True),
            'ovoid_length_mm': (True, True),
            'ring_diameter_mm': (False, False),
            'needle_count': (False, False),
        },
        'Tandem and Ring': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (True, True),
            'needle_count': (False, False),
        },
        'Tandem, Ring and Needles': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (True, True),
            'needle_count': (True, True),
        },
        'Tandem and Ring with Needles': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (True, True),
            'needle_count': (True, True),
        },
        'Tandem and Needles': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (False, False),
            'needle_count': (True, True),
        },
        'Tandem and Ovoids with Needles': {
            'tandem_length_cm': (True, True),
            'ovoid_diameter_mm': (True, True),
            'ovoid_length_mm': (True, True),
            'ring_diameter_mm': (False, False),
            'needle_count': (True, True),
        },
        'Interstitial needles only': {
            'tandem_length_cm': (False, False),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (False, False),
            'needle_count': (True, True),
        },
        'Interstitial only (Template/Needles)': {
            'tandem_length_cm': (False, False),
            'ovoid_diameter_mm': (False, False),
            'ovoid_length_mm': (False, False),
            'ring_diameter_mm': (False, False),
            'needle_count': (True, True),
        },
    }

    for app_name, field_dict in mappings.items():
        app_obj = ApplicatorType.objects.filter(name=app_name).first()
        if not app_obj:
            continue
        order_idx = 1
        for code, (is_enabled, is_required) in field_dict.items():
            mdef = meas_defs.get(code)
            if not mdef:
                continue
            rule = ApplicatorFieldRule.objects.filter(
                applicator_type=app_obj,
                measurement_definition=mdef
            ).first()
            if not rule:
                ApplicatorFieldRule.objects.create(
                    applicator_type=app_obj,
                    measurement_definition=mdef,
                    enabled=is_enabled,
                    required=is_required,
                    display_order=order_idx,
                )
            order_idx += 1


class Migration(migrations.Migration):

    dependencies = [
        ('radiotherapy', '0002_brachycourse_approval_locked_and_more'),
    ]

    operations = [
        # Rename BrachyApplicator to ApplicatorType in Django state (db table is already sbtblBrachyApplicator)
        migrations.RenameModel(
            old_name='BrachyApplicator',
            new_name='ApplicatorType',
        ),
        migrations.RenameField(
            model_name='applicatortype',
            old_name='applicator_id',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='applicatortype',
            old_name='applicator_name',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='applicatortype',
            old_name='is_active',
            new_name='active',
        ),

        # Create measurement definition catalog
        migrations.CreateModel(
            name='ApplicatorMeasurementDefinition',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(help_text='e.g. tandem_length_cm, ovoid_diameter_mm', max_length=50, unique=True)),
                ('label', models.CharField(help_text='Clinical display label', max_length=100)),
                ('data_type', models.CharField(choices=[('decimal', 'Decimal (Floating Point)'), ('integer', 'Whole Integer')], default='decimal', max_length=20)),
                ('unit', models.CharField(blank=True, default='', help_text='Unit string, e.g. cm, mm', max_length=20)),
                ('minimum_value', models.FloatField(blank=True, help_text='Default clinical minimum value', null=True)),
                ('maximum_value', models.FloatField(blank=True, help_text='Default clinical maximum value', null=True)),
                ('active', models.BooleanField(default=True)),
                ('display_order', models.IntegerField(default=1)),
            ],
            options={
                'db_table': 'sbtblApplicatorMeasurementDefinition',
                'ordering': ['display_order', 'id'],
            },
        ),

        # Create field rules table
        migrations.CreateModel(
            name='ApplicatorFieldRule',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('enabled', models.BooleanField(default=True)),
                ('required', models.BooleanField(default=True)),
                ('display_order', models.IntegerField(default=1)),
                ('min_value_override', models.FloatField(blank=True, help_text='Optional override for minimum value', null=True)),
                ('max_value_override', models.FloatField(blank=True, help_text='Optional override for maximum value', null=True)),
                ('applicator_type', models.ForeignKey(db_column='ApplicatorTypeID', on_delete=django.db.models.deletion.CASCADE, related_name='field_rules', to='radiotherapy.applicatortype')),
                ('measurement_definition', models.ForeignKey(db_column='MeasurementDefID', on_delete=django.db.models.deletion.CASCADE, related_name='applicator_rules', to='radiotherapy.applicatormeasurementdefinition')),
            ],
            options={
                'db_table': 'sbtblApplicatorFieldRule',
                'ordering': ['display_order', 'id'],
                'unique_together': {('applicator_type', 'measurement_definition')},
            },
        ),

        # State and database migration for BrachySession fields
        migrations.AddField(
            model_name='brachysession',
            name='approval_locked',
            field=models.BooleanField(db_column='Approval_Locked', default=False),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='approved_by',
            field=models.CharField(blank=True, db_column='Approved_By', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='approved_on',
            field=models.DateTimeField(blank=True, db_column='Approved_On', null=True),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='approved_rules_snapshot',
            field=models.TextField(blank=True, db_column='Approved_Rules_Snapshot', null=True),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='is_approved',
            field=models.BooleanField(db_column='Is_Approved', default=False),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='legacy_ovoid_size_mm',
            field=models.FloatField(blank=True, db_column='Legacy_Ovoid_Size_mm', help_text='Preserved legacy ovoid size before separation', null=True),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='ovoid_diameter_mm',
            field=models.FloatField(blank=True, db_column='Ovoid_Diameter_mm', null=True),
        ),
        migrations.AddField(
            model_name='brachysession',
            name='ovoid_length_mm',
            field=models.FloatField(blank=True, db_column='Ovoid_Length_mm', null=True),
        ),

        # Update needle_count and ovoid_size_mm in state without altering existing Number_Of_Needles column
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='brachysession',
                    name='number_of_needles',
                ),
                migrations.RemoveField(
                    model_name='brachysession',
                    name='ovoid_size_mm',
                ),
                migrations.AddField(
                    model_name='brachysession',
                    name='needle_count',
                    field=models.IntegerField(blank=True, db_column='Number_Of_Needles', null=True),
                ),
                migrations.AlterField(
                    model_name='brachysession',
                    name='applicator',
                    field=models.ForeignKey(db_column='BrachyApplicatorID', on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='radiotherapy.applicatortype'),
                ),
            ],
            database_operations=[]
        ),

        # Seed data and copy legacy ovoid measurements
        migrations.RunPython(seed_applicator_rules, reverse_code=migrations.RunPython.noop),
    ]
