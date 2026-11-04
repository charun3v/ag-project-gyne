"""
SVG Generator & Clinical Examination Mapping Engine
Handles:
1. Auto-populating SVG anatomical regions from clinical pelvic examination findings.
2. Generating marked SVG XML for web rendering and interactive diagram display.
3. Converting populated vector SVG into scaled, rotated ReportLab Drawing objects for PDF reports.
"""

import io
import os
import xml.etree.ElementTree as ET
from django.conf import settings
from reportlab.graphics.shapes import Drawing, Group
from svglib.svglib import svg2rlg

from clinical.models import SVGRegion, ClinicalSVGFinding


REGION_LABELS_MAP = {
    "Vag_Cor_U3": "Vag Cor Upper 1/3", "Vag_Sag_U3": "Vag Sag Upper 1/3",
    "Vag_Sag_M3": "Vag Sag Middle 1/3", "Vag_Cor_M3": "Vag Cor Middle 1/3",
    "Var_Sag_M3": "Vag Sag Middle 1/3",
    "Vag_Sag_L3": "Vag Sag Lower 1/3", "Vag_Cor_L3": "Vag Cor Lower 1/3",
    "Rectum": "Rectum", "Bladder": "Bladder",
    "Fornix_Ant": "Fornix Ant", "Fornix_Rt": "Fornix Rt", "Fornix_Lt": "Fornix Lt", "Fornix_Post": "Fornix Post",
    "VAG_PS_U3_Rt": "Vag Wall Upper 1/3 - Rt", "VAG_PS_U3_Lt": "Vag Wall Upper 1/3 - Lt",
    "VAG_PS_U3_Ant": "Vag Wall Upper 1/3 - Ant", "VAG_PS_U3_Post": "Vag Wall Upper 1/3 - Post",
    "VAG_PS_M3_Post": "Vag Wall Middle 1/3 - Post", "VAG_PS_M3_Ant": "Vag Wall Middle 1/3 - Ant",
    "VAG_PS_M3_Lt": "Vag Wall Middle 1/3 - Lt", "VAG_PS_M3_Rt": "Vag Wall Middle 1/3 - Rt",
    "VAG_PS_L3_Post": "Vag Wall Lower 1/3 - Post", "VAG_PS_L3_Ant": "Vag Wall Lower 1/3 - Ant",
    "VAG_12_1": "Vagina Clock 12-1 o'clock", "VAG_1_2": "Vagina Clock 1-2 o'clock",
    "VAG_2_3": "Vagina Clock 2-3 o'clock", "VAG_3_4": "Vagina Clock 3-4 o'clock",
    "VAG_4_5": "Vagina Clock 4-5 o'clock", "VAG_5_6": "Vagina Clock 5-6 o'clock",
    "VAG_6_7": "Vagina Clock 6-7 o'clock", "VAG_7_8": "Vagina Clock 7-8 o'clock",
    "VAG_8_9": "Vagina Clock 8-9 o'clock", "VAG_9_10": "Vagina Clock 9-10 o'clock",
    "VAG_10_11": "Vagina Clock 10-11 o'clock", "VAG_11_12": "Vagina Clock 11-12 o'clock",
    "Para_NMD_3_Lt": "Parametrium NMD 3cm - Lt", "Para_NMD_4_Lt": "Parametrium NMD 4cm - Lt",
    "Para_NMD_5_Lt": "Parametrium NMD 5cm - Lt", "Para_NMD_6_Lt": "Parametrium NMD 6cm - Lt",
    "Para_NMD_3_Rt": "Parametrium NMD 3cm - Rt", "Para_NMD_4_Rt": "Parametrium NMD 4cm - Rt",
    "Para_NMD_5_Rt": "Parametrium NMD 5cm - Rt", "Para_NMD_6_Rt": "Parametrium NMD 6cm - Rt",
    "Para_NMD_2_Rt": "Parametrium NMD 2cm - Rt", "Para_NMD_2_Lt": "Parametrium NMD 2cm - Lt",
    "Cx_Cor_1_Rt": "Cervix Coronal - 1 - Rt", "Cx_Cor_2_Rt": "Cervix Coronal - 2 - Rt",
    "Cx_Cor_1_Lt": "Cervix Coronal - 1 - Lt", "Cx_Cor_2_Lt": "Cervix Coronal - 2 - Lt",
    "Cx_Sag_1_Post": "Cervix Sagittal - 1 - Post", "Cx_Sag_1_Ant": "Cervix Sagittal - 1 - Ant",
    "Cx_Sag_2_Post": "Cervix Sagittal - 2 - Post", "Cx_Sag_2_Ant": "Cervix Sagittal - 2 - Ant",
    "Para_Ax_2_Lt": "Parametrium Axial 2cm - Lt", "Para_Ax_3_Lt": "Parametrium Axial 3cm - Lt",
    "Para_Ax_2_Rt": "Parametrium Axial 2cm - Rt", "Para_Ax_3_Rt": "Parametrium Axial 3cm - Rt",
    "Cx_Ax_Ant_Rt": "Cervix Axial - Ant - Rt", "Cx_Ax_Post_Lt": "Cervix Axial - Post - Rt",
    "Cx_Ax_Ant_Lt": "Cervix Axial - Ant_Lt", "Cx_Ax_Ant": "Cervix Axial - Ant",
    "Cx_Ax_Lat_Rt": "Cervix Axial - Lat - Rt", "Cx_Ax_Post": "Cervix Axial - Post",
    "Cx_Ax_Lat_Lt": "Cervix Axial - Lat_Lt", "Ut_Body_Cor": "Uterine Body - Coronal",
    "Ut_Body_Sag": "Uterine Body - Sagittal"
}


