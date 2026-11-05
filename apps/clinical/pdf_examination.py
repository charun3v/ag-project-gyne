"""
Clinical Examination & Imaging Investigations PDF Report Generator
Kidwai Memorial Institute of Oncology — Radiation Oncology

Generates comprehensive A4 printable reports with:
- Main Header: Radiation Oncology | Kidwai Memorial Institute of Oncology
- Chronological Longitudinal Evaluations:
    1. Baseline Evaluation (Pelvic Exam, Populated IBS Anatomical Vector Diagram, Baseline Imaging)
    2. Post-NACT Reassessment (if recorded) (Pelvic Exam, Populated IBS Diagram, Restaging Imaging)
    3. Pre-Brachy Evaluation (Pelvic Exam, Populated IBS Diagram, Response Imaging)
    4. Longitudinal Follow-Up Surveillance (Visit timeline, Disease status, Surveillance Imaging)
- Populated IBS vector diagrams with light-red highlights on involved zones
- Imaging investigations formatted without tables (Modality - Site (Date) - Details - Impression)
- No blood investigations populated per clinical specification
"""

import io
import hashlib
from datetime import date, datetime, timedelta
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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.pdfgen import canvas

from patients.models import Patient
from clinical.models import Encounter, EncounterType
from clinical.svg_generator import get_svg_drawing_flowable, REGION_LABELS_MAP


class ExamNumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic 'Page X of Y' and running headers."""
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
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#003366"))

        # Running header on subsequent pages
        if self._pageNumber > 1:
            self.drawString(28, 815, "RADIATION ONCOLOGY  |  KIDWAI MEMORIAL INSTITUTE OF ONCOLOGY")
            mr_no = getattr(self, '_patient_mr', '')
            pt_name = getattr(self, '_patient_name', '')
            if mr_no:
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#555555"))
                self.drawRightString(567, 815, f"{pt_name} (MR: {mr_no}) — Clinical Examination & Imaging Report")
            self.setStrokeColor(colors.HexColor("#b0c0d0"))
            self.setLineWidth(0.5)
            self.line(28, 810, 567, 810)

        # Confidentiality footer on all pages
        self.setStrokeColor(colors.HexColor("#b0c0d0"))
        self.setLineWidth(0.5)
        self.line(28, 28, 567, 28)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#555555"))
        self.drawString(28, 18, "Kidwai Memorial Institute of Oncology — Radiation Oncology Clinical Record | Confidential Medical Record")
        self.drawRightString(567, 18, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def format_imaging_investigation(im, cell_style):
    """Formats an ImagingInvestigation into the clean non-table layout requested by clinicians."""
    mod_name = str(im.imaging_type) if im.imaging_type else "Radiology"
    site_name = str(im.imaging_site) if im.imaging_site else "Pelvis"
    dt_str = im.imaging_date.strftime('%d-%b-%Y') if im.imaging_date else '—'

    details_parts = []
    p_det = getattr(im, 'pelvis_detail', None)
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
                details_parts.append(f"Right parametrium involved: {p_det.para_left_extent_cm or '—'} cm")
            if p_det.para_right_involved:
                details_parts.append(f"Left parametrium involved: {p_det.para_right_extent_cm or '—'} cm")

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

    if not details_parts and im.details:
        details_parts.append(im.details.strip())

    details_str = '; '.join(details_parts) if details_parts else 'Not recorded'
    impression_str = im.impression.strip() if im.impression else (p_det.radiologist_impression.strip() if (p_det and p_det.radiologist_impression) else 'Not recorded')

    img_html = (
        f"<font color='#003366'><b>{dt_str} {mod_name} ({site_name})</b></font><br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Details:</b> {details_str}<br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Impression:</b> {impression_str}"
    )
    return Paragraph(img_html, cell_style)


def build_examination_investigation_pdf(patient_or_encounter):
    """
    Builds the Comprehensive Longitudinal Clinical Examination & Imaging Investigations PDF.
    Includes:
    - Baseline, Post-NACT, Pre-Brachy, and Follow-Up chronologically
    - Mapped IBS Pelvic Diagrams for each available examination
    - Chronological Imaging Investigations (only imaging, no blood tests)
    """
    if isinstance(patient_or_encounter, Encounter):
        patient = patient_or_encounter.patient
    else:
        patient = patient_or_encounter

    buf = io.BytesIO()

    # A4 printable dimensions: 595.27 x 841.89 pt. 28pt margins = 539.27pt content width.
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=36
    )

    base_styles = getSampleStyleSheet()

    title_dept = ParagraphStyle(
        'TitleDept',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=1
    )
    title_inst = ParagraphStyle(
        'TitleInst',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=2
    )
    title_doc = ParagraphStyle(
        'TitleDoc',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#555555')
    )
    sec_title = ParagraphStyle(
        'SectionTitle',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#003366'),
        spaceBefore=6,
        spaceAfter=3
    )
    sub_title = ParagraphStyle(
        'SubSectionTitle',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1a365d'),
        spaceBefore=4,
        spaceAfter=2
    )
    th_style = ParagraphStyle(
        'TH',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#003366')
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=base_styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.0,
        textColor=colors.HexColor('#222222')
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10.0,
        textColor=colors.HexColor('#222222')
    )

    story = []

    # 1. Main Header Table matching KMIO standards
    hdr_table = Table([
        [
            Paragraph("<b>Radiation Oncology</b>", title_dept),
            Paragraph(f"<b>MR No: {patient.mr_no}</b>", ParagraphStyle(
                'MRHeader', fontName='Helvetica-Bold', fontSize=12, leading=14,
                textColor=colors.HexColor('#cc0000'), alignment=2
            ))
        ],
        [
            Paragraph("<b>Kidwai Memorial Institute of Oncology</b>", title_inst),
            Paragraph(f"Report Date: {date.today().strftime('%d-%b-%Y')}", ParagraphStyle(
                'ExamDate', fontName='Helvetica', fontSize=8, leading=10,
                textColor=colors.HexColor('#555555'), alignment=2
            ))
        ],
        [
            Paragraph("Clinical Examination & Imaging Investigations Report", title_doc),
            Paragraph("Longitudinal Chronological Assessment & IBS Pelvic Diagrams", ParagraphStyle(
                'EncType', fontName='Helvetica-Bold', fontSize=8, leading=10,
                textColor=colors.HexColor('#003366'), alignment=2
            ))
        ]
    ], colWidths=[370, 169])
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#003366'), spaceAfter=5, spaceBefore=4))

    # Current Diagnosis info
    diag = patient.diagnoses.filter(is_current=True, soft_deleted=False).first() or patient.diagnoses.filter(soft_deleted=False).first()
    if diag and diag.diagnosis_description:
        diag_str = diag.diagnosis_description
    else:
        diag_str = str(diag.primary_site) if diag and diag.primary_site else "Gynaecological Oncology"
        if diag and diag.histology:
            diag_str += f" ({diag.histology})"
        elif diag and diag.histology_other:
            diag_str += f" ({diag.histology_other})"
    other_diags_cnt = patient.diagnoses.filter(soft_deleted=False).exclude(pk=diag.pk).count() if diag else 0
    if other_diags_cnt > 0:
        diag_str += f" (+{other_diags_cnt} additional)"
    figo_str = diag.stage_text if diag and diag.stage_text else "—"
    tnm_str = f"T: {diag.t_status or '—'} N: {diag.n_status or '—'} M: {diag.m_status or '—'}" if diag else "—"

    # Patient Demographics Card
    demo_data = [
        [
            Paragraph("<b>Patient Name:</b>", th_style),
            Paragraph(str(patient.pt_name or ''), cell_bold),
            Paragraph("<b>Age / Sex:</b>", th_style),
            Paragraph(f"{patient.age or '—'} yrs / {patient.sex or 'Female'}", cell_style),
            Paragraph("<b>Primary Consultant:</b>", th_style),
            Paragraph(str(patient.primary_consultant) if patient.primary_consultant else "Unassigned", cell_style),
        ],
        [
            Paragraph("<b>Primary Diagnosis:</b>", th_style),
            Paragraph(diag_str, cell_style),
            Paragraph("<b>FIGO Stage:</b>", th_style),
            Paragraph(f"<b>{figo_str}</b>", ParagraphStyle('StageBadge', parent=cell_style, fontName='Helvetica-Bold', textColor=colors.HexColor('#003366'))),
            Paragraph("<b>TNM Staging:</b>", th_style),
            Paragraph(tnm_str, cell_style),
        ]
    ]
    t_demo = Table(demo_data, colWidths=[80, 130, 65, 85, 95, 84])
    t_demo.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#003366')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#c0d0e0')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f5fa')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f0f5fa')),
        ('BACKGROUND', (4, 0), (4, -1), colors.HexColor('#f0f5fa')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_demo)
    story.append(Spacer(1, 5))

    # Fetch Clinical Encounters & Milestones
    all_encounters = patient.encounters.filter(soft_deleted=False).select_related('encounter_type').order_by('encounter_date', 'clinical_id')
    base_enc = all_encounters.filter(encounter_type__encounter_type_name__icontains='Baseline').first() or all_encounters.first()
    postnact_enc = all_encounters.filter(encounter_type__encounter_type_name__icontains='Post-NACT').first()
    preb_enc = all_encounters.filter(encounter_type__encounter_type_name__icontains='Pre-Brachy').first()
    fu_encs = all_encounters.filter(encounter_type__encounter_type_name__icontains='Follow')
    fu_records = patient.follow_up_records.filter(soft_deleted=False).select_related('disease_status', 'contact_type').order_by('follow_up_date')

    # Treatments for chronological date boundaries
    nact_course = patient.nact_courses.filter(soft_deleted=False, nact_received=True).first()
    ebrt_course = patient.ebrt_courses.filter(soft_deleted=False).order_by('course_sequence').first()
    brachy_course = patient.brachy_courses.filter(soft_deleted=False).order_by('course_sequence').first()

    nact_start = nact_course.nact_start_date if nact_course else None
    ebrt_start = ebrt_course.ebrt_start_date if ebrt_course else None
    ebrt_end = ebrt_course.ebrt_end_date if ebrt_course else None
    last_brachy_date = None
    if brachy_course:
        for s in brachy_course.sessions.all():
            for f in s.fractions.all():
                if f.fraction_date:
                    if not last_brachy_date or f.fraction_date > last_brachy_date:
                        last_brachy_date = f.fraction_date
        if not last_brachy_date and brachy_course.brachy_end_date:
            last_brachy_date = brachy_course.brachy_end_date

    # Partition Imaging Studies chronologically into stages
    all_imaging = list(patient.imaging_studies.filter(soft_deleted=False).select_related('imaging_type', 'imaging_site').order_by('imaging_date', 'imaging_id'))
    baseline_images = []
    postnact_images = []
    prebrachy_images = []
    followup_images = []
    assigned_img_ids = set()

    for im in all_imaging:
        i_date = im.imaging_date
        if not i_date:
            baseline_images.append(im)
            assigned_img_ids.add(im.imaging_id)
            continue

        # Post-NACT window
        if nact_start and i_date >= nact_start and (not ebrt_start or i_date < ebrt_start):
            postnact_images.append(im)
            assigned_img_ids.add(im.imaging_id)
        # Pre-Brachy window (after EBRT start / around plan completion before last brachy)
        elif (ebrt_end and (ebrt_end - timedelta(days=10)) <= i_date <= (last_brachy_date or ebrt_end + timedelta(days=14))) or (preb_enc and abs((i_date - preb_enc.encounter_date).days) <= 14):
            prebrachy_images.append(im)
            assigned_img_ids.add(im.imaging_id)
        # Follow-up window (after all RT / last brachy)
        elif (last_brachy_date and i_date > last_brachy_date) or (ebrt_end and not brachy_course and i_date > ebrt_end):
            followup_images.append(im)
            assigned_img_ids.add(im.imaging_id)
        # Baseline window (prior to treatment or around baseline encounter)
        elif (nact_start and i_date < nact_start) or (ebrt_start and i_date <= ebrt_start) or (base_enc and i_date <= (base_enc.encounter_date + timedelta(days=14))):
            baseline_images.append(im)
            assigned_img_ids.add(im.imaging_id)
        else:
            # Fallback to follow-up if late, else baseline
            if ebrt_end and i_date >= ebrt_end:
                followup_images.append(im)
            else:
                baseline_images.append(im)
            assigned_img_ids.add(im.imaging_id)

    def render_encounter_block(enc, stage_num, stage_title, stage_images):
        """Renders Pelvic Examination metrics, Populated IBS SVG Diagram, and associated Imaging."""
        block_elements = []
        enc_date_str = enc.encounter_date.strftime('%d-%b-%Y') if (enc and enc.encounter_date) else '—'
        block_elements.append(Paragraph(f"<b>{stage_num}. {stage_title.upper()} (Encounter Date: {enc_date_str})</b>", sec_title))

        if enc:
            # Vitals & Pelvic metrics
            para_str = "Absent"
            if enc.parametrial_invasion or enc.para_left or enc.para_right:
                sides = []
                if enc.para_left:
                    ext_l = f" ({enc.para_extent_left_cm} cm)" if enc.para_extent_left_cm else ""
                    sides.append(f"Left{ext_l}")
                if enc.para_right:
                    ext_r = f" ({enc.para_extent_right_cm} cm)" if enc.para_extent_right_cm else ""
                    sides.append(f"Right{ext_r}")
                para_str = f"<b>PRESENT:</b> {', '.join(sides)}" if sides else "<b>PRESENT</b>"

            rectal_str = "<font color='#cc0000'><b>Mucosal Invasion</b></font>" if enc.rectal_invasion else "Normal / Free"
            bladder_str = "<font color='#cc0000'><b>Mucosal Invasion</b></font>" if enc.bladder_invasion else "Normal / Free"
            dims = [f"{d} cm" for d in [enc.tumour_size_cm, enc.tumour_size_2_cm, getattr(enc, 'tumour_size_3_cm', None)] if d is not None]
            tumour_dim = " × ".join(dims) if dims else "—"
            tandem_str = f"Sounded ({enc.tandem_length_cm} cm)" if (enc.tandem_sounded and enc.tandem_length_cm) else ("Sounded" if enc.tandem_sounded else "Not sounded")

            bmi_val = "—"
            if enc.height and enc.weight and enc.height > 0:
                ht_m = enc.height / 100.0
                bmi_val = f"{enc.weight / (ht_m * ht_m):.1f} kg/m²"

            exam_rows = [
                [
                    Paragraph("<b>ECOG / Vitals:</b>", th_style),
                    Paragraph(f"ECOG: {enc.ecog or '—'} | Ht: {enc.height or '—'}cm | Wt: {enc.weight or '—'}kg (BMI: {bmi_val})", cell_style),
                    Paragraph("<b>Tumour Size:</b>", th_style),
                    Paragraph(tumour_dim, cell_bold),
                ],
                [
                    Paragraph("<b>Parametrium:</b>", th_style),
                    Paragraph(para_str, cell_style),
                    Paragraph("<b>Uterine Sound:</b>", th_style),
                    Paragraph(tandem_str, cell_style),
                ],
                [
                    Paragraph("<b>Rectal Mucosa:</b>", th_style),
                    Paragraph(rectal_str, cell_style),
                    Paragraph("<b>Bladder Mucosa:</b>", th_style),
                    Paragraph(bladder_str, cell_style),
                ]
            ]
            t_ex = Table(exam_rows, colWidths=[90, 190, 95, 164])
            t_ex.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#b0b0b0')),
                ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9f9f9')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f9f9f9')),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            block_elements.append(t_ex)
            block_elements.append(Spacer(1, 4))

            # Populated IBS Pelvic Vector Diagram
            drawing, marked_labels = get_svg_drawing_flowable(enc, width_pt=460)
            if drawing:
                d_table = Table([[drawing]], colWidths=[539])
                d_table.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#003366')),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]))
                block_elements.append(d_table)
                block_elements.append(Spacer(1, 2))

            if marked_labels:
                labels_txt = ", ".join([f"<b>{lbl}</b>" for lbl in marked_labels])
                zones_note = f"<font color='#cc0000'><b>Mapped Pelvic Zones ({len(marked_labels)}):</b></font> {labels_txt}"
            else:
                zones_note = "<font color='#666666'><i>No specific anatomical pelvic zones marked for this evaluation.</i></font>"

            t_leg = Table([[Paragraph(zones_note, cell_style)]], colWidths=[539], style=[
                ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#c0d0e0')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f8fb')),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ])
            block_elements.append(t_leg)
            block_elements.append(Spacer(1, 4))
        else:
            block_elements.append(Paragraph("<i>No physical examination encounter logged for this stage.</i>", cell_style))
            block_elements.append(Spacer(1, 3))

        # Associated Imaging Studies
        block_elements.append(Paragraph(f"<b>Associated Imaging & Radiology Investigations ({len(stage_images)}):</b>", sub_title))
        if stage_images:
            for im in stage_images:
                block_elements.append(format_imaging_investigation(im, cell_style))
                block_elements.append(Spacer(1, 2))
        else:
            block_elements.append(Paragraph("<i>No imaging or radiology studies recorded for this timepoint.</i>", cell_style))

        block_elements.append(Spacer(1, 4))
        return block_elements

    # -------------------------------------------------------------
    # 1. BASELINE EVALUATION & IMAGING
    # -------------------------------------------------------------
    stage_idx = 1
    story.extend(render_encounter_block(base_enc, str(stage_idx), "Baseline Clinical Evaluation & Imaging", baseline_images))

    # -------------------------------------------------------------
    # 2. POST-NACT REASSESSMENT & IMAGING (only if post-NACT exam or imaging exists)
    # -------------------------------------------------------------
    if postnact_enc or postnact_images:
        stage_idx += 1
        story.append(PageBreak())
        story.extend(render_encounter_block(postnact_enc, str(stage_idx), "Post-NACT Reassessment & Restaging Imaging", postnact_images))

    # -------------------------------------------------------------
    # 3. PRE-BRACHY EVALUATION & IMAGING (if pre-brachy exam, imaging, or brachy course exists)
    # -------------------------------------------------------------
    if preb_enc or prebrachy_images or brachy_course:
        stage_idx += 1
        story.append(PageBreak())
        story.extend(render_encounter_block(preb_enc, str(stage_idx), "Pre-Brachytherapy Evaluation & Response Imaging", prebrachy_images))

    # -------------------------------------------------------------
    # 4. LONGITUDINAL FOLLOW-UP SURVEILLANCE & RECURRENCE MONITORING
    # -------------------------------------------------------------
    if fu_records.exists() or followup_images or fu_encs.exists():
        stage_idx += 1
        story.append(PageBreak())
        story.append(Paragraph(f"<b>{stage_idx}. LONGITUDINAL FOLLOW-UP SURVEILLANCE & SURVEILLANCE IMAGING</b>", sec_title))

        if fu_records.exists():
            fu_table_rows = [
                [
                    Paragraph("<b>Visit Date</b>", th_style),
                    Paragraph("<b>Contact Mode</b>", th_style),
                    Paragraph("<b>Disease Status</b>", th_style),
                    Paragraph("<b>Recurrence / Metastasis</b>", th_style),
                    Paragraph("<b>Vital Status</b>", th_style),
                    Paragraph("<b>Next Due</b>", th_style),
                ]
            ]
            for f in fu_records:
                dis_status = f.disease_status.status_name if f.disease_status else "Logged"
                dis_color = "#15803d" if "no evidence" in dis_status.lower() else "#b91c1c"
                
                rec_txt = "No recurrence"
                if f.recurrence_detected:
                    rec_site = f.recurrence_site.site_name if f.recurrence_site else "Local / Pelvic"
                    rec_txt = f"<font color='#cc0000'><b>RECURRENCE:</b> {rec_site}</font>"

                vital_txt = "<font color='#15803d'><b>Alive</b></font>"
                if f.death_reported:
                    vital_txt = f"<font color='#000000'><b>† Deceased</b> ({f.date_of_death.strftime('%d-%b-%Y') if f.date_of_death else ''})</font>"

                fu_table_rows.append([
                    Paragraph(f.follow_up_date.strftime('%d-%b-%Y') if f.follow_up_date else '—', cell_bold),
                    Paragraph(f.contact_type.contact_type if f.contact_type else 'In-person Clinic', cell_style),
                    Paragraph(f"<font color='{dis_color}'><b>{dis_status}</b></font>", cell_style),
                    Paragraph(rec_txt, cell_style),
                    Paragraph(vital_txt, cell_style),
                    Paragraph(f.next_fu_date.strftime('%d-%b-%Y') if f.next_fu_date else '—', cell_style),
                ])

            t_fu_list = Table(fu_table_rows, colWidths=[75, 95, 120, 125, 65, 59])
            t_fu_list.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#003366')),
                ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f5fa')),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t_fu_list)
            story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("<i>No longitudinal follow-up visit encounters recorded yet.</i>", cell_style))
            story.append(Spacer(1, 3))

        # Follow-up Surveillance Imaging
        story.append(Paragraph(f"<b>Surveillance Imaging & Radiology Investigations ({len(followup_images)}):</b>", sub_title))
        if followup_images:
            for im in followup_images:
                story.append(format_imaging_investigation(im, cell_style))
                story.append(Spacer(1, 2))
        else:
            story.append(Paragraph("<i>No surveillance imaging investigations recorded.</i>", cell_style))

    story.append(Spacer(1, 8))

    # Consultant Sign-Off Block
    signoff_rows = [
        [
            Paragraph("<b>Clinical Verification & Consultant Sign-off:</b>", th_style),
            Paragraph(f"Attending Consultant: <b>{str(patient.primary_consultant) if patient.primary_consultant else 'Department of Radiation Oncology'}</b> &nbsp;|&nbsp; Kidwai Memorial Institute of Oncology", cell_style),
        ]
    ]
    t_sign = Table(signoff_rows, colWidths=[160, 379], style=[
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#003366')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8faff')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    story.append(t_sign)

    # Attach metadata to canvas
    def _canvas_maker(*args, **kwargs):
        c = ExamNumberedCanvas(*args, **kwargs)
        c._patient_mr = patient.mr_no
        c._patient_name = patient.pt_name
        return c

    doc.build(story, canvasmaker=_canvas_maker)
    buf.seek(0)
    return buf


# Backwards compatibility alias
build_examination_pdf = build_examination_investigation_pdf
