"""
Analytical Research Export Engine for Gynae Oncology Database.
Generates R / SPSS / Stata / SAS ready exports:
- Formats: Excel Workbook (.xlsx via native OpenXML) and CSV (UTF-8 BOM).
- Scopes: Wide-Format (Patient-level analytical record with survival endpoints)
          and Long-Format (Event-level timeline record for longitudinal analysis).
- Standardized syntax: snake_case column names, ISO-8601 dates (YYYY-MM-DD),
  pre-computed survival times (OS/DFS status and days/months), radiobiology EQD2,
  Overall Treatment Time (OTT), and treatment compliance.
"""

import io
import csv
import zipfile
from datetime import date
from xml.sax.saxutils import escape
from django.http import HttpResponse


def col_name(n):
    """Convert 1-based column index to Excel column name (A, B, ..., Z, AA, AB, ...)."""
    name = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def build_excel_xml_workbook(sheets_data):
    """
    Builds a native Microsoft Excel (.xlsx) file in memory using pure Python.
    sheets_data: list of dicts:
      [
        {
          'name': 'Patients_Wide_Format',
          'headers': ['mr_no', 'age_years', ...],
          'rows': [['PT001', 45, ...], ...]
        }
      ]
    Returns bytes of the .xlsx zip archive.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. [Content_Types].xml
        content_types = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '  <Default Extension="xml" ContentType="application/xml"/>',
            '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        ]
        for i in range(1, len(sheets_data) + 1):
            content_types.append(f'  <Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        content_types.append('</Types>')
        zf.writestr('[Content_Types].xml', "\n".join(content_types))

        # 2. _rels/.rels
        zf.writestr('_rels/.rels', '\n'.join([
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>',
            '</Relationships>'
        ]))

        # 3. xl/_rels/workbook.xml.rels
        wb_rels = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        ]
        for i in range(1, len(sheets_data) + 1):
            wb_rels.append(f'  <Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        style_rid = len(sheets_data) + 1
        wb_rels.append(f'  <Relationship Id="rId{style_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        wb_rels.append('</Relationships>')
        zf.writestr('xl/_rels/workbook.xml.rels', "\n".join(wb_rels))

        # 4. xl/workbook.xml
        wb_xml = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
            '  <sheets>'
        ]
        for i, s in enumerate(sheets_data, start=1):
            sheet_title = escape(s.get('name', f'Sheet{i}')[:31])
            wb_xml.append(f'    <sheet name="{sheet_title}" sheetId="{i}" r:id="rId{i}"/>')
        wb_xml.append('  </sheets>')
        wb_xml.append('</workbook>')
        zf.writestr('xl/workbook.xml', "\n".join(wb_xml))

        # 5. xl/styles.xml
        # style 0 = normal Segoe UI 10pt
        # style 1 = header bold Segoe UI 10pt with Navy Blue background (#003366) and white text
        # style 2 = data row with light border
        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10"/><name val="Segoe UI"/></font>
    <font><b/><sz val="10"/><name val="Segoe UI"/><color rgb="FFFFFFFF"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF003366"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/></border>
    <border>
      <left style="thin"><color rgb="FFD0D0D0"/></left>
      <right style="thin"><color rgb="FFD0D0D0"/></right>
      <top style="thin"><color rgb="FFD0D0D0"/></top>
      <bottom style="thin"><color rgb="FFD0D0D0"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
  </cellXfs>
</styleSheet>"""
        zf.writestr('xl/styles.xml', styles_xml)

        # 6. xl/worksheets/sheet{i}.xml
        for idx, s in enumerate(sheets_data, start=1):
            headers = s.get('headers', [])
            rows = s.get('rows', [])

            ws_parts = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                '  <sheetData>'
            ]

            # Header Row (Row 1)
            if headers:
                ws_parts.append('    <row r="1">')
                for c_idx, h in enumerate(headers, start=1):
                    c_ref = f"{col_name(c_idx)}1"
                    escaped_h = escape(str(h) if h is not None else '')
                    ws_parts.append(f'      <c r="{c_ref}" t="inlineStr" s="1"><is><t>{escaped_h}</t></is></c>')
                ws_parts.append('    </row>')

            # Data Rows
            for r_idx, row in enumerate(rows, start=2):
                ws_parts.append(f'    <row r="{r_idx}">')
                for c_idx, val in enumerate(row, start=1):
                    c_ref = f"{col_name(c_idx)}{r_idx}"
                    if val is None or val == '':
                        continue
                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        ws_parts.append(f'      <c r="{c_ref}" s="2"><v>{val}</v></c>')
                    elif isinstance(val, bool):
                        bool_val = '1' if val else '0'
                        ws_parts.append(f'      <c r="{c_ref}" t="b" s="2"><v>{bool_val}</v></c>')
                    else:
                        escaped_val = escape(str(val))
                        ws_parts.append(f'      <c r="{c_ref}" t="inlineStr" s="2"><is><t>{escaped_val}</t></is></c>')
                ws_parts.append('    </row>')

            ws_parts.append('  </sheetData>')
            ws_parts.append('</worksheet>')
            zf.writestr(f'xl/worksheets/sheet{idx}.xml', "\n".join(ws_parts))

    buf.seek(0)
    return buf.getvalue()


def generate_excel_response(sheets_data, filename="gynae_oncology_export.xlsx"):
    """Returns an HttpResponse attachment with native Excel .xlsx content."""
    content = build_excel_xml_workbook(sheets_data)
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def generate_csv_response(headers, rows, filename="gynae_oncology_export.csv"):
    """Returns an HttpResponse attachment with UTF-8 BOM encoded CSV content for R/SPSS."""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # Write UTF-8 BOM so Excel & statistical tools auto-detect encoding correctly
    response.write('\ufeff')
    writer = csv.writer(response)
    if headers:
        writer.writerow(headers)
    for r in rows:
        # Convert None to empty string
        writer.writerow([("" if v is None else v) for v in r])
    return response


def calculate_eqd2_simple(dose, fx, alpha_beta):
    """Calculates Linear-Quadratic Equivalent Dose in 2 Gy fractions (EQD2)."""
    if not dose or not fx or fx <= 0 or not alpha_beta or alpha_beta <= 0:
        return 0.0
    d = float(dose) / float(fx)
    return float(dose) * (d + float(alpha_beta)) / (2.0 + float(alpha_beta))


