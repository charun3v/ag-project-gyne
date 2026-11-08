import io
import hashlib
from datetime import date, datetime
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

# Python 3.8 / OpenSSL hashlib compatibility shim for ReportLab 4.x
try:
    hashlib.md5(usedforsecurity=False)
except TypeError:
    _orig_md5 = hashlib.md5
    def _compat_md5(*args, **kwargs):
        kwargs.pop('usedforsecurity', None)
        return _orig_md5(*args, **kwargs)
    hashlib.md5 = _compat_md5

try:
    import reportlab.pdfbase.pdfdoc as _pdfdoc
    _pdfdoc.md5 = hashlib.md5
except Exception:
    pass

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

from patients.models import Patient


from clinical.svg_generator import get_svg_drawing_flowable

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print total page count 'Page X of Y'
    along with running header on subsequent pages and confidentiality footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#003366"))

        # Running header on page 2 and beyond
        if self._pageNumber > 1:
            self.drawString(28, 815, "RADIATION ONCOLOGY  |  KIDWAI MEMORIAL INSTITUTE OF ONCOLOGY")
            mr_no = getattr(self, '_patient_mr', '')
            pt_name = getattr(self, '_patient_name', '')
            if mr_no:
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#555555"))
                self.drawRightString(567, 815, f"{pt_name} (MR: {mr_no}) — Clinical Summary")
            self.setStrokeColor(colors.HexColor("#b0c0d0"))
            self.setLineWidth(0.5)
            self.line(28, 810, 567, 810)

        # Running footer on every page
        self.setStrokeColor(colors.HexColor("#d0d0d0"))
        self.setLineWidth(0.5)
        self.line(28, 30, 567, 30)

        gen_time = datetime.now().strftime("%d-%b-%Y %H:%M")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#555555"))
        self.drawString(28, 20, f"Kidwai Memorial Institute of Oncology — Radiation Oncology | Confidential Medical Record | Generated: {gen_time}")
        self.drawRightString(567, 20, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def _extract_imaging_details(img):
    """Extracts structured imaging details and impression matching original MS Access layout."""
    details_parts = []
    p_det = getattr(img, 'pelvis_detail', None)
    if p_det:
        if p_det.tumour_dimension_1_cm:
            dims = [str(d) for d in [p_det.tumour_dimension_1_cm, p_det.tumour_dimension_2_cm, p_det.tumour_dimension_3_cm] if d is not None]
            details_parts.append(f"Tumour size: {' x '.join(dims)} cm")

        inv_organs = []
        if p_det.cervix_involved: inv_organs.append('Cervix')
        if p_det.uterine_corpus_involved: inv_organs.append('Uterine Corpus')
        if p_det.vaginal_involvement: inv_organs.append(f"Vagina ({p_det.vaginal_extent})" if p_det.vaginal_extent else 'Vagina')
        if inv_organs:
            details_parts.append(f"Involving: {', '.join(inv_organs)}")

        if p_det.parametrium_involved or p_det.para_left_involved or p_det.para_right_involved:
            if p_det.para_left_involved:
                details_parts.append(f"Left parametrium involved: {p_det.para_left_extent_cm or '—'} cm")
            if p_det.para_right_involved:
                details_parts.append(f"Right parametrium involved: {p_det.para_right_extent_cm or '—'} cm")

        nodes = []
        for n in p_det.nodal_stations.all():
            side_str = f"{n.side} " if n.side else ""
            station_str = str(n.nodal_station)
            parts = []
            if n.number_involved is not None: parts.append(f"{n.number_involved}")
            if n.largest_size_mm is not None: parts.append(f"largest {n.largest_size_mm} mm")
            nodes.append(f"{side_str}{station_str} nodes: {', '.join(parts)}" if parts else f"{side_str}{station_str} nodes")
        if nodes:
            details_parts.append('; '.join(nodes))

    if not details_parts and img.details:
        details_parts.append(img.details.strip())
    if getattr(img, 'imaging_findings', None) and img.imaging_findings.strip():
        details_parts.append(f"Findings: {img.imaging_findings.strip()}")

    details_str = '; '.join(details_parts) if details_parts else 'Not recorded'
    impression_str = img.impression.strip() if img.impression else (p_det.radiologist_impression.strip() if (p_det and p_det.radiologist_impression) else 'Not recorded')

    return details_str, impression_str


def build_patient_summary_pdf(patient):
    """
    Builds and returns an A4 PDF BytesIO stream for the given Patient instance.
    Adheres strictly to user clinical summary requirements:
    Header: Patient name, age, sex, MR No, diagnosis, staging.
    Below Header:
      1. Presenting complaints & clinical history
      2. Pathology details
      3. Molecular / cytogenetic details
      4. Imaging details (with dates)
      5. Treatment details:
         - NACT: given (yes/no), start/end dates, drug agents & doses
         - EBRT: total dose, fractions, start/end dates, planning dates, concurrent chemo
         - Brachy: dose & date for each fraction (Fraction 1, 2, ...), applicator, source
         - Adjuvant Chemo: start/end dates, cycles, agents
      6. Follow-up details (including follow-up imaging)
    (Blood investigations excluded per specification).
    """
    buffer = io.BytesIO()

    # A4 Dimensions: 595.27 x 841.89 pt. 28pt margins give 539.27pt printable width.
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor("#003366")
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#444444")
    )
    sec_header_style = ParagraphStyle(
        'SecHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#003366"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#222222")
    )
    table_header_style = ParagraphStyle(
        'THeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#003366")
    )
    table_cell_style = ParagraphStyle(
        'TCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#222222")
    )
    table_cell_bold = ParagraphStyle(
        'TCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#111111")
    )

    story = []

    # ---------------------------------------------------------
    # 0. HEADER BANNER: Hospital / System & Title
    # ---------------------------------------------------------
    title_dept = ParagraphStyle(
        'TitleDept',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=1
    )
    title_inst = ParagraphStyle(
        'TitleInst',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=2
    )
    title_doc = ParagraphStyle(
        'TitleDoc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#555555')
    )

    header_data = [
        [
            Paragraph("<b>Radiation Oncology</b>", title_dept),
            Paragraph(f"<b>MR No: {patient.mr_no}</b>", ParagraphStyle('MRStyle', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=colors.HexColor("#cc0000"), alignment=2))
        ],
        [
            Paragraph("<b>Kidwai Memorial Institute of Oncology</b>", title_inst),
            Paragraph(f"Report Date: {date.today().strftime('%d-%b-%Y')}", ParagraphStyle('SubRDate', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#555555"), alignment=2))
        ],
        [
            Paragraph("Gynaecological Oncology — Comprehensive Multidisciplinary Clinical Summary", title_doc),
            Paragraph(f"Reg Date: {patient.date_of_registration.strftime('%d-%b-%Y') if patient.date_of_registration else '—'}", ParagraphStyle('SubR', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#666666"), alignment=2))
        ]
    ]
    t_top = Table(header_data, colWidths=[370, 169])
    t_top.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_top)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#003366"), spaceBefore=3, spaceAfter=5))

    # ---------------------------------------------------------
    # 1. PATIENT DEMOGRAPHICS & DIAGNOSIS / STAGING HEADER CARD
    # ---------------------------------------------------------
    all_diags = list(patient.diagnoses.filter(soft_deleted=False).order_by('-is_current', 'diagnosis_sequence', '-date_of_diagnosis'))
    curr_diag = all_diags[0] if all_diags else None
    primary_site_str = str(curr_diag.primary_site) if (curr_diag and curr_diag.primary_site) else "Gynaecological Oncology"
    histology_str = str(curr_diag.histology) if (curr_diag and curr_diag.histology) else (curr_diag.histology_other if curr_diag else "—")
    grade_str = str(curr_diag.grade) if (curr_diag and curr_diag.grade) else "—"
    stage_str = curr_diag.stage_text if (curr_diag and curr_diag.stage_text) else "Not formally staged"
    tnm_str = f"T: {curr_diag.t_status or '—'}  N: {curr_diag.n_status or '—'}  M: {curr_diag.m_status or '—'}" if curr_diag else "—"
    diag_date_str = curr_diag.date_of_diagnosis.strftime('%d-%b-%Y') if (curr_diag and curr_diag.date_of_diagnosis) else "—"
    full_diag_display = curr_diag.diagnosis_description if (curr_diag and curr_diag.diagnosis_description) else f"{primary_site_str} ({histology_str})"

    demo_card_data = [
        [
            Paragraph("<strong>Patient Name:</strong>", table_cell_bold),
            Paragraph(patient.pt_name, table_cell_style),
            Paragraph("<strong>Age / Sex:</strong>", table_cell_bold),
            Paragraph(f"{patient.age or '—'} yrs / {patient.sex}", table_cell_style),
            Paragraph("<strong>Primary Consultant:</strong>", table_cell_bold),
            Paragraph(str(patient.primary_consultant) if patient.primary_consultant else "Unassigned", table_cell_style),
        ],
        [
            Paragraph("<strong>Primary Diagnosis:</strong>", table_cell_bold),
            Paragraph(full_diag_display, table_cell_style),
            Paragraph("<strong>FIGO Stage:</strong>", table_cell_bold),
            Paragraph(f"<strong>{stage_str}</strong>", ParagraphStyle('StageBadge', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#003366"))),
            Paragraph("<strong>Date of Diagnosis:</strong>", table_cell_bold),
            Paragraph(diag_date_str, table_cell_style),
        ],
        [
            Paragraph("<strong>Tumour Grade:</strong>", table_cell_bold),
            Paragraph(grade_str, table_cell_style),
            Paragraph("<strong>TNM Classification:</strong>", table_cell_bold),
            Paragraph(tnm_str, table_cell_style),
            Paragraph("<strong>Contact Phone:</strong>", table_cell_bold),
            Paragraph(f"{patient.phone}{' / ' + patient.phone_alternate if patient.phone_alternate else ''}", table_cell_style),
        ]
    ]

    t_demo = Table(demo_card_data, colWidths=[90, 135, 75, 80, 85, 74])
    t_demo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#b0c4de")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e2ec")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_demo)
    story.append(Spacer(1, 4))

    # Multi-diagnosis table if patient has multiple diagnoses
    if len(all_diags) > 1:
        story.append(Paragraph("<b>ALL RECORDED ONCOLOGIC DIAGNOSES (" + str(len(all_diags)) + ")</b>", ParagraphStyle('SubDiagHdr', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#003366"), spaceBefore=2, spaceAfter=2)))
        diag_rows = [[
            Paragraph("<b>#</b>", table_cell_bold),
            Paragraph("<b>Status</b>", table_cell_bold),
            Paragraph("<b>Site</b>", table_cell_bold),
            Paragraph("<b>Full Diagnosis</b>", table_cell_bold),
            Paragraph("<b>Histology</b>", table_cell_bold),
            Paragraph("<b>Grade</b>", table_cell_bold),
            Paragraph("<b>Stage</b>", table_cell_bold),
            Paragraph("<b>Date</b>", table_cell_bold),
        ]]
        for idx, d in enumerate(all_diags, 1):
            diag_rows.append([
                Paragraph(str(idx), table_cell_style),
                Paragraph("⭐ Primary" if d.is_current else f"Secondary #{d.diagnosis_sequence}", table_cell_style),
                Paragraph(str(d.primary_site) if d.primary_site else "—", table_cell_style),
                Paragraph(d.diagnosis_description or "—", table_cell_style),
                Paragraph(str(d.histology or d.histology_other or "—"), table_cell_style),
                Paragraph(str(d.grade) if d.grade else "—", table_cell_style),
                Paragraph(f"Stage {d.stage_text}" if d.stage_text else "—", table_cell_style),
                Paragraph(d.date_of_diagnosis.strftime('%d-%b-%Y') if d.date_of_diagnosis else "—", table_cell_style),
            ])
        t_all_diags = Table(diag_rows, colWidths=[18, 62, 65, 145, 95, 60, 45, 49])
        t_all_diags.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#b0c4de")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e2ec")),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_all_diags)
        story.append(Spacer(1, 4))

    # ---------------------------------------------------------
    # 2. PRESENTING COMPLAINTS & CLINICAL HISTORY
    # ---------------------------------------------------------
    story.append(Paragraph("1. PRESENTING COMPLAINTS & CLINICAL HISTORY", sec_header_style))
    hist = patient.histories.filter(soft_deleted=False).order_by('-snapshot_date').first()
    
    complaints = []
    if hist:
        if hist.bleeding_pv: complaints.append("Bleeding P/V")
        if hist.water_discharge_pv: complaints.append("Watery discharge P/V")
        if hist.dyspareunia: complaints.append("Dyspareunia")
        if hist.loin_pain: complaints.append("Loin / flank pain")
    
    complaints_str = ", ".join(complaints) if complaints else "No specific cardinal symptoms logged"
    hpi_str = hist.hpi if (hist and hist.hpi) else "Not documented"
    
    comorbs = []
    if hist:
        if hist.hypertension: comorbs.append("Hypertension")
        if hist.diabetic: comorbs.append("Diabetes Mellitus")
        if hist.hypothyroidism: comorbs.append("Hypothyroidism")
        if hist.seizures: comorbs.append("Seizure Disorder")
        if hist.comorbidity_others and hist.comorbidity_notes: comorbs.append(hist.comorbidity_notes)
    comorbs_str = ", ".join(comorbs) if comorbs else "None reported"

    prior_surg = hist.previous_surgery_details if (hist and hist.previous_surgery and hist.previous_surgery_details) else ("Prior surgery logged" if (hist and hist.previous_surgery) else "None")
    prior_rt = hist.prior_radiation_details if (hist and hist.prior_radiation and hist.prior_radiation_details) else ("Prior radiotherapy reported" if (hist and hist.prior_radiation) else "None")

    history_table_data = [
        [
            Paragraph("<strong>Presenting Complaints:</strong>", table_cell_bold),
            Paragraph(complaints_str, table_cell_style),
            Paragraph("<strong>Comorbidities:</strong>", table_cell_bold),
            Paragraph(comorbs_str, table_cell_style),
        ],
        [
            Paragraph("<strong>History of Illness:</strong>", table_cell_bold),
            Paragraph(hpi_str, table_cell_style),
            Paragraph("<strong>Prior Surgeries / RT:</strong>", table_cell_bold),
            Paragraph(f"Surgery: {prior_surg}; RT: {prior_rt}", table_cell_style),
        ]
    ]
    t_hist = Table(history_table_data, colWidths=[105, 175, 100, 159])
    t_hist.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#f8f9fa")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_hist)
    story.append(Spacer(1, 4))

    # Clinical Pelvic Examination Findings & IBS Diagram
    latest_enc = patient.encounters.filter(soft_deleted=False).order_by('-encounter_date').first()
    if latest_enc:
        para_s = "Absent"
        if latest_enc.parametrial_invasion or latest_enc.para_left or latest_enc.para_right:
            sides = []
            if latest_enc.para_left:
                sides.append(f"Left ({latest_enc.para_extent_left_cm or '—'} cm)" if latest_enc.para_extent_left_cm else "Left")
            if latest_enc.para_right:
                sides.append(f"Right ({latest_enc.para_extent_right_cm or '—'} cm)" if latest_enc.para_extent_right_cm else "Right")
            para_s = f"Present: {', '.join(sides)}" if sides else "Present"

        dims = [f"{d} cm" for d in [latest_enc.tumour_size_cm, latest_enc.tumour_size_2_cm, getattr(latest_enc, 'tumour_size_3_cm', None)] if d is not None]
        t_dim = " × ".join(dims) if dims else "—"

        exam_table_data = [
            [
                Paragraph("<strong>Clinical Pelvic Exam:</strong>", table_cell_bold),
                Paragraph(f"Date: {latest_enc.encounter_date or '—'} | ECOG: {latest_enc.ecog or '—'} | Height: {latest_enc.height or '—'}cm | Weight: {latest_enc.weight or '—'}kg", table_cell_style),
                Paragraph("<strong>Tumour Size:</strong>", table_cell_bold),
                Paragraph(t_dim, table_cell_style),
            ],
            [
                Paragraph("<strong>Parametrial Extent:</strong>", table_cell_bold),
                Paragraph(para_s, table_cell_style),
                Paragraph("<strong>Organ Invasion:</strong>", table_cell_bold),
                Paragraph(f"Rectum: {'Inv' if latest_enc.rectal_invasion else 'Clear'}; Bladder: {'Inv' if latest_enc.bladder_invasion else 'Clear'}", table_cell_style),
            ]
        ]
        t_exam = Table(exam_table_data, colWidths=[105, 175, 100, 159])
        t_exam.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#f8f9fa")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_exam)
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 2))

    # ---------------------------------------------------------
    # 2. HISTOPATHOLOGY DETAILS
    # ---------------------------------------------------------
    story.append(Paragraph("2. HISTOPATHOLOGY DETAILS", sec_header_style))
    path_reports = patient.pathology_reports.filter(soft_deleted=False).order_by('-path_date')
    if path_reports.exists():
        path_table_data = [
            [
                Paragraph("Date", table_header_style),
                Paragraph("Specimen / Site", table_header_style),
                Paragraph("Type / Lab Ref", table_header_style),
                Paragraph("Histopathologic Findings & Impression", table_header_style),
            ]
        ]
        for pr in path_reports:
            site_info = str(pr.biopsy_site) if pr.biopsy_site else (str(pr.fnac_site) if pr.fnac_site else "—")
            spec_info = f"{str(pr.specimen) if pr.specimen else 'Specimen'} ({site_info})"
            type_ref = f"{str(pr.path_type) if pr.path_type else 'Biopsy'}{' | ' + pr.lab_reference_no if pr.lab_reference_no else ''}"
            desc = pr.impression or pr.details or "No details logged"
            path_table_data.append([
                Paragraph(pr.path_date.strftime('%d-%b-%Y') if pr.path_date else '—', table_cell_style),
                Paragraph(spec_info, table_cell_style),
                Paragraph(type_ref, table_cell_style),
                Paragraph(desc, table_cell_style),
            ])
        t_path = Table(path_table_data, colWidths=[65, 125, 110, 239])
        t_path.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_path)
    else:
        story.append(Paragraph("<em>No histopathology reports recorded for this patient.</em>", body_style))
    story.append(Spacer(1, 6))

    # ---------------------------------------------------------
    # 4. MOLECULAR / CYTOGENETIC DETAILS
    # ---------------------------------------------------------
    story.append(Paragraph("3. MOLECULAR & CYTOGENETIC PROFILING", sec_header_style))
    mol_tests = patient.molecular_tests.filter(soft_deleted=False).prefetch_related('results__marker').order_by('-test_date')
    if mol_tests.exists():
        mol_table_data = [
            [
                Paragraph("Date", table_header_style),
                Paragraph("Test Modality", table_header_style),
                Paragraph("Specimen / Testing Lab", table_header_style),
                Paragraph("Biomarker Results & Clinical Impression", table_header_style),
            ]
        ]
        for mt in mol_tests:
            markers_list = []
            for r in mt.results.all():
                val = r.result_value or (str(r.result_numeric) if r.result_numeric is not None else "")
                markers_list.append(f"<strong>{r.marker.marker_name}:</strong> {val} ({r.result_status or 'Logged'})")
            markers_str = "<br/>".join(markers_list) if markers_list else ""
            if mt.impression:
                markers_str += f"<br/><em>Impression: {mt.impression}</em>" if markers_str else mt.impression

            mol_table_data.append([
                Paragraph(mt.test_date.strftime('%d-%b-%Y') if mt.test_date else '—', table_cell_style),
                Paragraph(str(mt.molecular_type) if mt.molecular_type else "Molecular Test", table_cell_style),
                Paragraph(f"{str(mt.specimen) if mt.specimen else 'Tissue'}{' | ' + mt.testing_lab if mt.testing_lab else ''}", table_cell_style),
                Paragraph(markers_str or "No biomarker results logged", table_cell_style),
            ])
        t_mol = Table(mol_table_data, colWidths=[65, 110, 125, 239])
        t_mol.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_mol)
    else:
        story.append(Paragraph("<em>No molecular / cytogenetic investigations recorded for this patient.</em>", body_style))
    story.append(Spacer(1, 6))

    # ---------------------------------------------------------
    # 5. IMAGING DETAILS (WITH DATE) - Non-Table Layout
    # ---------------------------------------------------------
    story.append(Paragraph("4. IMAGING & RADIOLOGY INVESTIGATIONS", sec_header_style))
    imaging_studies = patient.imaging_studies.filter(soft_deleted=False).order_by('-imaging_date')
    if imaging_studies.exists():
        for img in imaging_studies:
            mod_name = str(img.imaging_type) if img.imaging_type else (img.other_modality or "Imaging")
            site_name = img.sites_display
            dt_str = img.imaging_date.strftime('%d-%b-%Y') if img.imaging_date else '—'
            d_str, imp_str = _extract_imaging_details(img)

            img_block = (
                f"<b>{dt_str} {mod_name} ({site_name})</b><br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Details:</b> {d_str}<br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Impression:</b> {imp_str}"
            )
            story.append(Paragraph(img_block, table_cell_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("<em>No imaging / radiology studies recorded for this patient.</em>", body_style))
    story.append(Spacer(1, 4))

    # ---------------------------------------------------------
    # 6. ONCOLOGY TREATMENT DETAILS
    # ---------------------------------------------------------
    story.append(Paragraph("5. ONCOLOGY TREATMENT DETAILS", sec_header_style))

    # A. NACT (Neoadjuvant Chemotherapy) - Plain Text Readable Summary
    nact_course = patient.nact_courses.filter(soft_deleted=False).first()
    nact_given = bool(nact_course and nact_course.nact_received)
    
    if nact_given:
        # Determine start and end date
        start_d_val = nact_course.nact_start_date
        end_d_val = nact_course.nact_end_date
        cycles = nact_course.cycles.all().order_by('cycle_date', 'cycle_number')
        if not start_d_val and cycles.exists():
            start_d_val = cycles.first().cycle_date
        if not end_d_val and cycles.exists():
            end_d_val = cycles.last().cycle_date

        start_d = start_d_val.strftime('%d-%b-%Y') if start_d_val else "—"
        end_d = end_d_val.strftime('%d-%b-%Y') if end_d_val else "—"
        
        reg_name = str(nact_course.chemo_regimen) if nact_course.chemo_regimen else "NACT"
        freq_str = f"Every {nact_course.cycle_frequency_days} days" if nact_course.cycle_frequency_days else "—"
        resp_name = str(nact_course.response_to_nact) if nact_course.response_to_nact else "Evaluated"
        post_nact_stage_val = nact_course.post_nact_stage or "—"

        nact_lines = [
            f"<b>A. Neoadjuvant Chemotherapy (NACT):</b> <font color='#2e7d32'><b>YES — Administered</b></font><br/>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Regimen:</b> {reg_name} &nbsp;|&nbsp; "
            f"<b>Frequency:</b> {freq_str} &nbsp;|&nbsp; "
            f"<b>Cycles:</b> {nact_course.received_cycles} administered / {nact_course.planned_cycles} planned &nbsp;|&nbsp; "
            f"<b>Dates:</b> {start_d} to {end_d} &nbsp;|&nbsp; "
            f"<b>Response:</b> {resp_name} &nbsp;|&nbsp; "
            f"<b>Post NACT staging:</b> {post_nact_stage_val}"
        ]

        if cycles.exists():
            for cyc in cycles:
                c_date = cyc.cycle_date.strftime('%d-%b-%Y') if cyc.cycle_date else '—'
                drug_items = []
                for drg in cyc.drugs.all():
                    d_agent = drg.chemo_agent.agent_name if drg.chemo_agent else "Drug"
                    d_dose = f"{drg.dose:g}" if isinstance(drg.dose, float) and drg.dose.is_integer() else f"{drg.dose or ''}"
                    d_unit = drg.dose_unit.unit_name if drg.dose_unit else 'mg'
                    d_route = drg.chemo_route.route_name if drg.chemo_route else "IV Infusion"
                    d_days = f"{drg.no_of_days} day{'s' if drg.no_of_days and drg.no_of_days > 1 else ''}"
                    d_day_admin = f"Day {drg.day_of_administration}" if drg.day_of_administration else "Day 1"
                    drug_items.append(f"{d_agent} {d_dose} {d_unit} ({d_day_admin}, {d_days}, {d_route})")
                
                drugs_str = "; ".join(drug_items) if drug_items else "No drug details recorded"
                status_str = f" [{cyc.cycle_status}]" if cyc.cycle_status else ""
                nact_lines.append(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;• <b>Cycle #{cyc.cycle_number} ({c_date}):</b> {drugs_str}{status_str}"
                )
        else:
            nact_lines.append("&nbsp;&nbsp;&nbsp;&nbsp;<em>No specific cycle administration records logged.</em>")

        t_nact_box = Table([[Paragraph("<br/>".join(nact_lines), table_cell_style)]], colWidths=[539])
        t_nact_box.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fafffa")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_nact_box)
    else:
        story.append(Table([[Paragraph("<strong>A. NACT Administered:</strong> NO (Not Given / Not Indicated)", table_cell_style)]], colWidths=[539]))
    story.append(Spacer(1, 4))

    # B. EBRT (External Beam Radiotherapy)
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False).order_by('course_sequence')
    if ebrt_courses.exists():
        for eb in ebrt_courses:
            eb_start = eb.ebrt_start_date.strftime('%d-%b-%Y') if eb.ebrt_start_date else "—"
            eb_end = eb.ebrt_end_date.strftime('%d-%b-%Y') if eb.ebrt_end_date else "—"
            eb_dose = f"{eb.total_dose_gy or '—'} Gy"
            eb_fx = f"{eb.total_fractions or '—'} fractions ({eb.dose_per_fraction_gy or '—'} Gy/#)"

            # EBRT OTT (inclusive of both dates: end - start + 1)
            if eb.ebrt_start_date and eb.ebrt_end_date:
                eb_days = (eb.ebrt_end_date - eb.ebrt_start_date).days + 1
                eb_ott_str = f"<b>{eb_days} days</b> ({eb.ebrt_start_date.strftime('%d-%b')} to {eb.ebrt_end_date.strftime('%d-%b-%Y')})"
                if eb.treatment_interrupted and eb.interruption_days:
                    eb_ott_str += f" [{eb.interruption_days}d lost]"
            else:
                eb_ott_str = "—"
            
            # Check concurrent chemotherapy
            conc_info = "None given"
            conc_course = eb.concurrent_chemo_courses.first()
            if conc_course and conc_course.concurrent_received:
                agents_c = []
                for cyc in conc_course.cycles.all():
                    for drg in cyc.drugs.all():
                        a_name = f"{drg.chemo_agent.agent_name} {drg.dose or ''}{drg.dose_unit.unit_name if drg.dose_unit else ''}"
                        if a_name not in agents_c:
                            agents_c.append(a_name)
                conc_info = f"YES — {', '.join(agents_c) if agents_c else 'Concurrent Chemo'} ({conc_course.received_cycles} cycles delivered)"

            sim_str = eb.simulation_date.strftime('%d-%b-%Y') if eb.simulation_date else "—"
            tech_str = str(eb.ebrt_technique) if eb.ebrt_technique else '3DCRT/IMRT'
            intent_str = str(eb.ebrt_intent) if eb.ebrt_intent else 'Radical'
            sites_str = ", ".join([s.ebrt_site.site_name for s in eb.sites.all()]) if eb.sites.exists() else "Whole Pelvis"

            ebrt_rows = [
                [
                    Paragraph(f"<strong>B. EBRT Course #{eb.course_sequence}:</strong>", table_cell_bold),
                    Paragraph(f"<strong>Total Dose:</strong> {eb_dose} | <strong>Fractions:</strong> {eb_fx} | <strong>Technique:</strong> {tech_str} ({intent_str})", table_cell_style),
                    Paragraph("<strong>Start Date:</strong>", table_cell_bold),
                    Paragraph(eb_start, table_cell_style),
                    Paragraph("<strong>End Date:</strong>", table_cell_bold),
                    Paragraph(eb_end, table_cell_style),
                ],
                [
                    Paragraph("<strong>Planning & Chemo:</strong>", table_cell_bold),
                    Paragraph(f"Sim: {sim_str} | Sites: {sites_str} | Concurrent Chemo: {conc_info}", table_cell_style),
                    Paragraph("<strong>EBRT OTT:</strong>", table_cell_bold),
                    Paragraph(eb_ott_str, table_cell_style),
                    "", ""
                ]
            ]
            t_eb = Table(ebrt_rows, colWidths=[105, 160, 65, 75, 55, 79])
            t_eb.setStyle(TableStyle([
                ('SPAN', (3, 1), (5, 1)),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8faff")),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t_eb)
            story.append(Spacer(1, 4))
    else:
        story.append(Table([[Paragraph("<strong>B. EBRT Course:</strong>", table_cell_bold), Paragraph("NO (No EBRT Course recorded)", table_cell_style)]], colWidths=[110, 429]))
        story.append(Spacer(1, 4))

    # C. Brachytherapy (Brachy)
    brachy_courses = patient.brachy_courses.filter(soft_deleted=False).order_by('course_sequence')
    if brachy_courses.exists():
        for bc in brachy_courses:
            # Determine start and end date of brachy
            first_brachy_date = None
            last_brachy_date = None
            for s in bc.sessions.all():
                if s.session_date:
                    if not first_brachy_date or s.session_date < first_brachy_date:
                        first_brachy_date = s.session_date
                    if not last_brachy_date or s.session_date > last_brachy_date:
                        last_brachy_date = s.session_date
                for f in s.fractions.all():
                    if f.fraction_date:
                        if not first_brachy_date or f.fraction_date < first_brachy_date:
                            first_brachy_date = f.fraction_date
                        if not last_brachy_date or f.fraction_date > last_brachy_date:
                            last_brachy_date = f.fraction_date
            if not first_brachy_date and bc.brachy_start_date:
                first_brachy_date = bc.brachy_start_date
            if not last_brachy_date and bc.brachy_end_date:
                last_brachy_date = bc.brachy_end_date

            bc_start_str = first_brachy_date.strftime('%d-%b-%Y') if first_brachy_date else "—"
            bc_end_str = last_brachy_date.strftime('%d-%b-%Y') if last_brachy_date else "—"
            if first_brachy_date and last_brachy_date:
                bc_days = (last_brachy_date - first_brachy_date).days + 1
                bc_ott_str = f"<b>{bc_days} days</b> ({first_brachy_date.strftime('%d-%b')} to {last_brachy_date.strftime('%d-%b-%Y')})"
            else:
                bc_ott_str = "—"

            dosing_str = bc.brachy_dosing.dosing_point if bc.brachy_dosing else (bc.sessions.first().brachy_dosing.dosing_point if bc.sessions.exists() and bc.sessions.first().brachy_dosing else "HR-CTV D90 (GEC-ESTRO)")
            source_str = bc.brachy_source.source_name if bc.brachy_source else (bc.sessions.first().brachy_source.source_name if bc.sessions.exists() and bc.sessions.first().brachy_source else "HDR Ir-192")
            centre_str = bc.treatment_centre.centre_name if bc.treatment_centre else "KMIO"

            # Applicator summaries
            app_summaries = []
            for s in bc.sessions.all():
                meas = []
                if s.tandem_length_cm: meas.append(f"Tandem: {s.tandem_length_cm} cm")
                if s.ovoid_diameter_mm: meas.append(f"Ovoid: {s.ovoid_diameter_mm} cm")
                if s.ring_diameter_mm: meas.append(f"Ring: {s.ring_diameter_mm} mm")
                if s.needle_count: meas.append(f"Needles: {s.needle_count}")
                meas_str = f" ({', '.join(meas)})" if meas else ""
                app_date = s.session_date.strftime('%d-%b-%Y') if s.session_date else "—"
                app_name = s.applicator.name if s.applicator else "Applicator"
                app_summaries.append(f"<b>App #{s.session_number}</b> ({app_date}): {app_name}{meas_str}")
            app_desc = "; ".join(app_summaries) if app_summaries else "Applicators logged"

            # Fractions and Physical Totals
            all_fractions = []
            tot_physical_dose = 0.0
            tot_hrctv = 0.0
            tot_rectum = 0.0
            tot_bladder = 0.0
            tot_sigmoid = 0.0

            for s in bc.sessions.all():
                for f in s.fractions.all():
                    d_val = f.dose_delivered_gy or f.prescribed_dose_gy or 0.0
                    tot_physical_dose += d_val
                    if f.hrctv_d90_gy: tot_hrctv += f.hrctv_d90_gy
                    if f.rectum_dose_2cc_gy: tot_rectum += f.rectum_dose_2cc_gy
                    if f.bladder_dose_2cc_gy: tot_bladder += f.bladder_dose_2cc_gy
                    if f.sigmoid_dose_2cc_gy: tot_sigmoid += f.sigmoid_dose_2cc_gy

                    f_dt = f.fraction_date.strftime('%d-%b-%Y') if f.fraction_date else "—"
                    d_parts = [f"{d_val} Gy"]
                    if f.hrctv_d90_gy: d_parts.append(f"D90: {f.hrctv_d90_gy}Gy")
                    if f.rectum_dose_2cc_gy: d_parts.append(f"R2cc: {f.rectum_dose_2cc_gy}Gy")
                    if f.bladder_dose_2cc_gy: d_parts.append(f"B2cc: {f.bladder_dose_2cc_gy}Gy")
                    if f.sigmoid_dose_2cc_gy: d_parts.append(f"Sig2cc: {f.sigmoid_dose_2cc_gy}Gy")
                    all_fractions.append((f.overall_fraction_number, f"<strong>Fx #{f.overall_fraction_number}:</strong> {' | '.join(d_parts)} ({f_dt})"))

            all_fractions.sort(key=lambda x: x[0])
            fx_formatted_str = ";  ".join([x[1] for x in all_fractions]) if all_fractions else "Fractions in progress / pending log"

            num_apps = bc.sessions.count()
            planned_apps = bc.total_applications_planned or num_apps
            planned_fx = bc.total_fractions_planned or len(all_fractions)

            brachy_rows = [
                [
                    Paragraph(f"<strong>C. Brachytherapy Course #{bc.course_sequence}:</strong>", table_cell_bold),
                    Paragraph(f"<strong>Dosing:</strong> {dosing_str} | <strong>Source:</strong> {source_str} | <strong>Facility:</strong> {centre_str}", table_cell_style),
                    Paragraph("<strong>Start Date:</strong>", table_cell_bold),
                    Paragraph(bc_start_str, table_cell_style),
                    Paragraph("<strong>End Date:</strong>", table_cell_bold),
                    Paragraph(bc_end_str, table_cell_style),
                ],
                [
                    Paragraph("<strong>Applications & Fractions:</strong>", table_cell_bold),
                    Paragraph(f"Applications: <b>{num_apps}/{planned_apps} planned</b> | Fractions: <b>{len(all_fractions)}/{planned_fx} planned</b>", table_cell_style),
                    Paragraph("<strong>Brachy OTT:</strong>", table_cell_bold),
                    Paragraph(bc_ott_str, table_cell_style),
                    "", ""
                ],
                [
                    Paragraph("<strong>Applicators:</strong>", table_cell_bold),
                    Paragraph(app_desc, table_cell_style),
                    "", "", "", ""
                ],
                [
                    Paragraph("<strong>Delivered Fractions:</strong>", table_cell_bold),
                    Paragraph(fx_formatted_str, table_cell_style),
                    "", "", "", ""
                ],
                [
                    Paragraph("<strong>Physical Totals:</strong>", table_cell_bold),
                    Paragraph(f"Delivered Dose: <b>{tot_physical_dose:.1f} Gy</b> | HR-CTV D90: <b>{tot_hrctv:.1f} Gy</b> | Rectum 2cc: <b>{tot_rectum:.1f} Gy</b> | Bladder 2cc: <b>{tot_bladder:.1f} Gy</b> | Sigmoid 2cc: <b>{tot_sigmoid:.1f} Gy</b>", table_cell_style),
                    "", "", "", ""
                ]
            ]
            t_bc = Table(brachy_rows, colWidths=[105, 160, 65, 75, 55, 79])
            t_bc.setStyle(TableStyle([
                ('SPAN', (3, 1), (5, 1)),
                ('SPAN', (1, 2), (5, 2)),
                ('SPAN', (1, 3), (5, 3)),
                ('SPAN', (1, 4), (5, 4)),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fffdf5")),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t_bc)
            story.append(Spacer(1, 4))
    else:
        story.append(Table([[Paragraph("<strong>C. Brachytherapy:</strong>", table_cell_bold), Paragraph("NO (No Brachytherapy recorded)", table_cell_style)]], colWidths=[110, 429]))
        story.append(Spacer(1, 4))

    # --- D. Radiation Oncology Overall Treatment Time (OTT) & Cumulative Radiobiological Dosimetry (EQD2) ---
    if ebrt_courses.exists() or brachy_courses.exists():
        first_eb = ebrt_courses.first() if ebrt_courses.exists() else None
        
        # 1. Total Treatment OTT: Date of last fraction of Brachy - EBRT start date + 1, inclusive
        last_brachy_date = None
        for bc in brachy_courses:
            for s in bc.sessions.all():
                if s.session_date:
                    if not last_brachy_date or s.session_date > last_brachy_date:
                        last_brachy_date = s.session_date
                for fx in s.fractions.all():
                    if fx.fraction_date:
                        if not last_brachy_date or fx.fraction_date > last_brachy_date:
                            last_brachy_date = fx.fraction_date
            if not last_brachy_date and bc.brachy_end_date:
                last_brachy_date = bc.brachy_end_date

        if first_eb and first_eb.ebrt_start_date and last_brachy_date:
            tot_days = (last_brachy_date - first_eb.ebrt_start_date).days + 1
            total_ott_val = f"<strong>{tot_days} days</strong>"
        elif first_eb and first_eb.ebrt_start_date and first_eb.ebrt_end_date:
            eb_days = (first_eb.ebrt_end_date - first_eb.ebrt_start_date).days + 1
            total_ott_val = f"<strong>{eb_days} days</strong>"
        else:
            total_ott_val = "—"

        # 2. Cumulative EQD2 calculations (Tumour a/b=10, OARs a/b=3)
        cum_tumor_eqd2 = 0.0
        cum_rectum_eqd2 = 0.0
        cum_bladder_eqd2 = 0.0
        cum_sigmoid_eqd2 = 0.0

        for eb in ebrt_courses:
            if eb.total_dose_gy and eb.total_fractions and eb.total_fractions > 0:
                d_eb = eb.total_dose_gy / eb.total_fractions
                cum_tumor_eqd2 += eb.total_dose_gy * ((d_eb + 10.0) / 12.0)
                cum_rectum_eqd2 += eb.total_dose_gy * ((d_eb + 3.0) / 5.0)
                cum_bladder_eqd2 += eb.total_dose_gy * ((d_eb + 3.0) / 5.0)
                cum_sigmoid_eqd2 += eb.total_dose_gy * ((d_eb + 3.0) / 5.0)

        for bc in brachy_courses:
            ab_t = bc.alpha_beta_tumor or 10.0
            ab_b = bc.alpha_beta_bladder or 3.0
            ab_r = bc.alpha_beta_rectum or 3.0
            ab_s = bc.alpha_beta_sigmoid or 3.0
            for s in bc.sessions.all():
                for fx in s.fractions.all():
                    d_del = fx.dose_delivered_gy or fx.prescribed_dose_gy or 0.0
                    hrctv = fx.hrctv_d90_gy if fx.hrctv_d90_gy is not None else d_del
                    if hrctv and (2.0 + ab_t) > 0:
                        cum_tumor_eqd2 += hrctv * ((hrctv + ab_t) / (2.0 + ab_t))
                    if fx.rectum_dose_2cc_gy and (2.0 + ab_r) > 0:
                        cum_rectum_eqd2 += fx.rectum_dose_2cc_gy * ((fx.rectum_dose_2cc_gy + ab_r) / (2.0 + ab_r))
                    if fx.bladder_dose_2cc_gy and (2.0 + ab_b) > 0:
                        cum_bladder_eqd2 += fx.bladder_dose_2cc_gy * ((fx.bladder_dose_2cc_gy + ab_b) / (2.0 + ab_b))
                    if fx.sigmoid_dose_2cc_gy and (2.0 + ab_s) > 0:
                        cum_sigmoid_eqd2 += fx.sigmoid_dose_2cc_gy * ((fx.sigmoid_dose_2cc_gy + ab_s) / (2.0 + ab_s))

        eqd2_str = (
            f"Tumour: <font color='#166534'><b>{cum_tumor_eqd2:.1f} Gy₁₀</b></font> &nbsp;|&nbsp; "
            f"Rectum 2cc: <font color='#9a3412'><b>{cum_rectum_eqd2:.1f} Gy₃</b></font> &nbsp;|&nbsp; "
            f"Bladder 2cc: <font color='#9a3412'><b>{cum_bladder_eqd2:.1f} Gy₃</b></font> &nbsp;|&nbsp; "
            f"Sigmoid (Sig) 2cc: <font color='#9a3412'><b>{cum_sigmoid_eqd2:.1f} Gy₃</b></font>"
        )

        ott_rows = [
            [
                Paragraph("<strong>D. Total Treatment OTT:</strong>", table_cell_bold),
                Paragraph(f"<font color='#003366' size='8.5'><b>{total_ott_val}</b></font>", table_cell_style),
            ],
            [
                Paragraph("<strong>Cumulative EQD2:</strong>", table_cell_bold),
                Paragraph(eqd2_str, table_cell_style),
            ]
        ]
        t_ott = Table(ott_rows, colWidths=[120, 419])
        t_ott.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor("#2e7d32")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#d5ebd5")),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_ott)
        story.append(Spacer(1, 4))

    # E. Adjuvant Chemotherapy
    adj_course = patient.adjuvant_courses.filter(soft_deleted=False).first()
    adj_given = bool(adj_course and adj_course.adjuvant_received)
    if adj_given:
        adj_start_val = None
        adj_end_val = None
        if adj_course.cycles.exists():
            adj_start_val = adj_course.cycles.order_by('cycle_date').first().cycle_date
            adj_end_val = adj_course.cycles.order_by('cycle_date').last().cycle_date

        adj_start = adj_start_val.strftime('%d-%b-%Y') if adj_start_val else "—"
        adj_end = adj_end_val.strftime('%d-%b-%Y') if adj_end_val else "—"
        adj_drugs = []
        for cyc in adj_course.cycles.all():
            for drg in cyc.drugs.all():
                d_str = f"{drg.chemo_agent.agent_name} ({drg.dose or ''} {drg.dose_unit.unit_name if drg.dose_unit else 'mg'})"
                if d_str not in adj_drugs:
                    adj_drugs.append(d_str)
        adj_drugs_str = ", ".join(adj_drugs) if adj_drugs else "Regimen drugs logged in cycles"

        adj_rows = [
            [
                Paragraph("<strong>E. Adjuvant Chemo:</strong>", table_cell_bold),
                Paragraph(f"<strong>YES</strong> ({adj_course.received_cycles} / {adj_course.planned_cycles} cycles)", table_cell_style),
                Paragraph("<strong>Start:</strong>", table_cell_bold),
                Paragraph(adj_start, table_cell_style),
                Paragraph("<strong>End:</strong>", table_cell_bold),
                Paragraph(adj_end, table_cell_style),
            ],
            [
                Paragraph("<strong>Regimen & Drugs:</strong>", table_cell_bold),
                Paragraph(f"Adjuvant: {adj_drugs_str}", table_cell_style),
                "", "", "", ""
            ]
        ]
        t_adj = Table(adj_rows, colWidths=[95, 115, 45, 80, 40, 164])
        t_adj.setStyle(TableStyle([
            ('SPAN', (1, 1), (5, 1)),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fafffa")),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_adj)
    else:
        story.append(Table([[Paragraph("<strong>E. Adjuvant Chemo:</strong>", table_cell_bold), Paragraph("NO (Not Given / Not Indicated)", table_cell_style)]], colWidths=[110, 429]))
    story.append(Spacer(1, 6))


    # ---------------------------------------------------------
    # 7. FOLLOW-UP DETAILS (INCLUDING FOLLOW-UP IMAGING)
    # ---------------------------------------------------------
    story.append(Paragraph("6. LONGITUDINAL FOLLOW-UP & SURVEILLANCE DETAILS", sec_header_style))
    followups = patient.follow_up_records.filter(soft_deleted=False).order_by('-follow_up_date')
    if followups.exists():
        fu_table_data = [
            [
                Paragraph("Visit Date", table_header_style),
                Paragraph("Contact Type", table_header_style),
                Paragraph("Vital & Disease Status", table_header_style),
                Paragraph("Recurrence Status & Surveillance Notes", table_header_style),
            ]
        ]
        for fu in followups:
            v_date = fu.follow_up_date.strftime('%d-%b-%Y') if fu.follow_up_date else "—"
            c_type = str(fu.contact_type) if fu.contact_type else "Clinic Visit"
            d_status = str(fu.disease_status) if fu.disease_status else "Status Evaluated"
            
            rec_info = []
            if fu.recurrence_detected:
                rec_site = str(fu.recurrence_site) if fu.recurrence_site else "Recurrence"
                rec_info.append(f"<strong>⚠️ RECURRENCE:</strong> {rec_site}")
                if fu.recurrence_confirmed_by: rec_info.append(f"Confirmed by: {fu.recurrence_confirmed_by}")
                if fu.recurrence_treatment_plan: rec_info.append(f"Plan: {fu.recurrence_treatment_plan}")
            else:
                rec_info.append("No recurrence detected")

            if fu.performance_notes:
                rec_info.append(fu.performance_notes)

            fu_table_data.append([
                Paragraph(v_date, table_cell_style),
                Paragraph(c_type, table_cell_style),
                Paragraph(d_status, table_cell_bold),
                Paragraph("<br/>".join(rec_info), table_cell_style),
            ])
        t_fu = Table(fu_table_data, colWidths=[65, 80, 135, 259])
        t_fu.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#c0c8d0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e6ed")),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_fu)
    else:
        story.append(Paragraph("<em>No longitudinal follow-up records logged yet.</em>", body_style))

    # Follow-Up / Surveillance Imaging Details
    # (Scans performed post-treatment or during surveillance)
    treatment_dates = []
    if nact_course and nact_course.nact_end_date: treatment_dates.append(nact_course.nact_end_date)
    for eb in ebrt_courses:
        if eb.ebrt_end_date: treatment_dates.append(eb.ebrt_end_date)
    for bc in brachy_courses:
        if bc.brachy_end_date: treatment_dates.append(bc.brachy_end_date)
    
    last_tx_date = max(treatment_dates) if treatment_dates else None
    if last_tx_date:
        surveillance_scans = patient.imaging_studies.filter(soft_deleted=False, imaging_date__gte=last_tx_date).order_by('-imaging_date')
        if surveillance_scans.exists():
            story.append(Spacer(1, 4))
            story.append(Paragraph("<strong>Surveillance & Follow-Up Imaging:</strong>", ParagraphStyle('SubSec', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#003366"))))
            for s_img in surveillance_scans:
                m_name = str(s_img.imaging_type) if s_img.imaging_type else (s_img.other_modality or "Scan")
                r_name = s_img.sites_display
                s_date = s_img.imaging_date.strftime('%d-%b-%Y') if s_img.imaging_date else '—'
                s_det, s_imp = _extract_imaging_details(s_img)
                s_html = (
                    f"<b>{s_date} {m_name} ({r_name})</b><br/>"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Details:</b> {s_det}<br/>"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Impression:</b> {s_imp}"
                )
                story.append(Paragraph(s_html, table_cell_style))
                story.append(Spacer(1, 2))

    # Attach patient meta to canvas for running header
    def make_canvas(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c._patient_mr = patient.mr_no
        c._patient_name = patient.pt_name
        return c

    doc.build(story, canvasmaker=make_canvas)
    buffer.seek(0)
    return buffer
