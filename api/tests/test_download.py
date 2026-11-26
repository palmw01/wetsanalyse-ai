"""Elke export is een inerte download (`bestandsnaam.download`, SonarQube S5131)."""
from __future__ import annotations

import pytest

from app import bestandsnaam


def test_download_is_een_bijlage_zonder_sniffen_en_zonder_scripts():
    r = bestandsnaam.download(b"<script>alert(1)</script>", "text/csv; charset=utf-8", "begrippen.csv")
    assert r.body == b"<script>alert(1)</script>"
    assert r.headers["content-disposition"] == 'attachment; filename="begrippen.csv"'
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == "default-src 'none'; sandbox"


@pytest.mark.parametrize("soort", ["text/html", "text/HTML; charset=utf-8", "application/xhtml+xml"])
def test_download_weigert_html(soort):
    with pytest.raises(ValueError):
        bestandsnaam.download(b"x", soort, "x.html")