def auto_populate_svg_from_encounter(encounter, user_username='system', force_overwrite=False):
    """
    Translates clinical pelvic examination findings (parametrial involvement,
    rectal/bladder invasion, tumor size) into corresponding anatomical SVG region codes
    and records them in ClinicalSVGFinding.
    """
    if not encounter:
        return []

    # If findings already exist and force_overwrite is False, do not duplicate
    existing = encounter.svg_findings.filter(soft_deleted=False)
    if existing.exists() and not force_overwrite:
        return [f.region.region_code for f in existing if f.region]

    codes_to_mark = set()

    # 1. Rectal Invasion
    if encounter.rectal_invasion:
        codes_to_mark.add('Rectum')

    # 2. Bladder Invasion
    if encounter.bladder_invasion:
        codes_to_mark.add('Bladder')

    # 3. Parametrial Left Invasion & Extent
    if encounter.para_left or encounter.parametrial_invasion:
        codes_to_mark.add('Para_NMD_2_Lt')
        codes_to_mark.add('Para_Ax_2_Lt')
        ext = encounter.para_extent_left_cm or 0
        if ext >= 3.0:
            codes_to_mark.add('Para_NMD_3_Lt')
            codes_to_mark.add('Para_Ax_3_Lt')
        if ext >= 4.0:
            codes_to_mark.add('Para_NMD_4_Lt')
        if ext >= 5.0:
            codes_to_mark.add('Para_NMD_5_Lt')
        if ext >= 6.0:
            codes_to_mark.add('Para_NMD_6_Lt')

    # 4. Parametrial Right Invasion & Extent
    if encounter.para_right or encounter.parametrial_invasion:
        codes_to_mark.add('Para_NMD_2_Rt')
        codes_to_mark.add('Para_Ax_2_Rt')
        ext = encounter.para_extent_right_cm or 0
        if ext >= 3.0:
            codes_to_mark.add('Para_NMD_3_Rt')
            codes_to_mark.add('Para_Ax_3_Rt')
        if ext >= 4.0:
            codes_to_mark.add('Para_NMD_4_Rt')
        if ext >= 5.0:
            codes_to_mark.add('Para_NMD_5_Rt')
        if ext >= 6.0:
            codes_to_mark.add('Para_NMD_6_Rt')

    # 5. Cervix / Primary Tumor
    has_cervix_disease = True
    diag = getattr(encounter.patient, 'diagnoses', None)
    if diag:
        curr_diag = diag.filter(is_current=True, soft_deleted=False).first()
        if curr_diag and curr_diag.primary_site:
            site_name = str(curr_diag.primary_site.site).lower()
            if 'cervix' not in site_name and 'cervical' not in site_name:
                has_cervix_disease = False

    if has_cervix_disease:
        codes_to_mark.add('Cx_Cor_1_Rt')
        codes_to_mark.add('Cx_Cor_1_Lt')
        codes_to_mark.add('Cx_Sag_1_Ant')
        codes_to_mark.add('Cx_Sag_1_Post')
        codes_to_mark.add('Cx_Ax_Ant')
        codes_to_mark.add('Cx_Ax_Post')

        sz = encounter.tumour_size_cm or 0
        if sz >= 4.0:
            codes_to_mark.add('Cx_Cor_2_Rt')
            codes_to_mark.add('Cx_Cor_2_Lt')
            codes_to_mark.add('Cx_Sag_2_Ant')
            codes_to_mark.add('Cx_Sag_2_Post')
            codes_to_mark.add('Fornix_Ant')
            codes_to_mark.add('Fornix_Post')
            codes_to_mark.add('Vag_Cor_U3')
            codes_to_mark.add('Vag_Sag_U3')

    # Persist into ClinicalSVGFinding
    for code in codes_to_mark:
        region = SVGRegion.objects.filter(region_code=code).first()
        if not region:
            continue
        finding, created = ClinicalSVGFinding.objects.get_or_create(
            encounter=encounter,
            region=region,
            defaults={
                'entered_by': user_username,
                'soft_deleted': False
            }
        )
        if not created and finding.soft_deleted:
            finding.soft_deleted = False
            finding.last_modified_by = user_username
            finding.save()

    return list(codes_to_mark)