def get_wide_format_data(patients_qs):
    """
    Generates standardized Wide-Format Patient-Level Analytical Records.
    Variables use snake_case identifiers, ISO dates, and pre-computed survival endpoints.
    """
    headers = [
        # 1. Demographics & Identification
        'mr_no', 'patient_name', 'age_years', 'sex', 'date_of_birth', 'registration_date',
        'primary_consultant', 'state', 'district',
        
        # 2. Oncology Diagnosis & Staging
        'date_of_diagnosis', 'primary_site', 'histology', 'grade',
        'figo_stage', 'figo_stage_group', 't_stage', 'n_stage', 'm_stage', 'laterality',
        
        # 3. Baseline Examination & Anthropometrics
        'baseline_ecog_score', 'baseline_height_cm', 'baseline_weight_kg', 'baseline_bmi',
        'tumour_size_cc_cm', 'tumour_size_ap_cm', 'tumour_size_ml_cm',
        'parametrial_invasion', 'parametrial_left', 'parametrial_right',
        'rectal_invasion', 'bladder_invasion',
        
        # 4. Neoadjuvant Chemotherapy (NACT)
        'nact_given', 'nact_regimen', 'nact_planned_cycles', 'nact_received_cycles',
        'nact_response', 'nact_treatment_status', 'nact_reason', 'nact_post_staging', 'nact_is_approved',
        
        # 5. External Beam Radiotherapy (EBRT) & Concurrent Chemo
        'ebrt_given', 'ebrt_intent', 'ebrt_technique', 'ebrt_target_sites',
        'ebrt_total_dose_gy', 'ebrt_fractions', 'ebrt_start_date', 'ebrt_end_date',
        'ebrt_ott_days', 'ebrt_treatment_status', 'ebrt_reason', 'ebrt_is_approved',
        'concurrent_chemo_given', 'concurrent_chemo_regimen', 'concurrent_chemo_cycles',
        
        # 6. Brachytherapy & Radiobiology
        'brachy_given', 'brachy_source', 'brachy_dosing_system', 'brachy_prescription_dose_gy',
        'brachy_fractions_planned', 'brachy_fractions_delivered',
        'brachy_start_date', 'brachy_end_date', 'total_ott_days',
        'cumul_hrctv_d90_eqd2', 'cumul_bladder_2cc_eqd2', 'cumul_rectum_2cc_eqd2', 'cumul_sigmoid_2cc_eqd2',
        'brachy_treatment_status', 'brachy_reason', 'brachy_is_approved',
        
        # 7. Adjuvant Chemotherapy
        'adjuvant_chemo_given', 'adjuvant_regimen', 'adjuvant_planned_cycles', 'adjuvant_received_cycles',
        'adjuvant_treatment_status', 'adjuvant_reason', 'adjuvant_is_approved',
        
        # 8. Follow-Up, Recurrence & Vital Status
        'followup_visits_count', 'last_followup_date', 'current_disease_status',
        'recurrence_detected', 'date_of_recurrence', 'primary_recurrence_sites',
        'vital_status', 'death_reported', 'date_of_death', 'cause_of_death',
        
        # 9. Statistical Survival Endpoints (SPSS / R Ready)
        'os_status', 'os_days', 'os_months',
        'dfs_status', 'dfs_days', 'dfs_months'
    ]

    rows = []
    for pt in patients_qs:
        # Primary Diagnosis
        diag = pt.diagnoses.filter(is_current=True, soft_deleted=False).first() or pt.diagnoses.filter(soft_deleted=False).first()
        base_enc = pt.encounters.filter(soft_deleted=False).order_by('encounter_date', 'clinical_id').first()
        
        # NACT
        nact = pt.nact_courses.filter(soft_deleted=False).first()
        
        # EBRT & Concurrent Chemo
        ebrt = pt.ebrt_courses.filter(soft_deleted=False).first()
        conc = ebrt.concurrent_chemo_courses.filter(soft_deleted=False).first() if ebrt else None
        
        # Brachytherapy
        brachy = pt.brachy_courses.filter(soft_deleted=False).first()
        
        # Adjuvant Chemo
        adj = pt.adjuvant_courses.filter(soft_deleted=False).first()
        
        # Follow-Up Records
        fu_records = list(pt.follow_up_records.filter(soft_deleted=False).order_by('follow_up_date', 'follow_up_status_id'))
        latest_fu = fu_records[-1] if fu_records else None
        
        # --- Anthropometrics & BMI ---
        height_cm = None
        weight_kg = None
        # Look across all encounters for baseline height and weight
        for enc in pt.encounters.filter(soft_deleted=False).order_by('encounter_date', 'clinical_id'):
            if height_cm is None and enc.height and enc.height > 0:
                height_cm = enc.height
            if weight_kg is None and enc.weight and enc.weight > 0:
                weight_kg = enc.weight
            if height_cm is not None and weight_kg is not None:
                break
                
        bmi = None
        if height_cm and weight_kg and height_cm > 0:
            bmi = round(weight_kg / ((height_cm / 100.0) ** 2), 1)

        # --- FIGO Stage Grouping ---
        stage_text = diag.stage_text if diag else ''
        stage_group = ''
        if stage_text:
            st_upper = stage_text.upper().strip()
            if st_upper.startswith('IV'):
                stage_group = 'Stage IV'
            elif st_upper.startswith('III'):
                stage_group = 'Stage III'
            elif st_upper.startswith('II'):
                stage_group = 'Stage II'
            elif st_upper.startswith('I'):
                stage_group = 'Stage I'

        # --- Radiobiology EQD2 & Overall Treatment Time (OTT) ---
        ebrt_start = ebrt.ebrt_start_date if ebrt else None
        ebrt_end = ebrt.ebrt_end_date if ebrt else None
        ebrt_ott_days = None
        if ebrt_start and ebrt_end and ebrt_end >= ebrt_start:
            ebrt_ott_days = (ebrt_end - ebrt_start).days + 1

        brachy_start = None
        brachy_end = None
        if brachy and brachy.sessions.exists():
            s_dates = [s.session_date for s in brachy.sessions.all() if s.session_date]
            if s_dates:
                brachy_start = min(s_dates)
                brachy_end = max(s_dates)

        total_ott_days = None
        if ebrt_start and brachy_end and brachy_end >= ebrt_start:
            total_ott_days = (brachy_end - ebrt_start).days + 1
        elif ebrt_ott_days is not None:
            total_ott_days = ebrt_ott_days

        # Cumulative EQD2 calculation
        tumor_eqd2 = 0.0
        bladder_eqd2 = 0.0
        rectum_eqd2 = 0.0
        sigmoid_eqd2 = 0.0

        if ebrt and ebrt.total_dose_gy and ebrt.total_fractions:
            e_dose = float(ebrt.total_dose_gy)
            e_fx = int(ebrt.total_fractions)
            tumor_eqd2 += calculate_eqd2_simple(e_dose, e_fx, 10.0)
            bladder_eqd2 += calculate_eqd2_simple(e_dose, e_fx, 3.0)
            rectum_eqd2 += calculate_eqd2_simple(e_dose, e_fx, 3.0)
            sigmoid_eqd2 += calculate_eqd2_simple(e_dose, e_fx, 3.0)

        if brachy:
            for sess in brachy.sessions.all():
                for fx in sess.fractions.all():
                    if fx.hrctv_d90_gy:
                        tumor_eqd2 += calculate_eqd2_simple(fx.hrctv_d90_gy, 1, 10.0)
                    elif fx.dose_delivered_gy:
                        tumor_eqd2 += calculate_eqd2_simple(fx.dose_delivered_gy, 1, 10.0)
                    if fx.bladder_dose_2cc_gy:
                        bladder_eqd2 += calculate_eqd2_simple(fx.bladder_dose_2cc_gy, 1, 3.0)
                    if fx.rectum_dose_2cc_gy:
                        rectum_eqd2 += calculate_eqd2_simple(fx.rectum_dose_2cc_gy, 1, 3.0)
                    if fx.sigmoid_dose_2cc_gy:
                        sigmoid_eqd2 += calculate_eqd2_simple(fx.sigmoid_dose_2cc_gy, 1, 3.0)

        # --- Survival & Time-To-Event Calculations (SPSS / R) ---
        reg_date = pt.date_of_registration
        diag_date = diag.date_of_diagnosis if (diag and diag.date_of_diagnosis) else reg_date
        index_date = diag_date or reg_date

        # Last Contact Date
        last_contact_date = latest_fu.follow_up_date if latest_fu else (ebrt_end or brachy_end or reg_date)

        # Vital Status & Overall Survival (OS)
        death_reported = False
        death_date = None
        cause_of_death_str = ''

        for fu in fu_records:
            if fu.death_reported:
                death_reported = True
                death_date = fu.date_of_death or fu.follow_up_date
                if fu.cause_of_death:
                    cause_of_death_str = fu.cause_of_death.cause_name
                break

        if death_reported:
            vital_status = 'Dead'
            os_status = 1  # Event observed
            os_end_date = death_date or last_contact_date
        else:
            vital_status = latest_fu.disease_status.status_name if (latest_fu and latest_fu.disease_status) else 'Alive - Under Care'
            os_status = 0  # Censored
            os_end_date = last_contact_date

        os_days = None
        os_months = None
        if index_date and os_end_date:
            os_days = max(0, (os_end_date - index_date).days)
            os_months = round(os_days / 30.4375, 2)

        # Recurrence & Disease-Free Survival (DFS)
        recurrence_detected = False
        date_of_recurrence = None
        rec_sites_list = []

        for fu in fu_records:
            if fu.recurrence_detected:
                recurrence_detected = True
                if not date_of_recurrence:
                    date_of_recurrence = fu.date_of_recurrence or fu.follow_up_date
                sites_str = fu.recurrence_sites_display
                if sites_str and sites_str not in rec_sites_list:
                    rec_sites_list.append(sites_str)

        primary_rec_sites_str = ", ".join(rec_sites_list) if rec_sites_list else ''

        if recurrence_detected:
            dfs_status = 1  # Event observed
            dfs_end_date = date_of_recurrence or last_contact_date
        elif death_reported:
            # If death occurred due to disease without prior recorded recurrence, consider as event
            dfs_status = 1
            dfs_end_date = death_date or last_contact_date
        else:
            dfs_status = 0  # Censored at last follow-up
            dfs_end_date = last_contact_date

        dfs_days = None
        dfs_months = None
        if index_date and dfs_end_date:
            dfs_days = max(0, (dfs_end_date - index_date).days)
            dfs_months = round(dfs_days / 30.4375, 2)

        # Targets string for EBRT
        targets_str = ", ".join([s.ebrt_site.site_name for s in ebrt.sites.all() if s.ebrt_site]) if ebrt else ''

        # Compliance Reason Helper
        def format_compliance_reason(obj, reason_attr, specify_attr):
            if not obj:
                return ''
            reason_obj = getattr(obj, reason_attr, None)
            specify = getattr(obj, specify_attr, '') or ''
            if reason_obj:
                r_name = getattr(reason_obj, 'reason_name', str(reason_obj))
                return f"{r_name} ({specify})" if specify else r_name
            return specify

        # Build patient row
        row = [
            # 1. Demographics & Identification
            pt.mr_no,
            pt.pt_name,
            pt.age if pt.age is not None else '',
            pt.sex,
            pt.date_of_birth.isoformat() if pt.date_of_birth else '',
            pt.date_of_registration.isoformat() if pt.date_of_registration else '',
            pt.primary_consultant.consultant_name if pt.primary_consultant else '',
            pt.state.state_name if (pt.state and hasattr(pt.state, 'state_name')) else (str(pt.state) if pt.state else ''),
            pt.district.district_name if (pt.district and hasattr(pt.district, 'district_name')) else (str(pt.district) if pt.district else ''),
            
            # 2. Oncology Diagnosis & Staging
            diag.date_of_diagnosis.isoformat() if (diag and diag.date_of_diagnosis) else '',
            diag.primary_site.site if (diag and diag.primary_site) else '',
            diag.histology.histology_name if (diag and diag.histology) else (diag.histology_other if diag else ''),
            diag.grade.grade_name if (diag and diag.grade) else '',
            diag.stage_text if diag else '',
            stage_group,
            diag.t_status if diag else '',
            diag.n_status if diag else '',
            diag.m_status if diag else '',
            diag.laterality if diag else '',
            
            # 3. Baseline Examination & Anthropometrics
            base_enc.ecog.score if (base_enc and base_enc.ecog) else '',
            height_cm if height_cm is not None else '',
            weight_kg if weight_kg is not None else '',
            bmi if bmi is not None else '',
            base_enc.tumour_size_cm if (base_enc and base_enc.tumour_size_cm) else '',
            base_enc.tumour_size_2_cm if (base_enc and base_enc.tumour_size_2_cm) else '',
            base_enc.tumour_size_3_cm if (base_enc and base_enc.tumour_size_3_cm) else '',
            1 if (base_enc and base_enc.parametrial_invasion) else 0,
            1 if (base_enc and base_enc.para_left) else 0,
            1 if (base_enc and base_enc.para_right) else 0,
            1 if (base_enc and base_enc.rectal_invasion) else 0,
            1 if (base_enc and base_enc.bladder_invasion) else 0,
            
            # 4. Neoadjuvant Chemotherapy (NACT)
            1 if (nact and nact.nact_received) else 0,
            nact.chemo_regimen.regimen_code if (nact and nact.chemo_regimen) else '',
            nact.planned_cycles if (nact and nact.planned_cycles) else '',
            nact.cycles.count() if nact else '',
            nact.response_to_nact.response_code if (nact and nact.response_to_nact) else '',
            getattr(nact, 'treatment_status', (nact.nact_status.status_name if (nact and nact.nact_status) else '')),
            format_compliance_reason(nact, 'compliance_reason', 'specify_reason'),
            getattr(nact, 'post_nact_staging', ''),
            1 if (nact and nact.is_approved) else 0,
            
            # 5. External Beam Radiotherapy (EBRT) & Concurrent Chemo
            1 if ebrt else 0,
            ebrt.ebrt_intent.intent_name if (ebrt and ebrt.ebrt_intent) else '',
            ebrt.ebrt_technique.technique_name if (ebrt and ebrt.ebrt_technique) else '',
            targets_str,
            ebrt.total_dose_gy if (ebrt and ebrt.total_dose_gy) else '',
            ebrt.total_fractions if (ebrt and ebrt.total_fractions) else '',
            ebrt.ebrt_start_date.isoformat() if (ebrt and ebrt.ebrt_start_date) else '',
            ebrt.ebrt_end_date.isoformat() if (ebrt and ebrt.ebrt_end_date) else '',
            ebrt_ott_days if ebrt_ott_days is not None else '',
            getattr(ebrt, 'treatment_status', (ebrt.course_status.status_name if (ebrt and ebrt.course_status) else '')),
            format_compliance_reason(ebrt, 'compliance_reason', 'specify_reason'),
            1 if (ebrt and ebrt.is_approved) else 0,
            1 if (conc and conc.concurrent_received) else 0,
            conc.chemo_regimen.regimen_code if (conc and conc.chemo_regimen) else '',
            conc.cycles.count() if conc else '',
            
            # 6. Brachytherapy & Radiobiology
            1 if brachy else 0,
            brachy.brachy_source.source_name if (brachy and brachy.brachy_source) else '',
            brachy.brachy_dosing.dosing_point if (brachy and brachy.brachy_dosing) else '',
            brachy.prescription_dose_gy if (brachy and brachy.prescription_dose_gy) else '',
            brachy.total_fractions_planned if (brachy and brachy.total_fractions_planned) else '',
            brachy.total_fractions_delivered if (brachy and brachy.total_fractions_delivered) else '',
            brachy_start.isoformat() if brachy_start else '',
            brachy_end.isoformat() if brachy_end else '',
            total_ott_days if total_ott_days is not None else '',
            round(tumor_eqd2, 1) if tumor_eqd2 > 0 else '',
            round(bladder_eqd2, 1) if bladder_eqd2 > 0 else '',
            round(rectum_eqd2, 1) if rectum_eqd2 > 0 else '',
            round(sigmoid_eqd2, 1) if sigmoid_eqd2 > 0 else '',
            getattr(brachy, 'treatment_status', (brachy.completion_status or '')),
            format_compliance_reason(brachy, 'compliance_reason', 'specify_reason'),
            1 if (brachy and brachy.is_approved) else 0,
            
            # 7. Adjuvant Chemotherapy
            1 if (adj and adj.adjuvant_received) else 0,
            adj.chemo_regimen.regimen_code if (adj and adj.chemo_regimen) else '',
            adj.planned_cycles if (adj and adj.planned_cycles) else '',
            adj.cycles.count() if adj else '',
            getattr(adj, 'treatment_status', (adj.chemo_status.status_name if (adj and adj.chemo_status) else '')),
            format_compliance_reason(adj, 'compliance_reason', 'specify_reason'),
            1 if (adj and adj.is_approved) else 0,
            
            # 8. Follow-Up, Recurrence & Vital Status
            len(fu_records),
            latest_fu.follow_up_date.isoformat() if latest_fu else '',
            latest_fu.disease_status.status_name if (latest_fu and latest_fu.disease_status) else '',
            1 if recurrence_detected else 0,
            date_of_recurrence.isoformat() if date_of_recurrence else '',
            primary_rec_sites_str,
            vital_status,
            1 if death_reported else 0,
            death_date.isoformat() if death_date else '',
            cause_of_death_str,
            
            # 9. Statistical Survival Endpoints (SPSS / R Ready)
            os_status,
            os_days if os_days is not None else '',
            os_months if os_months is not None else '',
            dfs_status,
            dfs_days if dfs_days is not None else '',
            dfs_months if dfs_months is not None else ''
        ]
        rows.append(row)

    return headers, rows


