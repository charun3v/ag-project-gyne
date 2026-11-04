# Gynaecological Oncology Clinical Database & MDT System

A comprehensive, multidisciplinary clinical information and radiation oncology management system built with Django, designed for gynaecological cancer care at Kidwai Memorial Institute of Oncology (KMIO).

## Key Features

- **Patient Demographics & Central Registration**: Patient master record management with contact details, consultant assignment, and quick worklist search.
- **Clinical History & Habits**: Structured tracking of presenting complaints, toxic habits (smoking, alcohol, tobacco chewing), comorbidities (hypertension, diabetes, thyroid disorders), and prior surgeries/radiation.
- **Pelvic Examination & Interactive IBS Diagrams**: Physical examination and interactive pelvic anatomy diagram marking for baseline, post-NACT, and pre-brachytherapy evaluation with automatic chronological carry-forward.
- **Comprehensive Investigations Hub**:
  - **Pathology & Cytology**: Histopathology, biopsy sites, FNAC sites, and microscopic descriptions.
  - **Molecular & Biomarkers**: IHC and molecular testing outcomes (e.g. p53, p16, MSI/dMMR, PD-L1).
  - **Imaging & Radiology**: Multi-modality imaging studies (MRI Pelvis, CT, PET-CT) with structured organ invasion and nodal station tracking.
  - **Hematology & Biochemistry**: Complete blood count and renal/liver/electrolyte labs.
- **Multi-Diagnosis & Staging Engine**:
  - Support for multiple cancer diagnoses per patient with Primary vs Secondary classification.
  - Auto-population of Histological Type and Grade from pathology/molecular investigation entries.
  - FIGO / AJCC TNM clinical and pathological staging.
- **Systemic Chemotherapy Modules**:
  - **Neoadjuvant Chemotherapy (NACT)**: Regimens, cycles, administered drug hierarchy, doses, and clinical response evaluation.
  - **Adjuvant Chemotherapy**: Post-definitive systemic therapy tracking.
- **Radiation Oncology Management**:
  - **External Beam Radiotherapy (EBRT)**: Technique, intent, fractions, target sites, simulation/start/end dates with chronological planning rules, and concurrent chemotherapy.
  - **Brachytherapy**: Insertion sessions and multiple applications, applicator types (Tandem only, Tandem + Ovoids, Tandem + Ring, Interstitial template/needles) with configurable measurement validation, target dosimetry (HRCTV D90), and OAR 2cc doses (bladder, rectum, sigmoid).
  - **LQ Radiobiology**: Cumulative EQD2 calculations for tumour and OARs across EBRT and Brachytherapy.
- **Longitudinal Follow-up & Surveillance**: Surveillance visit logging, disease status (NED, recurrence, residual), next appointment scheduling, and surveillance imaging.
- **Clinical Summary & Investigation PDF Reports**: High-quality, publication-grade A4 PDF reports generated dynamically with ReportLab.

## Tech Stack

- **Backend**: Python 3.8+, Django 4.2 LTS
- **Database**: SQLite (default for development/local deployment) or PostgreSQL
- **PDF Generation**: ReportLab
- **Frontend**: Django Templates with responsive MS Access clinical workflow design

## Quick Setup Guide

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "AG project - Gyne"
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Copy `.env.example` to `.env` and set your secret key:
   ```bash
   copy .env.example .env
   ```

5. **Apply database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Run the development server**:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

   Visit `http://127.0.0.1:8000/` in your browser.
