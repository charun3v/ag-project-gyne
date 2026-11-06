"""
Investigation & Diagnostic Evaluation PDF Report Generator
Generates A4 printable reports with:
- Header: Radiation Oncology | Kidwai Memorial Institute of Oncology
- Complete Blood, Biochemistry, Renal & Liver Panels
- Histopathology & Cytopathology Reports
- Molecular & Cytogenetic Profiling
- Imaging & Radiology Investigations (MRI, CT, PET-CT, USG with Pelvis Details)
- Professional clinical styling matching the KMIO reporting layout
"""

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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

from patients.models import Patient


class InvestNumberedCanvas(canvas.Canvas):
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
                self.drawRightString(567, 815, f"{pt_name} (MR: {mr_no}) — Diagnostic Investigations")
            self.setStrokeColor(colors.HexColor("#b0c0d0"))
            self.setLineWidth(0.5)
            self.line(28, 810, 567, 810)

        # Confidentiality footer on all pages
        self.setStrokeColor(colors.HexColor("#b0c0d0"))
        self.setLineWidth(0.5)
        self.line(28, 30, 567, 30)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#555555"))
        self.drawString(28, 20, "Kidwai Memorial Institute of Oncology — Radiation Oncology Diagnostic Record | Confidential Medical Record")
        self.drawRightString(567, 20, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_investigations_pdf(patient):
    """Builds and returns BytesIO buffer for Diagnostic Investigations Report."""
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

    # Custom styles
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
        spaceBefore=8,
        spaceAfter=3
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
        leading=9.5,
        textColor=colors.HexColor('#222222')
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=base_styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
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
                'RepDate', fontName='Helvetica', fontSize=8, leading=10,
                textColor=colors.HexColor('#555555'), alignment=2
            ))
        ],
        [
            Paragraph("Comprehensive Diagnostic Investigations & Laboratory Evaluation Report", title_doc),
            Paragraph(f"Reg Date: {patient.date_of_registration or '—'}", ParagraphStyle(
                'RegDate', fontName='Helvetica', fontSize=8, leading=10,
                textColor=colors.HexColor('#555555'), alignment=2
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
    story.append(Spacer(1, 4))

    # Section 1: Complete Blood & Biochemistry Investigations
    story.append(Paragraph("1. HEMATOLOGY, RENAL, LIVER & ELECTROLYTE INVESTIGATIONS", sec_title))
    blood_qs = patient.blood_tests.filter(soft_deleted=False).order_by('-test_date')
    if blood_qs.exists():
        for b in blood_qs:
            b_header = [
                Paragraph(f"<b>Date: {b.test_date or '—'}</b>", cell_bold),
                Paragraph(f"<b>Lab Ref:</b> {b.lab_reference_no or '—'}", cell_style),
                Paragraph(f"<b>Specimen:</b> {b.specimen_type or 'Blood'}", cell_style),
                Paragraph(f"<b>Entered By:</b> {b.entered_by or 'Staff'}", cell_style)
            ]
            
            # Row 1: CBC
            cbc_row = [
                Paragraph("<b>Complete Blood Count:</b>", th_style),
                Paragraph(f"Hb: <b>{b.hb or '—'}</b> g/dL", cell_style),
                Paragraph(f"TLC: <b>{b.tc or '—'}</b> /cu.mm", cell_style),
                Paragraph(f"ANC: {b.anc or '—'} | ALC: {b.alc or '—'}", cell_style),
                Paragraph(f"Platelets: <b>{b.platelet or '—'}</b> lakhs/cu.mm", cell_style)
            ]

            # Row 2: RFT & Electrolytes
            rft_row = [
                Paragraph("<b>Renal & Electrolytes:</b>", th_style),
                Paragraph(f"Urea: <b>{b.serum_urea or '—'}</b> mg/dL", cell_style),
                Paragraph(f"Creatinine: <b>{b.serum_creatinine or '—'}</b> mg/dL", cell_style),
                Paragraph(f"Na⁺: {b.serum_sodium or '—'} | K⁺: {b.serum_potassium or '—'} mEq/L", cell_style),
                Paragraph(f"Serum Calcium: {b.serum_calcium or '—'} mg/dL", cell_style)
            ]

            # Row 3: LFT & Proteins
            lft_row = [
                Paragraph("<b>Liver Function & Proteins:</b>", th_style),
                Paragraph(f"SGOT: {b.sgot or '—'} U/L | SGPT: {b.sgpt or '—'} U/L", cell_style),
                Paragraph(f"ALP: {b.alp or '—'} U/L", cell_style),
                Paragraph(f"Total Protein: {b.total_protein or '—'} g/dL", cell_style),
                Paragraph(f"Albumin: <b>{b.serum_albumin or '—'}</b> g/dL", cell_style)
            ]

            t_b_data = [
                [b_header[0], b_header[1], b_header[2], b_header[3], Paragraph("", cell_style)],
                cbc_row,
                rft_row,
                lft_row
            ]
            if b.impression or b.details:
                imp_text = f"<b>Clinical Notes / Remarks:</b> {b.impression or b.details}"
                t_b_data.append([Paragraph(imp_text, cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style)])

            t_blood = Table(t_b_data, colWidths=[120, 105, 105, 110, 99])
            t_blood_styles = [
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#003366')),
                ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f0f8')),
                ('SPAN', (0, 0), (1, 0)),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            if b.impression or b.details:
                t_blood_styles.append(('SPAN', (0, -1), (-1, -1)))
                t_blood_styles.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fafafa')))

            t_blood.setStyle(TableStyle(t_blood_styles))
            story.append(t_blood)
            story.append(Spacer(1, 4))
    else:
        story.append(Table([[Paragraph("<i>No routine blood or biochemistry investigations recorded for this patient.</i>", cell_style)]], colWidths=[539]))
        story.append(Spacer(1, 4))

    # Section 2: Histopathology Reports
    story.append(Paragraph("2. HISTOPATHOLOGY & CYTOPATHOLOGY INVESTIGATIONS", sec_title))
    path_qs = patient.pathology_reports.filter(soft_deleted=False).order_by('-path_date')
    if path_qs.exists():
        path_rows = [[
            Paragraph("<b>Date</b>", th_style),
            Paragraph("<b>Specimen / Biopsy Site</b>", th_style),
            Paragraph("<b>Pathology Type</b>", th_style),
            Paragraph("<b>Lab Ref No.</b>", th_style),
            Paragraph("<b>Microscopic Diagnosis & Impression</b>", th_style),
        ]]
        for p in path_qs:
            spec_str = f"{p.specimen or 'Specimen'} / {p.biopsy_site or p.fnac_site or 'Pelvic site'}"
            diag_txt = p.impression or p.details or "No findings noted"
            path_rows.append([
                Paragraph(str(p.path_date or '—'), cell_style),
                Paragraph(spec_str, cell_bold),
                Paragraph(str(p.path_type or 'Biopsy'), cell_style),
                Paragraph(p.lab_reference_no or '—', cell_style),
                Paragraph(diag_txt, cell_style),
            ])
        t_path = Table(path_rows, colWidths=[65, 125, 75, 75, 199])
        t_path.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#003366')),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f5fa')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_path)
    else:
        story.append(Table([[Paragraph("<i>No histopathology reports recorded for this patient.</i>", cell_style)]], colWidths=[539]))
    story.append(Spacer(1, 4))

    # Section 3: Molecular & Cytogenetic Testing
    story.append(Paragraph("3. MOLECULAR & CYTOGENETIC PROFILING", sec_title))
    mol_qs = patient.molecular_tests.filter(soft_deleted=False).order_by('-test_date')
    if mol_qs.exists():
        mol_rows = [[
            Paragraph("<b>Date</b>", th_style),
            Paragraph("<b>Assay / Test Modality</b>", th_style),
            Paragraph("<b>Testing Lab</b>", th_style),
            Paragraph("<b>Biomarkers & Outcomes</b>", th_style),
        ]]
        for m in mol_qs:
            results_list = []
            for r in m.results.all():
                val = r.result_value or (f"{r.result_numeric}" if r.result_numeric is not None else "Tested")
                st = f" ({r.result_status})" if r.result_status else ""
                results_list.append(f"<b>{r.marker.marker_name if r.marker else 'Marker'}:</b> {val}{st}")
            res_str = "<br/>".join(results_list) if results_list else (m.impression or m.details or "Tested")

            mol_rows.append([
                Paragraph(str(m.test_date or '—'), cell_style),
                Paragraph(str(m.molecular_type or 'NGS Panel'), cell_bold),
                Paragraph(m.testing_lab or 'KMIO Molecular Lab', cell_style),
                Paragraph(res_str, cell_style),
            ])
        t_mol = Table(mol_rows, colWidths=[65, 125, 110, 239])
        t_mol.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#003366')),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0e0e0')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f5fa')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t_mol)
    else:
        story.append(Table([[Paragraph("<i>No molecular / cytogenetic profiling recorded for this patient.</i>", cell_style)]], colWidths=[539]))
    story.append(Spacer(1, 4))

    # Section 4: Imaging & Radiology Investigations - Simple Non-Table Layout
    story.append(Paragraph("4. IMAGING & RADIOLOGY INVESTIGATIONS (WITH DATES)", sec_title))
    img_qs = patient.imaging_studies.filter(soft_deleted=False).order_by('-imaging_date')
    if img_qs.exists():
        for im in img_qs:
            mod_name = str(im.imaging_type) if im.imaging_type else "Radiology"
            site_name = im.sites_display
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

            if not details_parts and im.details:
                details_parts.append(im.details.strip())

            details_str = '; '.join(details_parts) if details_parts else 'Not recorded'
            impression_str = im.impression.strip() if im.impression else (p_det.radiologist_impression.strip() if (p_det and p_det.radiologist_impression) else 'Not recorded')

            img_block = (
                f"<b>{dt_str} {mod_name} ({site_name})</b><br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Details:</b> {details_str}<br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Impression:</b> {impression_str}"
            )
            story.append(Paragraph(img_block, cell_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Table([[Paragraph("<i>No imaging or radiology studies recorded for this patient.</i>", cell_style)]], colWidths=[539]))

    # Attach metadata to canvas
    def _canvas_maker(*args, **kwargs):
        c = InvestNumberedCanvas(*args, **kwargs)
        c._patient_mr = patient.mr_no
        c._patient_name = patient.pt_name
        return c

    doc.build(story, canvasmaker=_canvas_maker)
    buf.seek(0)
    return buf