def get_wide_data_dictionary():
    """
    Returns the comprehensive Codebook / Data Dictionary for the Wide-Format dataset.
    Used to populate the second sheet in Excel exports.
    """
    dict_headers = [
        'variable_name',
        'variable_label',
        'data_type',
        'clinical_domain',
        'description_and_methodology',
        'coding_and_valid_values'
    ]

    dict_rows = [
        # 1. Demographics & Identification
        ['mr_no', 'Medical Record Number', 'Text', 'Demographics', 'Unique institutional patient identifier at Kidwai Memorial Institute of Oncology', 'Unique identifier string'],
        ['patient_name', 'Patient Full Name', 'Text', 'Demographics', 'Full name of the patient', 'Text string'],
        ['age_years', 'Age at Presentation', 'Integer', 'Demographics', 'Patient age in completed years calculated from date of birth to registration', 'Positive integer (e.g. 18-99)'],
        ['sex', 'Biological Sex', 'Categorical', 'Demographics', 'Biological sex of the patient', 'Female, Male'],
        ['date_of_birth', 'Date of Birth', 'Date (YYYY-MM-DD)', 'Demographics', 'Patient date of birth', 'ISO-8601 date string'],
        ['registration_date', 'Hospital Registration Date', 'Date (YYYY-MM-DD)', 'Demographics', 'Date patient was formally registered in the oncology hospital database', 'ISO-8601 date string'],
        ['primary_consultant', 'Primary Attending Oncologist', 'Text', 'Demographics', 'Name of primary treating radiation/gynaecologic oncology consultant', 'Consultant name string'],
        ['state', 'State of Residence', 'Text', 'Demographics', 'Geographic state of domicile', 'State name string'],
        ['district', 'District of Residence', 'Text', 'Demographics', 'Geographic district of domicile', 'District name string'],

        # 2. Oncology Diagnosis & Staging
        ['date_of_diagnosis', 'Date of Primary Diagnosis', 'Date (YYYY-MM-DD)', 'Diagnosis & Staging', 'Date primary oncologic malignancy was formally confirmed', 'ISO-8601 date string'],
        ['primary_site', 'Primary Malignancy Site', 'Categorical', 'Diagnosis & Staging', 'Primary anatomical site of gynaecological malignancy', 'Cervix, Endometrium, Ovary, Vagina, Vulva, Gestational Trophoblastic Disease, Fallopian Tube, Other'],
        ['histology', 'Histological Subtype', 'Categorical', 'Diagnosis & Staging', 'Pathological histological cell type', 'Squamous Cell Carcinoma, Adenocarcinoma, Adenosquamous, Clear Cell, Serous, Endometrioid, Mucinous, Other'],
        ['grade', 'Tumour Differentiation Grade', 'Categorical', 'Diagnosis & Staging', 'Histological grade of differentiation', 'Grade 1 (Well differentiated), Grade 2 (Moderately differentiated), Grade 3 (Poorly differentiated), Not Assessed'],
        ['figo_stage', 'FIGO Stage', 'Categorical', 'Diagnosis & Staging', 'International Federation of Gynecology and Obstetrics clinical stage', 'IA1, IA2, IB1, IB2, IB3, IIA1, IIA2, IIB, IIIA, IIIB, IIIC1, IIIC2, IVA, IVB'],
        ['figo_stage_group', 'FIGO Main Stage Group', 'Categorical', 'Diagnosis & Staging', 'Consolidated main FIGO stage group for subgroup analysis', 'Stage I, Stage II, Stage III, Stage IV'],
        ['t_stage', 'TNM T Status', 'Categorical', 'Diagnosis & Staging', 'Primary tumour category according to AJCC/UICC TNM 8th Edition', 'T1, T1a, T1b, T2, T2a, T2b, T3, T3a, T3b, T4'],
        ['n_stage', 'TNM N Status', 'Categorical', 'Diagnosis & Staging', 'Regional lymph node involvement status', 'N0 (Negative), N1 (Pelvic nodes positive), N2 (Para-aortic nodes positive), Nx'],
        ['m_stage', 'TNM M Status', 'Categorical', 'Diagnosis & Staging', 'Distant metastasis status', 'M0 (No distant metastasis), M1 (Distant metastasis present)'],
        ['laterality', 'Laterality', 'Categorical', 'Diagnosis & Staging', 'Anatomical laterality of the primary lesion', 'Central, Bilateral, Left, Right, Midline'],

        # 3. Baseline Examination & Anthropometrics
        ['baseline_ecog_score', 'Baseline ECOG Performance Status', 'Integer (0-4)', 'Clinical Examination', 'Eastern Cooperative Oncology Group performance score at presentation', '0 = Fully active; 1 = Restricted strenuous activity; 2 = Ambulatory, capable of self-care; 3 = Capable of limited self-care; 4 = Completely disabled'],
        ['baseline_height_cm', 'Patient Baseline Height', 'Numeric (cm)', 'Clinical Examination', 'Standing height in centimeters auto-populated and confirmed across encounters', 'Numeric float (e.g. 155.0)'],
        ['baseline_weight_kg', 'Patient Baseline Weight', 'Numeric (kg)', 'Clinical Examination', 'Body weight in kilograms at baseline physical examination', 'Numeric float (e.g. 54.5)'],
        ['baseline_bmi', 'Body Mass Index (BMI)', 'Numeric (kg/m²)', 'Clinical Examination', 'Calculated Body Mass Index = weight(kg) / [height(m)]²', 'Numeric float (e.g. 22.7)'],
        ['tumour_size_cc_cm', 'Tumour Dimension Cranio-Caudal', 'Numeric (cm)', 'Clinical Examination', 'Largest cranio-caudal dimension measured on pelvic examination or MRI', 'Numeric float (e.g. 4.0)'],
        ['tumour_size_ap_cm', 'Tumour Dimension Antero-Posterior', 'Numeric (cm)', 'Clinical Examination', 'Antero-posterior tumour dimension measured clinically or on MRI', 'Numeric float (e.g. 3.5)'],
        ['tumour_size_ml_cm', 'Tumour Dimension Medio-Lateral', 'Numeric (cm)', 'Clinical Examination', 'Medio-lateral tumour dimension measured clinically or on MRI', 'Numeric float (e.g. 3.0)'],
        ['parametrial_invasion', 'Parametrial Invasion Present', 'Binary Indicator', 'Clinical Examination', 'Involvement of the parametrium on clinical pelvic examination', '1 = Yes, 0 = No'],
        ['parametrial_left', 'Left Parametrial Involvement', 'Binary Indicator', 'Clinical Examination', 'Involvement of the left parametrium', '1 = Yes, 0 = No'],
        ['parametrial_right', 'Right Parametrial Involvement', 'Binary Indicator', 'Clinical Examination', 'Involvement of the right parametrium', '1 = Yes, 0 = No'],
        ['rectal_invasion', 'Rectal Mucosal Invasion', 'Binary Indicator', 'Clinical Examination', 'Clinical or endoscopic rectal mucosal invasion', '1 = Yes, 0 = No'],
        ['bladder_invasion', 'Bladder Mucosal Invasion', 'Binary Indicator', 'Clinical Examination', 'Clinical or cystoscopic bladder mucosal invasion', '1 = Yes, 0 = No'],

        # 4. Neoadjuvant Chemotherapy (NACT)
        ['nact_given', 'NACT Administered', 'Binary Indicator', 'Neoadjuvant Chemotherapy', 'Whether neoadjuvant systemic chemotherapy was given prior to local therapy', '1 = Yes, 0 = No'],
        ['nact_regimen', 'NACT Chemotherapy Regimen', 'Text', 'Neoadjuvant Chemotherapy', 'Cytotoxic drug regimen administered', 'Paclitaxel + Carboplatin, Cisplatin + 5-FU, Other'],
        ['nact_planned_cycles', 'NACT Cycles Planned', 'Integer', 'Neoadjuvant Chemotherapy', 'Number of NACT cycles prescribed', 'Integer (e.g. 3)'],
        ['nact_received_cycles', 'NACT Cycles Delivered', 'Integer', 'Neoadjuvant Chemotherapy', 'Actual number of NACT cycles completed', 'Integer (e.g. 3)'],
        ['nact_response', 'Objective Tumour Response to NACT', 'Categorical', 'Neoadjuvant Chemotherapy', 'Clinical/radiological response assessed by RECIST 1.1', 'CR (Complete Response), PR (Partial Response), SD (Stable Disease), PD (Progressive Disease)'],
        ['nact_treatment_status', 'NACT Treatment Status', 'Categorical', 'Neoadjuvant Chemotherapy', 'Compliance and completion status of NACT course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['nact_reason', 'Reason for NACT Interruption / Discontinuation', 'Text', 'Neoadjuvant Chemotherapy', 'Reason code and remarks if NACT was not started, interrupted, or stopped early', 'Toxicity, Disease progression, Patient refusal, Transferred, Other'],
        ['nact_post_staging', 'Post-NACT FIGO Restaging', 'Categorical', 'Neoadjuvant Chemotherapy', 'Restaged FIGO stage following NACT course completion', 'FIGO stage string (e.g. Stage IIA, Stage IB3)'],
        ['nact_is_approved', 'NACT Course Approved', 'Binary Indicator', 'Neoadjuvant Chemotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 5. External Beam Radiotherapy (EBRT) & Concurrent Chemo
        ['ebrt_given', 'EBRT Administered', 'Binary Indicator', 'External Beam Radiotherapy', 'Whether external beam radiotherapy was administered', '1 = Yes, 0 = No'],
        ['ebrt_intent', 'EBRT Treatment Intent', 'Categorical', 'External Beam Radiotherapy', 'Clinical objective of radiotherapy course', 'Radical, Adjuvant, Palliative, Recurrence / Salvage'],
        ['ebrt_technique', 'EBRT Delivery Technique', 'Categorical', 'External Beam Radiotherapy', 'Radiotherapy delivery technique', '3DCRT, IMRT, VMAT, Tomotherapy, 2D Conventional'],
        ['ebrt_target_sites', 'EBRT Anatomical Target Sites', 'Text', 'External Beam Radiotherapy', 'Target volumes treated with external beam radiation', 'Whole Pelvis, Parametrial Boost, Para-aortic Nodes, Vaginal Vault'],
        ['ebrt_total_dose_gy', 'EBRT Total Physical Dose', 'Numeric (Gy)', 'External Beam Radiotherapy', 'Total prescribed physical dose in Gray', 'Numeric float (e.g. 45.0, 50.0)'],
        ['ebrt_fractions', 'EBRT Total Fractions', 'Integer', 'External Beam Radiotherapy', 'Total number of fractions delivered', 'Integer (e.g. 25)'],
        ['ebrt_start_date', 'EBRT Start Date', 'Date (YYYY-MM-DD)', 'External Beam Radiotherapy', 'First day of external beam radiation treatment', 'ISO-8601 date string'],
        ['ebrt_end_date', 'EBRT Completion Date', 'Date (YYYY-MM-DD)', 'External Beam Radiotherapy', 'Final day of external beam radiation treatment', 'ISO-8601 date string'],
        ['ebrt_ott_days', 'EBRT Overall Treatment Time (OTT)', 'Integer (Days)', 'External Beam Radiotherapy', 'Elapsed days from EBRT start to EBRT end inclusive: (end_date - start_date + 1)', 'Integer days (e.g. 35)'],
        ['ebrt_treatment_status', 'EBRT Treatment Status', 'Categorical', 'External Beam Radiotherapy', 'Compliance and completion status of EBRT course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['ebrt_reason', 'Reason for EBRT Interruption / Discontinuation', 'Text', 'External Beam Radiotherapy', 'Reason code and remarks if EBRT was not started, interrupted, or stopped early', 'Toxicity, Interruption, Machine breakdown, Medical unfit, Patient default'],
        ['ebrt_is_approved', 'EBRT Course Approved', 'Binary Indicator', 'External Beam Radiotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],
        ['concurrent_chemo_given', 'Concurrent Chemotherapy Given', 'Binary Indicator', 'External Beam Radiotherapy', 'Whether concurrent radiosensitizing chemotherapy was administered', '1 = Yes, 0 = No'],
        ['concurrent_chemo_regimen', 'Concurrent Chemotherapy Regimen', 'Text', 'External Beam Radiotherapy', 'Chemotherapy agent used for concurrent radiosensitization', 'Weekly Cisplatin (40 mg/m²), Carboplatin, Other'],
        ['concurrent_chemo_cycles', 'Concurrent Chemo Cycles Administered', 'Integer', 'External Beam Radiotherapy', 'Number of weekly radiosensitizing cycles completed', 'Integer (e.g. 5)'],

        # 6. Brachytherapy & Radiobiology EQD2
        ['brachy_given', 'Brachytherapy Administered', 'Binary Indicator', 'Brachytherapy & Dosimetry', 'Whether brachytherapy course was administered', '1 = Yes, 0 = No'],
        ['brachy_source', 'Brachytherapy Radiation Source', 'Categorical', 'Brachytherapy & Dosimetry', 'Radioactive source used for HDR afterloading', 'Ir-192 HDR, Co-60 HDR, Other'],
        ['brachy_dosing_system', 'Brachytherapy Dosing System', 'Categorical', 'Brachytherapy & Dosimetry', 'Dosimetric specification system', 'HR-CTV D90 (GEC-ESTRO), Point A (Manchester), ICRU 38'],
        ['brachy_prescription_dose_gy', 'Brachytherapy Dose per Fraction', 'Numeric (Gy)', 'Brachytherapy & Dosimetry', 'Prescription dose per fraction in Gray', 'Numeric float (e.g. 7.0, 7.5)'],
        ['brachy_fractions_planned', 'Brachytherapy Fractions Planned', 'Integer', 'Brachytherapy & Dosimetry', 'Number of planned brachytherapy fractions', 'Integer (e.g. 2, 3, 4)'],
        ['brachy_fractions_delivered', 'Brachytherapy Fractions Delivered', 'Integer', 'Brachytherapy & Dosimetry', 'Total number of brachytherapy fractions successfully delivered', 'Integer (e.g. 2, 3, 4)'],
        ['brachy_start_date', 'Brachytherapy Start Date', 'Date (YYYY-MM-DD)', 'Brachytherapy & Dosimetry', 'Date of first brachytherapy applicator insertion/fraction', 'ISO-8601 date string'],
        ['brachy_end_date', 'Brachytherapy Completion Date', 'Date (YYYY-MM-DD)', 'Brachytherapy & Dosimetry', 'Date of final brachytherapy fraction delivery', 'ISO-8601 date string'],
        ['total_ott_days', 'Total Overall Treatment Time (EBRT to Brachy)', 'Integer (Days)', 'Brachytherapy & Dosimetry', 'Total calendar days from first EBRT fraction to last Brachytherapy fraction inclusive: (brachy_end - ebrt_start + 1). Clinical benchmark <= 56 days (8 weeks)', 'Integer days (e.g. 49)'],
        ['cumul_hrctv_d90_eqd2', 'Cumulative HR-CTV D90 EQD2 (Tumour)', 'Numeric (Gy₁₀)', 'Brachytherapy & Dosimetry', 'Total Equivalent Dose in 2 Gy fractions to tumour (EBRT + Brachytherapy) computed using Linear-Quadratic model with α/β = 10 Gy. Clinical goal >= 85 Gy₁₀', 'Numeric float (e.g. 87.5)'],
        ['cumul_bladder_2cc_eqd2', 'Cumulative Bladder D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of bladder (EBRT + Brachytherapy) with α/β = 3 Gy. Constraint < 90 Gy₃', 'Numeric float (e.g. 78.2)'],
        ['cumul_rectum_2cc_eqd2', 'Cumulative Rectum D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of rectum (EBRT + Brachytherapy) with α/β = 3 Gy. Constraint < 75 Gy₃', 'Numeric float (e.g. 68.4)'],
        ['cumul_sigmoid_2cc_eqd2', 'Cumulative Sigmoid D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of sigmoid colon with α/β = 3 Gy. Constraint < 75 Gy₃', 'Numeric float (e.g. 64.1)'],
        ['brachy_treatment_status', 'Brachytherapy Treatment Status', 'Categorical', 'Brachytherapy & Dosimetry', 'Compliance and completion status of brachytherapy course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['brachy_reason', 'Reason for Brachytherapy Interruption / Discontinuation', 'Text', 'Brachytherapy & Dosimetry', 'Clinical reason if brachytherapy was not started, held, or stopped', 'Medical unfit, Anatomical constraint, Patient refusal, Toxicity'],
        ['brachy_is_approved', 'Brachytherapy Course Approved', 'Binary Indicator', 'Brachytherapy & Dosimetry', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 7. Adjuvant Chemotherapy
        ['adjuvant_chemo_given', 'Adjuvant Chemotherapy Administered', 'Binary Indicator', 'Adjuvant Chemotherapy', 'Whether post-radiation adjuvant systemic chemotherapy was administered', '1 = Yes, 0 = No'],
        ['adjuvant_regimen', 'Adjuvant Chemotherapy Regimen', 'Text', 'Adjuvant Chemotherapy', 'Adjuvant systemic drug regimen', 'Paclitaxel + Carboplatin, Other'],
        ['adjuvant_planned_cycles', 'Adjuvant Cycles Planned', 'Integer', 'Adjuvant Chemotherapy', 'Number of adjuvant cycles prescribed', 'Integer (e.g. 4)'],
        ['adjuvant_received_cycles', 'Adjuvant Cycles Delivered', 'Integer', 'Adjuvant Chemotherapy', 'Number of adjuvant cycles delivered', 'Integer (e.g. 4)'],
        ['adjuvant_treatment_status', 'Adjuvant Chemo Treatment Status', 'Categorical', 'Adjuvant Chemotherapy', 'Compliance and completion status of adjuvant course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['adjuvant_reason', 'Reason for Adjuvant Interruption / Discontinuation', 'Text', 'Adjuvant Chemotherapy', 'Reason code and remarks if adjuvant chemotherapy was not started or stopped early', 'Toxicity, Neuropathy, Patient refusal, Progression'],
        ['adjuvant_is_approved', 'Adjuvant Course Approved', 'Binary Indicator', 'Adjuvant Chemotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 8. Follow-Up, Recurrence & Vital Status
        ['followup_visits_count', 'Number of Follow-Up Encounters', 'Integer', 'Follow-Up & Recurrence', 'Total number of documented follow-up surveillance clinic/proxy visits', 'Integer (e.g. 4)'],
        ['last_followup_date', 'Date of Last Follow-Up Contact', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Date of most recent clinical examination, telephone check, or proxy contact', 'ISO-8601 date string'],
        ['current_disease_status', 'Disease Status at Last Contact', 'Categorical', 'Follow-Up & Recurrence', 'Oncologic disease status assessed at last follow-up visit', 'No Evidence of Disease (NED), Stable Disease, Partial Response, Progression / Residual Disease, Lost to Follow-Up, Dead'],
        ['recurrence_detected', 'Disease Recurrence Documented', 'Binary Indicator', 'Follow-Up & Recurrence', 'Whether recurrence or disease progression was detected during surveillance', '1 = Yes, 0 = No'],
        ['date_of_recurrence', 'Date of Recurrence Confirmation', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Date when local, nodal, or distant recurrence was clinically/biochemically/radiologically confirmed', 'ISO-8601 date string'],
        ['primary_recurrence_sites', 'Anatomical Sites of Recurrence', 'Text', 'Follow-Up & Recurrence', 'Documented anatomical sites of relapse', 'Vault / Central, Pelvic Nodal, Para-aortic Nodal, Distant Visceral (Lung/Liver/Bone)'],
        ['vital_status', 'Patient Vital Status', 'Categorical', 'Follow-Up & Recurrence', 'Patient vital status at the close of observation', 'Alive - NED, Alive with Recurrence, Dead, Lost to Follow-up'],
        ['death_reported', 'Death Reported', 'Binary Indicator', 'Follow-Up & Recurrence', 'Whether patient death has been formally documented', '1 = Yes, 0 = No'],
        ['date_of_death', 'Date of Death', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Documented date of patient death', 'ISO-8601 date string'],
        ['cause_of_death', 'Documented Cause of Death', 'Categorical', 'Follow-Up & Recurrence', 'Clinical cause of death categorized according to oncology registry standards', 'Disease related, Non-disease related, Death due to other cancer, Not known / Unspecified'],

        # 9. Statistical Survival Endpoints (SPSS / R Ready)
        ['os_status', 'Overall Survival Event Status', 'Binary Indicator (0/1)', 'Statistical Survival Endpoints', 'Event indicator for Overall Survival: 1 = Event observed (Death); 0 = Censored (Alive or Lost to Follow-up at last contact). Directly usable in R Surv(os_days, os_status)', '1 = Dead, 0 = Censored'],
        ['os_days', 'Overall Survival Time (Days)', 'Integer (Days)', 'Statistical Survival Endpoints', 'Time elapsed in days from index date (date of diagnosis/registration) to date of death or last follow-up contact', 'Integer >= 0'],
        ['os_months', 'Overall Survival Time (Months)', 'Numeric (Months)', 'Statistical Survival Endpoints', 'Overall survival time in months = os_days / 30.4375 rounded to 2 decimal places', 'Numeric float >= 0'],
        ['dfs_status', 'Disease-Free Survival Event Status', 'Binary Indicator (0/1)', 'Statistical Survival Endpoints', 'Event indicator for Disease-Free / Progression-Free Survival: 1 = Event observed (Documented recurrence or disease-related death); 0 = Censored (Disease-free at last contact). Directly usable in R Surv(dfs_days, dfs_status)', '1 = Event, 0 = Censored'],
        ['dfs_days', 'Disease-Free Survival Time (Days)', 'Integer (Days)', 'Statistical Survival Endpoints', 'Time elapsed in days from index date to date of recurrence, disease-related death, or last recurrence-free contact', 'Integer >= 0'],
        ['dfs_months', 'Disease-Free Survival Time (Months)', 'Numeric (Months)', 'Statistical Survival Endpoints', 'Disease-free survival time in months = dfs_days / 30.4375 rounded to 2 decimal places', 'Numeric float >= 0'],
    ]

    return dict_headers, dict_rows


def get_long_data_dictionary():
    """
    Returns the Codebook / Data Dictionary for the Long-Format dataset.
    Used to populate the second sheet in Excel exports.
    """
    dict_headers = [
        'variable_name',
        'variable_label',
        'data_type',
        'clinical_domain',
        'description_and_methodology',
        'coding_and_valid_values'
    ]

    dict_rows = [
        ['mr_no', 'Medical Record Number', 'Text', 'Demographics', 'Unique institutional patient identifier at Kidwai Memorial Institute of Oncology', 'Unique identifier string'],
        ['patient_name', 'Patient Full Name', 'Text', 'Demographics', 'Full legal name of the patient', 'Text string'],
        ['primary_site', 'Primary Malignancy Site', 'Categorical', 'Diagnosis & Staging', 'Primary anatomical site of gynaecological malignancy', 'Cervix, Endometrium, Ovary, Vagina, Vulva, Other'],
        ['figo_stage', 'FIGO Stage', 'Categorical', 'Diagnosis & Staging', 'FIGO stage at presentation', 'Stage I - IV string'],
        ['event_domain', 'Clinical Treatment / Surveillance Domain', 'Categorical', 'Timeline Domain', 'Clinical phase or modality of the documented event', 'NACT, EBRT, Concurrent_Chemo, Brachytherapy, Adjuvant_Chemo, Follow_Up'],
        ['course_identifier', 'Course / Episode Unique Identifier', 'Text', 'Timeline Domain', 'Unique identifier linking the event to its specific treatment or follow-up course', 'e.g. NACT-C1, EBRT-C1-Conc, Brachy-C1-S1, ADJ-C1, FU-1'],
        ['event_sequence', 'Cycle / Fraction / Visit Sequence Number', 'Integer', 'Event Properties', 'Ordinal sequence of the cycle, fraction, or follow-up visit', 'Positive integer (1, 2, 3...)'],
        ['event_date', 'Date of Event Administration', 'Date (YYYY-MM-DD)', 'Event Properties', 'Actual calendar date when drug was given, RT fraction delivered, or clinic visit conducted', 'ISO-8601 date string'],
        ['event_type_or_agent', 'Administered Agent / Applicator / Status', 'Text', 'Event Properties', 'Specific drug agent name, brachytherapy applicator, or follow-up clinical status', 'Drug name (e.g. Cisplatin, Paclitaxel), Applicator type, or status string'],
        ['administered_dose', 'Delivered Dose Amount', 'Numeric', 'Event Properties', 'Prescribed physical dose delivered during this specific cycle or fraction', 'Numeric float (e.g. 50.0, 7.0) or empty'],
        ['dose_unit', 'Dose Measurement Unit', 'Text', 'Event Properties', 'Unit of measurement for the dose', 'Gy, mg, mg/m², mg/kg'],
        ['administration_days', 'Number of Administration Days', 'Integer', 'Event Properties', 'Duration of administration in days for systemic chemotherapy cycles', 'Integer (e.g. 1, 3) or empty'],
        ['day_number', 'Day of Administration Cycle', 'Integer', 'Event Properties', 'Specific day of the multi-day protocol (e.g. Day 1, Day 8)', 'Integer or empty'],
        ['administration_route', 'Route / Guidance Method', 'Categorical', 'Event Properties', 'Route of drug administration or brachytherapy image guidance modality', 'IV, Oral, CT-guided, Ultrasound-guided, Clinic Visit'],
        ['event_status', 'Event Completion Status', 'Categorical', 'Event Properties', 'Delivery status of the specific event', 'Administered, Delivered, Completed, Not Administered'],
        ['approval_status', 'Electronic Approval Status', 'Text', 'Audit & Governance', 'Clinical consultant electronic sign-off status and approver identifier', 'Approved by [Name] / Draft / Logged'],
    ]

    return dict_headers, dict_rows



def get_long_format_data(patients_qs):
    """
    Generates standardized Long-Format Event-Level Records.
    Contains one row per drug administration cycle, RT course/fraction, and follow-up visit.
    Ideal for longitudinal analysis, timeline plotting, and mixed-effects models in R.
    """
    headers = [
        'mr_no', 'patient_name', 'primary_site', 'figo_stage',
        'event_domain', 'course_identifier', 'event_sequence', 'event_date',
        'event_type_or_agent', 'administered_dose', 'dose_unit',
        'administration_days', 'day_number', 'administration_route',
        'event_status', 'approval_status'
    ]

    rows = []
    for pt in patients_qs:
        diag = pt.diagnoses.filter(is_current=True, soft_deleted=False).first() or pt.diagnoses.filter(soft_deleted=False).first()
        site_str = diag.primary_site.site if (diag and diag.primary_site) else ''
        stage_str = diag.stage_text if diag else ''

        # 1. NACT Drug Administrations
        for nact in pt.nact_courses.filter(soft_deleted=False, nact_received=True):
            appr_str = f"Approved by {nact.approved_by}" if nact.is_approved else "Draft"
            for cyc in nact.cycles.all():
                for d in cyc.drugs.all():
                    rows.append([
                        pt.mr_no, pt.pt_name, site_str, stage_str,
                        'NACT', f"NACT-C{nact.nact_course_id}", cyc.cycle_number,
                        cyc.cycle_date.isoformat() if cyc.cycle_date else '',
                        d.chemo_agent.agent_name if d.chemo_agent else '',
                        d.dose,
                        d.dose_unit.unit_name if d.dose_unit else '',
                        d.no_of_days, d.day_of_administration,
                        d.chemo_route.route_name if d.chemo_route else '',
                        'Administered' if d.administered else 'Not Administered',
                        appr_str
                    ])

        # 2. Concurrent Chemo Administrations
        for ebrt in pt.ebrt_courses.filter(soft_deleted=False):
            ebrt_appr = f"Approved by {ebrt.approved_by}" if ebrt.is_approved else "Draft"
            for conc in ebrt.concurrent_chemo_courses.filter(soft_deleted=False, concurrent_received=True):
                for cyc in conc.cycles.all():
                    for d in cyc.drugs.all():
                        rows.append([
                            pt.mr_no, pt.pt_name, site_str, stage_str,
                            'Concurrent_Chemo', f"EBRT-C{ebrt.ebrt_course_id}-Conc", cyc.cycle_number,
                            cyc.cycle_date.isoformat() if cyc.cycle_date else '',
                            d.chemo_agent.agent_name if d.chemo_agent else '',
                            d.dose,
                            d.dose_unit.unit_name if d.dose_unit else '',
                            d.no_of_days, d.day_of_administration,
                            d.chemo_route.route_name if d.chemo_route else '',
                            'Administered' if d.administered else 'Not Administered',
                            ebrt_appr
                        ])

        # 3. Adjuvant Chemo Administrations
        for adj in pt.adjuvant_courses.filter(soft_deleted=False, adjuvant_received=True):
            adj_appr = f"Approved by {adj.approved_by}" if adj.is_approved else "Draft"
            for cyc in adj.cycles.all():
                for d in cyc.drugs.all():
                    rows.append([
                        pt.mr_no, pt.pt_name, site_str, stage_str,
                        'Adjuvant_Chemo', f"ADJ-C{adj.adjuvant_course_id}", cyc.cycle_number,
                        cyc.cycle_date.isoformat() if cyc.cycle_date else '',
                        d.chemo_agent.agent_name if d.chemo_agent else '',
                        d.dose,
                        d.dose_unit.unit_name if d.dose_unit else '',
                        d.no_of_days, d.day_of_administration,
                        d.chemo_route.route_name if d.chemo_route else '',
                        'Administered' if d.administered else 'Not Administered',
                        adj_appr
                    ])

        # 4. Brachytherapy Fraction Applications
        for br in pt.brachy_courses.filter(soft_deleted=False):
            br_appr = f"Approved by {br.approved_by}" if br.is_approved else "Draft"
            for sess in br.sessions.all():
                app_name = sess.applicator.name if sess.applicator else 'Brachy Applicator'
                for fx in sess.fractions.all():
                    rows.append([
                        pt.mr_no, pt.pt_name, site_str, stage_str,
                        'Brachytherapy', f"Brachy-C{br.brachy_course_id}-S{sess.session_number}", fx.fraction_number,
                        fx.fraction_date.isoformat() if fx.fraction_date else (sess.session_date.isoformat() if sess.session_date else ''),
                        f"{app_name} (Fx #{fx.fraction_number})",
                        fx.dose_delivered_gy or fx.hrctv_d90_gy or '',
                        'Gy',
                        '', '',
                        sess.image_guidance.guidance_name if sess.image_guidance else '',
                        fx.fraction_status.status_name if fx.fraction_status else 'Delivered',
                        br_appr
                    ])

        # 5. Follow-Up Clinical Encounters
        for idx, fu in enumerate(pt.follow_up_records.filter(soft_deleted=False).order_by('follow_up_date'), start=1):
            disease_status_str = fu.disease_status.status_name if fu.disease_status else 'Follow-Up'
            rows.append([
                pt.mr_no, pt.pt_name, site_str, stage_str,
                'Follow_Up', f"FU-{fu.follow_up_status_id}", idx,
                fu.follow_up_date.isoformat() if fu.follow_up_date else '',
                disease_status_str,
                '', '', '', '',
                fu.contact_type.contact_type if fu.contact_type else 'Clinic Visit',
                'Completed',
                'Logged'
            ])

    return headers, rows


def get_wide_data_dictionary():
    """
    Returns the comprehensive Codebook / Data Dictionary for the Wide-Format dataset.
    Used to populate the second sheet in Excel exports.
    """
    dict_headers = [
        'variable_name',
        'variable_label',
        'data_type',
        'clinical_domain',
        'description_and_methodology',
        'coding_and_valid_values'
    ]

    dict_rows = [
        # 1. Demographics & Identification
        ['mr_no', 'Medical Record Number', 'Text', 'Demographics', 'Unique institutional patient identifier at Kidwai Memorial Institute of Oncology', 'Unique identifier string'],
        ['patient_name', 'Patient Full Name', 'Text', 'Demographics', 'Full name of the patient', 'Text string'],
        ['age_years', 'Age at Presentation', 'Integer', 'Demographics', 'Patient age in completed years calculated from date of birth to registration', 'Positive integer (e.g. 18-99)'],
        ['sex', 'Biological Sex', 'Categorical', 'Demographics', 'Biological sex of the patient', 'Female, Male'],
        ['date_of_birth', 'Date of Birth', 'Date (YYYY-MM-DD)', 'Demographics', 'Patient date of birth', 'ISO-8601 date string'],
        ['registration_date', 'Hospital Registration Date', 'Date (YYYY-MM-DD)', 'Demographics', 'Date patient was formally registered in the oncology hospital database', 'ISO-8601 date string'],
        ['primary_consultant', 'Primary Attending Oncologist', 'Text', 'Demographics', 'Name of primary treating radiation/gynaecologic oncology consultant', 'Consultant name string'],
        ['state', 'State of Residence', 'Text', 'Demographics', 'Geographic state of domicile', 'State name string'],
        ['district', 'District of Residence', 'Text', 'Demographics', 'Geographic district of domicile', 'District name string'],

        # 2. Oncology Diagnosis & Staging
        ['date_of_diagnosis', 'Date of Primary Diagnosis', 'Date (YYYY-MM-DD)', 'Diagnosis & Staging', 'Date primary oncologic malignancy was formally confirmed', 'ISO-8601 date string'],
        ['primary_site', 'Primary Malignancy Site', 'Categorical', 'Diagnosis & Staging', 'Primary anatomical site of gynaecological malignancy', 'Cervix, Endometrium, Ovary, Vagina, Vulva, Gestational Trophoblastic Disease, Fallopian Tube, Other'],
        ['histology', 'Histological Subtype', 'Categorical', 'Diagnosis & Staging', 'Pathological histological cell type', 'Squamous Cell Carcinoma, Adenocarcinoma, Adenosquamous, Clear Cell, Serous, Endometrioid, Mucinous, Other'],
        ['grade', 'Tumour Differentiation Grade', 'Categorical', 'Diagnosis & Staging', 'Histological grade of differentiation', 'Grade 1 (Well differentiated), Grade 2 (Moderately differentiated), Grade 3 (Poorly differentiated), Not Assessed'],
        ['figo_stage', 'FIGO Stage', 'Categorical', 'Diagnosis & Staging', 'International Federation of Gynecology and Obstetrics clinical stage', 'IA1, IA2, IB1, IB2, IB3, IIA1, IIA2, IIB, IIIA, IIIB, IIIC1, IIIC2, IVA, IVB'],
        ['figo_stage_group', 'FIGO Main Stage Group', 'Categorical', 'Diagnosis & Staging', 'Consolidated main FIGO stage group for subgroup analysis', 'Stage I, Stage II, Stage III, Stage IV'],
        ['t_stage', 'TNM T Status', 'Categorical', 'Diagnosis & Staging', 'Primary tumour category according to AJCC/UICC TNM 8th Edition', 'T1, T1a, T1b, T2, T2a, T2b, T3, T3a, T3b, T4'],
        ['n_stage', 'TNM N Status', 'Categorical', 'Diagnosis & Staging', 'Regional lymph node involvement status', 'N0 (Negative), N1 (Pelvic nodes positive), N2 (Para-aortic nodes positive), Nx'],
        ['m_stage', 'TNM M Status', 'Categorical', 'Diagnosis & Staging', 'Distant metastasis status', 'M0 (No distant metastasis), M1 (Distant metastasis present)'],
        ['laterality', 'Laterality', 'Categorical', 'Diagnosis & Staging', 'Anatomical laterality of the primary lesion', 'Central, Bilateral, Left, Right, Midline'],

        # 3. Baseline Examination & Anthropometrics
        ['baseline_ecog_score', 'Baseline ECOG Performance Status', 'Integer (0-4)', 'Clinical Examination', 'Eastern Cooperative Oncology Group performance score at presentation', '0 = Fully active; 1 = Restricted strenuous activity; 2 = Ambulatory, capable of self-care; 3 = Capable of limited self-care; 4 = Completely disabled'],
        ['baseline_height_cm', 'Patient Baseline Height', 'Numeric (cm)', 'Clinical Examination', 'Standing height in centimeters auto-populated and confirmed across encounters', 'Numeric float (e.g. 155.0)'],
        ['baseline_weight_kg', 'Patient Baseline Weight', 'Numeric (kg)', 'Clinical Examination', 'Body weight in kilograms at baseline physical examination', 'Numeric float (e.g. 54.5)'],
        ['baseline_bmi', 'Body Mass Index (BMI)', 'Numeric (kg/m²)', 'Clinical Examination', 'Calculated Body Mass Index = weight(kg) / [height(m)]²', 'Numeric float (e.g. 22.7)'],
        ['tumour_size_cc_cm', 'Tumour Dimension Cranio-Caudal', 'Numeric (cm)', 'Clinical Examination', 'Largest cranio-caudal dimension measured on pelvic examination or MRI', 'Numeric float (e.g. 4.0)'],
        ['tumour_size_ap_cm', 'Tumour Dimension Antero-Posterior', 'Numeric (cm)', 'Clinical Examination', 'Antero-posterior tumour dimension measured clinically or on MRI', 'Numeric float (e.g. 3.5)'],
        ['tumour_size_ml_cm', 'Tumour Dimension Medio-Lateral', 'Numeric (cm)', 'Clinical Examination', 'Medio-lateral tumour dimension measured clinically or on MRI', 'Numeric float (e.g. 3.0)'],
        ['parametrial_invasion', 'Parametrial Invasion Present', 'Binary Indicator', 'Clinical Examination', 'Involvement of the parametrium on clinical pelvic examination', '1 = Yes, 0 = No'],
        ['parametrial_left', 'Left Parametrial Involvement', 'Binary Indicator', 'Clinical Examination', 'Involvement of the left parametrium', '1 = Yes, 0 = No'],
        ['parametrial_right', 'Right Parametrial Involvement', 'Binary Indicator', 'Clinical Examination', 'Involvement of the right parametrium', '1 = Yes, 0 = No'],
        ['rectal_invasion', 'Rectal Mucosal Invasion', 'Binary Indicator', 'Clinical Examination', 'Clinical or endoscopic rectal mucosal invasion', '1 = Yes, 0 = No'],
        ['bladder_invasion', 'Bladder Mucosal Invasion', 'Binary Indicator', 'Clinical Examination', 'Clinical or cystoscopic bladder mucosal invasion', '1 = Yes, 0 = No'],

        # 4. Neoadjuvant Chemotherapy (NACT)
        ['nact_given', 'NACT Administered', 'Binary Indicator', 'Neoadjuvant Chemotherapy', 'Whether neoadjuvant systemic chemotherapy was given prior to local therapy', '1 = Yes, 0 = No'],
        ['nact_regimen', 'NACT Chemotherapy Regimen', 'Text', 'Neoadjuvant Chemotherapy', 'Cytotoxic drug regimen administered', 'Paclitaxel + Carboplatin, Cisplatin + 5-FU, Other'],
        ['nact_planned_cycles', 'NACT Cycles Planned', 'Integer', 'Neoadjuvant Chemotherapy', 'Number of NACT cycles prescribed', 'Integer (e.g. 3)'],
        ['nact_received_cycles', 'NACT Cycles Delivered', 'Integer', 'Neoadjuvant Chemotherapy', 'Actual number of NACT cycles completed', 'Integer (e.g. 3)'],
        ['nact_response', 'Objective Tumour Response to NACT', 'Categorical', 'Neoadjuvant Chemotherapy', 'Clinical/radiological response assessed by RECIST 1.1', 'CR (Complete Response), PR (Partial Response), SD (Stable Disease), PD (Progressive Disease)'],
        ['nact_treatment_status', 'NACT Treatment Status', 'Categorical', 'Neoadjuvant Chemotherapy', 'Compliance and completion status of NACT course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['nact_reason', 'Reason for NACT Interruption / Discontinuation', 'Text', 'Neoadjuvant Chemotherapy', 'Reason code and remarks if NACT was not started, interrupted, or stopped early', 'Toxicity, Disease progression, Patient refusal, Transferred, Other'],
        ['nact_post_staging', 'Post-NACT FIGO Restaging', 'Categorical', 'Neoadjuvant Chemotherapy', 'Restaged FIGO stage following NACT course completion', 'FIGO stage string (e.g. Stage IIA, Stage IB3)'],
        ['nact_is_approved', 'NACT Course Approved', 'Binary Indicator', 'Neoadjuvant Chemotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 5. External Beam Radiotherapy (EBRT) & Concurrent Chemo
        ['ebrt_given', 'EBRT Administered', 'Binary Indicator', 'External Beam Radiotherapy', 'Whether external beam radiotherapy was administered', '1 = Yes, 0 = No'],
        ['ebrt_intent', 'EBRT Treatment Intent', 'Categorical', 'External Beam Radiotherapy', 'Clinical objective of radiotherapy course', 'Radical, Adjuvant, Palliative, Recurrence / Salvage'],
        ['ebrt_technique', 'EBRT Delivery Technique', 'Categorical', 'External Beam Radiotherapy', 'Radiotherapy delivery technique', '3DCRT, IMRT, VMAT, Tomotherapy, 2D Conventional'],
        ['ebrt_target_sites', 'EBRT Anatomical Target Sites', 'Text', 'External Beam Radiotherapy', 'Target volumes treated with external beam radiation', 'Whole Pelvis, Parametrial Boost, Para-aortic Nodes, Vaginal Vault'],
        ['ebrt_total_dose_gy', 'EBRT Total Physical Dose', 'Numeric (Gy)', 'External Beam Radiotherapy', 'Total prescribed physical dose in Gray', 'Numeric float (e.g. 45.0, 50.0)'],
        ['ebrt_fractions', 'EBRT Total Fractions', 'Integer', 'External Beam Radiotherapy', 'Total number of fractions delivered', 'Integer (e.g. 25)'],
        ['ebrt_start_date', 'EBRT Start Date', 'Date (YYYY-MM-DD)', 'External Beam Radiotherapy', 'First day of external beam radiation treatment', 'ISO-8601 date string'],
        ['ebrt_end_date', 'EBRT Completion Date', 'Date (YYYY-MM-DD)', 'External Beam Radiotherapy', 'Final day of external beam radiation treatment', 'ISO-8601 date string'],
        ['ebrt_ott_days', 'EBRT Overall Treatment Time (OTT)', 'Integer (Days)', 'External Beam Radiotherapy', 'Elapsed days from EBRT start to EBRT end inclusive: (end_date - start_date + 1)', 'Integer days (e.g. 35)'],
        ['ebrt_treatment_status', 'EBRT Treatment Status', 'Categorical', 'External Beam Radiotherapy', 'Compliance and completion status of EBRT course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['ebrt_reason', 'Reason for EBRT Interruption / Discontinuation', 'Text', 'External Beam Radiotherapy', 'Reason code and remarks if EBRT was not started, interrupted, or stopped early', 'Toxicity, Interruption, Machine breakdown, Medical unfit, Patient default'],
        ['ebrt_is_approved', 'EBRT Course Approved', 'Binary Indicator', 'External Beam Radiotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],
        ['concurrent_chemo_given', 'Concurrent Chemotherapy Given', 'Binary Indicator', 'External Beam Radiotherapy', 'Whether concurrent radiosensitizing chemotherapy was administered', '1 = Yes, 0 = No'],
        ['concurrent_chemo_regimen', 'Concurrent Chemotherapy Regimen', 'Text', 'External Beam Radiotherapy', 'Chemotherapy agent used for concurrent radiosensitization', 'Weekly Cisplatin (40 mg/m²), Carboplatin, Other'],
        ['concurrent_chemo_cycles', 'Concurrent Chemo Cycles Administered', 'Integer', 'External Beam Radiotherapy', 'Number of weekly radiosensitizing cycles completed', 'Integer (e.g. 5)'],

        # 6. Brachytherapy & Radiobiology EQD2
        ['brachy_given', 'Brachytherapy Administered', 'Binary Indicator', 'Brachytherapy & Dosimetry', 'Whether brachytherapy course was administered', '1 = Yes, 0 = No'],
        ['brachy_source', 'Brachytherapy Radiation Source', 'Categorical', 'Brachytherapy & Dosimetry', 'Radioactive source used for HDR afterloading', 'Ir-192 HDR, Co-60 HDR, Other'],
        ['brachy_dosing_system', 'Brachytherapy Dosing System', 'Categorical', 'Brachytherapy & Dosimetry', 'Dosimetric specification system', 'HR-CTV D90 (GEC-ESTRO), Point A (Manchester), ICRU 38'],
        ['brachy_prescription_dose_gy', 'Brachytherapy Dose per Fraction', 'Numeric (Gy)', 'Brachytherapy & Dosimetry', 'Prescription dose per fraction in Gray', 'Numeric float (e.g. 7.0, 7.5)'],
        ['brachy_fractions_planned', 'Brachytherapy Fractions Planned', 'Integer', 'Brachytherapy & Dosimetry', 'Number of planned brachytherapy fractions', 'Integer (e.g. 2, 3, 4)'],
        ['brachy_fractions_delivered', 'Brachytherapy Fractions Delivered', 'Integer', 'Brachytherapy & Dosimetry', 'Total number of brachytherapy fractions successfully delivered', 'Integer (e.g. 2, 3, 4)'],
        ['brachy_start_date', 'Brachytherapy Start Date', 'Date (YYYY-MM-DD)', 'Brachytherapy & Dosimetry', 'Date of first brachytherapy applicator insertion/fraction', 'ISO-8601 date string'],
        ['brachy_end_date', 'Brachytherapy Completion Date', 'Date (YYYY-MM-DD)', 'Brachytherapy & Dosimetry', 'Date of final brachytherapy fraction delivery', 'ISO-8601 date string'],
        ['total_ott_days', 'Total Overall Treatment Time (EBRT to Brachy)', 'Integer (Days)', 'Brachytherapy & Dosimetry', 'Total calendar days from first EBRT fraction to last Brachytherapy fraction inclusive: (brachy_end - ebrt_start + 1). Clinical benchmark <= 56 days (8 weeks)', 'Integer days (e.g. 49)'],
        ['cumul_hrctv_d90_eqd2', 'Cumulative HR-CTV D90 EQD2 (Tumour)', 'Numeric (Gy₁₀)', 'Brachytherapy & Dosimetry', 'Total Equivalent Dose in 2 Gy fractions to tumour (EBRT + Brachytherapy) computed using Linear-Quadratic model with α/β = 10 Gy. Clinical goal >= 85 Gy₁₀', 'Numeric float (e.g. 87.5)'],
        ['cumul_bladder_2cc_eqd2', 'Cumulative Bladder D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of bladder (EBRT + Brachytherapy) with α/β = 3 Gy. Constraint < 90 Gy₃', 'Numeric float (e.g. 78.2)'],
        ['cumul_rectum_2cc_eqd2', 'Cumulative Rectum D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of rectum (EBRT + Brachytherapy) with α/β = 3 Gy. Constraint < 75 Gy₃', 'Numeric float (e.g. 68.4)'],
        ['cumul_sigmoid_2cc_eqd2', 'Cumulative Sigmoid D2cc EQD2', 'Numeric (Gy₃)', 'Brachytherapy & Dosimetry', 'Total EQD2 to most exposed 2 cm³ of sigmoid colon with α/β = 3 Gy. Constraint < 75 Gy₃', 'Numeric float (e.g. 64.1)'],
        ['brachy_treatment_status', 'Brachytherapy Treatment Status', 'Categorical', 'Brachytherapy & Dosimetry', 'Compliance and completion status of brachytherapy course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['brachy_reason', 'Reason for Brachytherapy Interruption / Discontinuation', 'Text', 'Brachytherapy & Dosimetry', 'Clinical reason if brachytherapy was not started, held, or stopped', 'Medical unfit, Anatomical constraint, Patient refusal, Toxicity'],
        ['brachy_is_approved', 'Brachytherapy Course Approved', 'Binary Indicator', 'Brachytherapy & Dosimetry', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 7. Adjuvant Chemotherapy
        ['adjuvant_chemo_given', 'Adjuvant Chemotherapy Administered', 'Binary Indicator', 'Adjuvant Chemotherapy', 'Whether post-radiation adjuvant systemic chemotherapy was administered', '1 = Yes, 0 = No'],
        ['adjuvant_regimen', 'Adjuvant Chemotherapy Regimen', 'Text', 'Adjuvant Chemotherapy', 'Adjuvant systemic drug regimen', 'Paclitaxel + Carboplatin, Other'],
        ['adjuvant_planned_cycles', 'Adjuvant Cycles Planned', 'Integer', 'Adjuvant Chemotherapy', 'Number of adjuvant cycles prescribed', 'Integer (e.g. 4)'],
        ['adjuvant_received_cycles', 'Adjuvant Cycles Delivered', 'Integer', 'Adjuvant Chemotherapy', 'Number of adjuvant cycles delivered', 'Integer (e.g. 4)'],
        ['adjuvant_treatment_status', 'Adjuvant Chemo Treatment Status', 'Categorical', 'Adjuvant Chemotherapy', 'Compliance and completion status of adjuvant course', 'PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED'],
        ['adjuvant_reason', 'Reason for Adjuvant Interruption / Discontinuation', 'Text', 'Adjuvant Chemotherapy', 'Reason code and remarks if adjuvant chemotherapy was not started or stopped early', 'Toxicity, Neuropathy, Patient refusal, Progression'],
        ['adjuvant_is_approved', 'Adjuvant Course Approved', 'Binary Indicator', 'Adjuvant Chemotherapy', 'Formal senior consultant electronic sign-off status', '1 = Approved, 0 = Draft'],

        # 8. Follow-Up, Recurrence & Vital Status
        ['followup_visits_count', 'Number of Follow-Up Encounters', 'Integer', 'Follow-Up & Recurrence', 'Total number of documented follow-up surveillance clinic/proxy visits', 'Integer (e.g. 4)'],
        ['last_followup_date', 'Date of Last Follow-Up Contact', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Date of most recent clinical examination, telephone check, or proxy contact', 'ISO-8601 date string'],
        ['current_disease_status', 'Disease Status at Last Contact', 'Categorical', 'Follow-Up & Recurrence', 'Oncologic disease status assessed at last follow-up visit', 'No Evidence of Disease (NED), Stable Disease, Partial Response, Progression / Residual Disease, Lost to Follow-Up, Dead'],
        ['recurrence_detected', 'Disease Recurrence Documented', 'Binary Indicator', 'Follow-Up & Recurrence', 'Whether recurrence or disease progression was detected during surveillance', '1 = Yes, 0 = No'],
        ['date_of_recurrence', 'Date of Recurrence Confirmation', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Date when local, nodal, or distant recurrence was clinically/biochemically/radiologically confirmed', 'ISO-8601 date string'],
        ['primary_recurrence_sites', 'Anatomical Sites of Recurrence', 'Text', 'Follow-Up & Recurrence', 'Documented anatomical sites of relapse', 'Vault / Central, Pelvic Nodal, Para-aortic Nodal, Distant Visceral (Lung/Liver/Bone)'],
        ['vital_status', 'Patient Vital Status', 'Categorical', 'Follow-Up & Recurrence', 'Patient vital status at the close of observation', 'Alive - NED, Alive with Recurrence, Dead, Lost to Follow-up'],
        ['death_reported', 'Death Reported', 'Binary Indicator', 'Follow-Up & Recurrence', 'Whether patient death has been formally documented', '1 = Yes, 0 = No'],
        ['date_of_death', 'Date of Death', 'Date (YYYY-MM-DD)', 'Follow-Up & Recurrence', 'Documented date of patient death', 'ISO-8601 date string'],
        ['cause_of_death', 'Documented Cause of Death', 'Categorical', 'Follow-Up & Recurrence', 'Clinical cause of death categorized according to oncology registry standards', 'Disease related, Non-disease related, Death due to other cancer, Not known / Unspecified'],

        # 9. Statistical Survival Endpoints (SPSS / R Ready)
        ['os_status', 'Overall Survival Event Status', 'Binary Indicator (0/1)', 'Statistical Survival Endpoints', 'Event indicator for Overall Survival: 1 = Event observed (Death); 0 = Censored (Alive or Lost to Follow-up at last contact). Directly usable in R Surv(os_days, os_status)', '1 = Dead, 0 = Censored'],
        ['os_days', 'Overall Survival Time (Days)', 'Integer (Days)', 'Statistical Survival Endpoints', 'Time elapsed in days from index date (date of diagnosis/registration) to date of death or last follow-up contact', 'Integer >= 0'],
        ['os_months', 'Overall Survival Time (Months)', 'Numeric (Months)', 'Statistical Survival Endpoints', 'Overall survival time in months = os_days / 30.4375 rounded to 2 decimal places', 'Numeric float >= 0'],
        ['dfs_status', 'Disease-Free Survival Event Status', 'Binary Indicator (0/1)', 'Statistical Survival Endpoints', 'Event indicator for Disease-Free / Progression-Free Survival: 1 = Event observed (Documented recurrence or disease-related death); 0 = Censored (Disease-free at last contact). Directly usable in R Surv(dfs_days, dfs_status)', '1 = Event, 0 = Censored'],
        ['dfs_days', 'Disease-Free Survival Time (Days)', 'Integer (Days)', 'Statistical Survival Endpoints', 'Time elapsed in days from index date to date of recurrence, disease-related death, or last recurrence-free contact', 'Integer >= 0'],
        ['dfs_months', 'Disease-Free Survival Time (Months)', 'Numeric (Months)', 'Statistical Survival Endpoints', 'Disease-free survival time in months = dfs_days / 30.4375 rounded to 2 decimal places', 'Numeric float >= 0'],
    ]

    return dict_headers, dict_rows


def get_long_data_dictionary():
    """
    Returns the Codebook / Data Dictionary for the Long-Format dataset.
    Used to populate the second sheet in Excel exports.
    """
    dict_headers = [
        'variable_name',
        'variable_label',
        'data_type',
        'clinical_domain',
        'description_and_methodology',
        'coding_and_valid_values'
    ]

    dict_rows = [
        ['mr_no', 'Medical Record Number', 'Text', 'Demographics', 'Unique institutional patient identifier at Kidwai Memorial Institute of Oncology', 'Unique identifier string'],
        ['patient_name', 'Patient Full Name', 'Text', 'Demographics', 'Full legal name of the patient', 'Text string'],
        ['primary_site', 'Primary Malignancy Site', 'Categorical', 'Diagnosis & Staging', 'Primary anatomical site of gynaecological malignancy', 'Cervix, Endometrium, Ovary, Vagina, Vulva, Other'],
        ['figo_stage', 'FIGO Stage', 'Categorical', 'Diagnosis & Staging', 'FIGO stage at presentation', 'Stage I - IV string'],
        ['event_domain', 'Clinical Treatment / Surveillance Domain', 'Categorical', 'Timeline Domain', 'Clinical phase or modality of the documented event', 'NACT, EBRT, Concurrent_Chemo, Brachytherapy, Adjuvant_Chemo, Follow_Up'],
        ['course_identifier', 'Course / Episode Unique Identifier', 'Text', 'Timeline Domain', 'Unique identifier linking the event to its specific treatment or follow-up course', 'e.g. NACT-C1, EBRT-C1-Conc, Brachy-C1-S1, ADJ-C1, FU-1'],
        ['event_sequence', 'Cycle / Fraction / Visit Sequence Number', 'Integer', 'Event Properties', 'Ordinal sequence of the cycle, fraction, or follow-up visit', 'Positive integer (1, 2, 3...)'],
        ['event_date', 'Date of Event Administration', 'Date (YYYY-MM-DD)', 'Event Properties', 'Actual calendar date when drug was given, RT fraction delivered, or clinic visit conducted', 'ISO-8601 date string'],
        ['event_type_or_agent', 'Administered Agent / Applicator / Status', 'Text', 'Event Properties', 'Specific drug agent name, brachytherapy applicator, or follow-up clinical status', 'Drug name (e.g. Cisplatin, Paclitaxel), Applicator type, or status string'],
        ['administered_dose', 'Delivered Dose Amount', 'Numeric', 'Event Properties', 'Prescribed physical dose delivered during this specific cycle or fraction', 'Numeric float (e.g. 50.0, 7.0) or empty'],
        ['dose_unit', 'Dose Measurement Unit', 'Text', 'Event Properties', 'Unit of measurement for the dose', 'Gy, mg, mg/m², mg/kg'],
        ['administration_days', 'Number of Administration Days', 'Integer', 'Event Properties', 'Duration of administration in days for systemic chemotherapy cycles', 'Integer (e.g. 1, 3) or empty'],
        ['day_number', 'Day of Administration Cycle', 'Integer', 'Event Properties', 'Specific day of the multi-day protocol (e.g. Day 1, Day 8)', 'Integer or empty'],
        ['administration_route', 'Route / Guidance Method', 'Categorical', 'Event Properties', 'Route of drug administration or brachytherapy image guidance modality', 'IV, Oral, CT-guided, Ultrasound-guided, Clinic Visit'],
        ['event_status', 'Event Completion Status', 'Categorical', 'Event Properties', 'Delivery status of the specific event', 'Administered, Delivered, Completed, Not Administered'],
        ['approval_status', 'Electronic Approval Status', 'Text', 'Audit & Governance', 'Clinical consultant electronic sign-off status and approver identifier', 'Approved by [Name] / Draft / Logged'],
    ]

    return dict_headers, dict_rows

