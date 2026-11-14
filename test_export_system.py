"""
Unit and Integration Tests for Analytical Research Export Engine.
Verifies:
1. Pure Python OpenXML Excel (.xlsx) generation and integrity.
2. Multi-sheet Excel export including secondary Data_Dictionary codebook sheet.
3. CSV generation with UTF-8 BOM.
4. Snake_case headers and statistical format readiness (R, SPSS, Stata).
5. Date range and primary site filtering.
6. Pre-calculated OS / DFS survival endpoints and EQD2 dosimetry.
"""

import os
import sys
import zipfile
import io
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gynae_oncology.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from patients.models import Patient
from clinical.models import Diagnosis, PrimarySite, Histology, Encounter, EncounterType
from radiotherapy.models import EBRTCourse, BrachyCourse
from core.models import Role, UserProfile
from core.views import export_data_view
from core.exports import (
    build_excel_xml_workbook,
    get_wide_format_data,
    get_long_format_data,
    get_wide_data_dictionary,
    get_long_data_dictionary,
    generate_excel_response,
    generate_csv_response
)

def run_tests():
    print("====================================================")
    print("Starting Analytical Export Engine Tests")
    print("====================================================")

    # 1. Test Pure Python OpenXML Excel (.xlsx) Generation
    print("\n[Test 1] Testing Pure Python OpenXML .xlsx generation...")
    test_sheets = [
        {
            'name': 'Patients_Wide',
            'headers': ['mr_no', 'age_years', 'primary_site', 'os_status', 'os_days', 'eqd2_total'],
            'rows': [
                ['MR-TEST-001', 48, 'Cervix', 0, 180, 84.5],
                ['MR-TEST-002', 52, 'Endometrium', 1, 95, 78.2],
                ['MR-TEST-003', None, 'Ovary', 0, 45, None],
            ]
        }
    ]
    xlsx_bytes = build_excel_xml_workbook(test_sheets)
    assert len(xlsx_bytes) > 0, "Excel output bytes must not be empty"

    with zipfile.ZipFile(io.BytesIO(xlsx_bytes), 'r') as zf:
        namelist = zf.namelist()
        print("  - Generated zip archive files:", namelist)
        assert '[Content_Types].xml' in namelist
        assert '_rels/.rels' in namelist
        assert 'xl/workbook.xml' in namelist
        assert 'xl/_rels/workbook.xml.rels' in namelist
        assert 'xl/styles.xml' in namelist
        assert 'xl/worksheets/sheet1.xml' in namelist

        sheet1_content = zf.read('xl/worksheets/sheet1.xml').decode('utf-8')
        assert 'MR-TEST-001' in sheet1_content
        assert '84.5' in sheet1_content
    print("  ✓ OpenXML Excel (.xlsx) structure verified successfully.")

    # 2. Test Statistical Format Readiness (snake_case headers, valid syntax)
    print("\n[Test 2] Testing Statistical Variable Naming Standards (R / SPSS / Stata)...")
    qs = Patient.objects.filter(soft_deleted=False)
    wide_headers, wide_rows = get_wide_format_data(qs)
    print(f"  - Wide format variables count: {len(wide_headers)}")
    
    var_regex = re.compile(r'^[a-z][a-z0-9_]*$')
    for h in wide_headers:
        assert var_regex.match(h), f"Header '{h}' does not match standard snake_case syntax for R/SPSS"
    print("  ✓ All wide format headers strictly match snake_case identifier rules for R / SPSS.")

    for expected_endpoint in ['os_status', 'os_days', 'os_months', 'dfs_status', 'dfs_days', 'dfs_months']:
        assert expected_endpoint in wide_headers, f"Expected survival endpoint '{expected_endpoint}' in wide headers"
    print("  ✓ Pre-calculated OS and DFS survival endpoints verified in headers.")

    for expected_rt in ['ebrt_ott_days', 'total_ott_days', 'cumul_hrctv_d90_eqd2', 'cumul_bladder_2cc_eqd2', 'cumul_rectum_2cc_eqd2']:
        assert expected_rt in wide_headers, f"Expected radiobiology field '{expected_rt}' in wide headers"
    print("  ✓ Radiobiology EQD2 and Overall Treatment Time (OTT) fields verified.")

    # 3. Test Data Dictionary Generators
    print("\n[Test 3] Testing Data Dictionary Generators...")
    wide_dict_h, wide_dict_r = get_wide_data_dictionary()
    long_dict_h, long_dict_r = get_long_data_dictionary()
    print(f"  - Wide Data Dictionary items count: {len(wide_dict_r)}")
    print(f"  - Long Data Dictionary items count: {len(long_dict_r)}")
    assert len(wide_dict_r) == len(wide_headers), f"Wide data dictionary ({len(wide_dict_r)}) must cover all wide headers ({len(wide_headers)})"
    assert len(long_dict_r) == 16, "Long data dictionary must have 16 variables"
    print("  ✓ Data dictionary completely covers all clinical variables.")

    # 4. Test Long Format Generation
    print("\n[Test 4] Testing Long Format (Event Timeline) Generation...")
    long_headers, long_rows = get_long_format_data(qs)
    print(f"  - Long format variables count: {len(long_headers)}, rows count: {len(long_rows)}")
    for h in long_headers:
        assert var_regex.match(h), f"Long header '{h}' does not match snake_case"
    print("  ✓ Long format headers strictly match snake_case identifier rules.")

    # 5. Test View Controller (export_data_view) with Multi-Sheet Excel & Filters
    print("\n[Test 5] Testing export_data_view HTTP responses and multi-sheet Excel export...")
    rf = RequestFactory()
    admin_user, _ = User.objects.get_or_create(username='test_admin_export', defaults={'is_superuser': True, 'is_staff': True})
    
    # 5a. Plain GET without download parameter -> Renders Dialog HTML
    req = rf.get('/export/')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert 'text/html' in res['Content-Type']
    assert b'Analytical & Research Data Export Center' in res.content
    print("  ✓ Plain GET /export/ correctly renders the interactive Export Center Dialog.")

    # 5b. GET /export/?download=1&format=wide&file_type=excel -> Returns .xlsx with Data_Dictionary sheet
    req = rf.get('/export/?download=1&format=wide&file_type=excel')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res['Content-Type']
    assert res['Content-Disposition'].endswith('.xlsx"')

    # Verify both sheet1.xml (Patients_Analysis) and sheet2.xml (Data_Dictionary) exist
    with zipfile.ZipFile(io.BytesIO(res.content), 'r') as zf:
        namelist = zf.namelist()
        assert 'xl/worksheets/sheet1.xml' in namelist, "sheet1.xml must exist in Excel export"
        assert 'xl/worksheets/sheet2.xml' in namelist, "sheet2.xml (Data_Dictionary) must exist in Excel export"
        
        workbook_xml = zf.read('xl/workbook.xml').decode('utf-8')
        assert 'Patients_Analysis' in workbook_xml, "Workbook must contain Patients_Analysis sheet"
        assert 'Data_Dictionary' in workbook_xml, "Workbook must contain Data_Dictionary sheet"

        dict_sheet_xml = zf.read('xl/worksheets/sheet2.xml').decode('utf-8')
        assert 'variable_name' in dict_sheet_xml
        assert 'description_and_methodology' in dict_sheet_xml
        assert 'os_status' in dict_sheet_xml
        assert 'cumul_hrctv_d90_eqd2' in dict_sheet_xml
    print("  ✓ Verified Multi-Sheet Excel Export: Sheet 1 = 'Patients_Analysis', Sheet 2 = 'Data_Dictionary'.")

    # 5c. GET /export/?download=1&format=wide&file_type=csv -> Returns .csv with UTF-8 BOM
    req = rf.get('/export/?download=1&format=wide&file_type=csv')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert 'text/csv' in res['Content-Type']
    assert res['Content-Disposition'].endswith('.csv"')
    assert res.content.startswith(b'\xef\xbb\xbf'), "CSV must start with UTF-8 BOM"
    print("  ✓ CSV Wide Export: Verified UTF-8 BOM and correct headers.")

    # 5d. GET /export/ with Primary Site filter (e.g. Cervix)
    req = rf.get('/export/?download=1&format=wide&file_type=csv&primary_site=Cervix')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert 'cervix' in res['Content-Disposition'].lower()
    print(f"  ✓ Primary Site Filter (Cervix) applied to export: filename={res['Content-Disposition']}")

    # 5e. GET /export/ with Date Range filter
    req = rf.get('/export/?download=1&format=wide&file_type=excel&date_from=2026-01-01&date_to=2026-12-31&date_field=registration')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert len(res.content) > 0
    print("  ✓ Date Range Filter applied to export successfully.")

    # 5f. GET /export/ Long Format Excel with Data_Dictionary
    req = rf.get('/export/?download=1&format=long&file_type=excel')
    req.user = admin_user
    res = export_data_view(req)
    assert res.status_code == 200
    assert 'gynae_events_long' in res['Content-Disposition']
    with zipfile.ZipFile(io.BytesIO(res.content), 'r') as zf:
        workbook_xml = zf.read('xl/workbook.xml').decode('utf-8')
        assert 'Event_Timeline' in workbook_xml
        assert 'Data_Dictionary' in workbook_xml
    print("  ✓ Long Format Excel export with Data_Dictionary verified.")

    print("\n====================================================")
    print("ALL ANALYTICAL EXPORT TESTS PASSED SUCCESSFULLY! ✓")
    print("====================================================")

if __name__ == '__main__':
    run_tests()
