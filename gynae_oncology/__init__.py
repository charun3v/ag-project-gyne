"""
Django project initialization for gynae_oncology.
Compatibility shims for Python 3.8 and ReportLab 4.x.
"""
import hashlib

# Python 3.8 / OpenSSL hashlib compatibility shim for ReportLab 4.x
# In Python 3.8, hashlib.md5 does not accept 'usedforsecurity=False'.
_orig_md5 = hashlib.md5

def _safe_md5(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return _orig_md5(*args, **kwargs)

hashlib.md5 = _safe_md5

try:
    import reportlab.pdfbase.pdfdoc as _pdfdoc
    _pdfdoc.md5 = _safe_md5
except Exception:
    pass
