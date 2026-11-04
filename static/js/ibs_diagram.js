/**
 * Interactive IBS Clinical Anatomy Pelvic Diagram
 * Native HTML5/SVG implementation ported from IBS_Wrapper.html
 */

var markedRegions = {};

var REGION_LABELS = {
    "Vag_Cor_U3": "Vag Cor Upper 1/3", "Vag_Sag_U3": "Vag Sag Upper 1/3",
    "Vag_Sag_M3": "Vag Sag Middle 1/3", "Vag_Cor_M3": "Vag Cor Middle 1/3",
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
};

function labelFor(code) {
    return REGION_LABELS[code] || code;
}

function initIBSDiagram() {
    var svg = document.getElementById("ibsSvg");
    if (!svg) {
        var holder = document.getElementById("svgHolder");
        if (holder) svg = holder.getElementsByTagName("svg")[0];
    }
    if (!svg) return;

    var paths = svg.getElementsByTagName("path");
    var attached = 0;
    for (var i = 0; i < paths.length; i++) {
        var p = paths[i];
        var label = p.getAttribute("inkscape:label");
        if (!label) {
            try { label = p.getAttributeNS("http://www.inkscape.org/namespaces/inkscape", "label"); } catch(e) {}
        }
        if (!label) {
            label = p.getAttribute("data-region");
        }

        if (label && label !== "Background" && label !== "Regions") {
            p.setAttribute("data-region", label);
            p.style.cursor = "pointer";
            p.addEventListener("click", onRegionClick);
            p.addEventListener("mouseenter", onRegionHover);
            p.addEventListener("mouseleave", onRegionUnhover);
            attached++;
        }
    }

    // Load initial marks if provided
    var initInput = document.getElementById("initialMarks");
    if (initInput && initInput.value) {
        setMarks(initInput.value);
    }
    var statusEl = document.getElementById("statusText");
    if (statusEl) statusEl.innerText = attached + " anatomical zones ready";
}

function onRegionClick(evt) {
    var region = this.getAttribute("data-region");
    if (!region) return;

    if (markedRegions[region]) {
        delete markedRegions[region];
        this.classList.remove("region-marked");
    } else {
        markedRegions[region] = true;
        this.classList.add("region-marked");
    }
    updateStatusDisplay();
}

function onRegionHover(evt) {
    var region = this.getAttribute("data-region");
    if (!region) return;
    this.classList.add("region-hover");
    var hoverLabel = document.getElementById("hoverRegionLabel");
    if (hoverLabel) {
        hoverLabel.innerText = labelFor(region);
    }
}

function onRegionUnhover(evt) {
    this.classList.remove("region-hover");
    var hoverLabel = document.getElementById("hoverRegionLabel");
    if (hoverLabel) {
        hoverLabel.innerText = "Hover over an anatomical zone";
    }
}

function getMarkedList() {
    var list = [];
    for (var k in markedRegions) {
        if (markedRegions.hasOwnProperty(k)) list.push(k);
    }
    return list.join(",");
}

function getMarkedDisplayList() {
    var list = [];
    for (var k in markedRegions) {
        if (markedRegions.hasOwnProperty(k)) list.push(labelFor(k));
    }
    return list.join(", ");
}

function updateStatusDisplay() {
    var countEl = document.getElementById("markedCount");
    var listEl = document.getElementById("markedListText");
    var hiddenInput = document.getElementById("markedRegionsInput");

    var list = getMarkedList();
    var count = Object.keys(markedRegions).length;

    if (countEl) countEl.innerText = count;
    if (listEl) listEl.innerText = count > 0 ? getMarkedDisplayList() : "None";
    if (hiddenInput) hiddenInput.value = list;
}

function clearAllMarks() {
    var svg = document.getElementById("ibsSvg");
    if (!svg) {
        var holder = document.getElementById("svgHolder");
        if (holder) svg = holder.getElementsByTagName("svg")[0];
    }
    if (!svg) return;
    var paths = svg.getElementsByTagName("path");
    for (var i = 0; i < paths.length; i++) {
        paths[i].classList.remove("region-marked");
    }
    markedRegions = {};
    updateStatusDisplay();
}

function setMarks(csvList) {
    clearAllMarks();
    if (!csvList) return;
    var codes = csvList.split(",");
    var svg = document.getElementById("ibsSvg");
    if (!svg) {
        var holder = document.getElementById("svgHolder");
        if (holder) svg = holder.getElementsByTagName("svg")[0];
    }
    if (!svg) return;
    var paths = svg.getElementsByTagName("path");

    for (var i = 0; i < codes.length; i++) {
        var code = codes[i].trim();
        if (!code) continue;
        for (var j = 0; j < paths.length; j++) {
            if (paths[j].getAttribute("data-region") === code) {
                markedRegions[code] = true;
                paths[j].classList.add("region-marked");
                break;
            }
        }
    }
    updateStatusDisplay();
}

document.addEventListener("DOMContentLoaded", initIBSDiagram);