def get_populated_svg_xml(encounter):
    """
    Returns (svg_xml_string, list_of_marked_codes, list_of_marked_labels).
    Per user clinical specifications:
    - Only selected areas are highlighted in light red (prints as light gray in B&W printing).
    - Unselected areas are transparent (fill: none; fill-opacity: 0), preserving only subtle boundary outlines.
    """
    svg_path = os.path.join(settings.BASE_DIR, 'static', 'svg', 'ibs_clinical.svg')
    if not os.path.exists(svg_path):
        return '', [], []

    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_text = f.read()

    # Collect marked codes
    marked_codes = set()
    if encounter:
        findings = encounter.svg_findings.filter(soft_deleted=False).select_related('region')
        if findings.exists():
            for f in findings:
                if f.region:
                    marked_codes.add(f.region.region_code)
        else:
            inferred = auto_populate_svg_from_encounter(encounter)
            marked_codes.update(inferred)

    # Parse and modify SVG elements
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
    ET.register_namespace('sodipodi', 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

    try:
        root = ET.fromstring(svg_text.encode('utf-8'))
    except Exception:
        return svg_text, list(marked_codes), []

    for elem in root.iter():
        label = elem.attrib.get('{http://www.inkscape.org/namespaces/inkscape}label') or elem.attrib.get('data-region')
        if label and label not in ('Background', 'Regions'):
            is_marked = (label in marked_codes) or (label == 'Var_Sag_M3' and 'Vag_Sag_M3' in marked_codes)
            if is_marked:
                # Highlight in light red (prints as light/medium gray on black-and-white printouts)
                elem.attrib['fill'] = '#ff9999'
                elem.attrib['style'] = 'fill:#ff9999 !important;opacity:0.85;fill-opacity:0.85;stroke:#cc0000;stroke-width:0.7px;'
            else:
                # Unselected areas are transparent (no fill), showing only anatomical outline
                elem.attrib['fill'] = 'none'
                elem.attrib['style'] = 'fill:none !important;opacity:0;fill-opacity:0;stroke:#888888;stroke-width:0.25px;'

    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding='utf-8', xml_declaration=True)
    xml_output = buf.getvalue().decode('utf-8')

    marked_labels = [REGION_LABELS_MAP.get(c, c) for c in sorted(marked_codes)]
    return xml_output, list(marked_codes), marked_labels


def get_svg_drawing_flowable(encounter, width_pt=480):
    """
    Produces a rotated, scaled ReportLab Drawing object representing the populated SVG diagram,
    turned 180 degrees from previously inverted orientation (rotated 270 deg counter-clockwise / 90 deg clockwise).
    Returns (drawing, list_of_marked_labels).
    """
    svg_xml, marked_codes, marked_labels = get_populated_svg_xml(encounter)
    if not svg_xml:
        return None, []

    buf = io.BytesIO(svg_xml.encode('utf-8'))
    try:
        orig_drawing = svg2rlg(buf)
    except Exception:
        return None, marked_labels

    if not orig_drawing:
        return None, marked_labels

    w, h = orig_drawing.width, orig_drawing.height

    # Turning 180 degrees from previously upside-down view:
    # Rotate 270 degrees in Cartesian space (= 90 deg clockwise), translated by (0, w)
    scale = float(width_pt) / float(h)
    target_w = h * scale
    target_h = w * scale

    drawing = Drawing(target_w, target_h)
    g = Group()
    g.scale(scale, scale)
    g.translate(0, w)
    g.rotate(270)
    for child in orig_drawing.contents:
        g.add(child)
    drawing.add(g)

    return drawing, marked_labels
