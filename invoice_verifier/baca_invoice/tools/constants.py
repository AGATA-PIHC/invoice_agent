KNOWN_PROVIDERS: dict[str, dict] = {
    "traveloka": {
        "keywords": ["traveloka", "pt trinusa travelindo", "www.traveloka.com"],
        "valid_creators": ["skia", "chrome", "chromium", "webkit", "wkhtmltopdf", "iText"],
    },
    "tiket.com": {
        "keywords": ["tiket.com", "pt global tiket network", "www.tiket.com"],
        "valid_creators": ["skia", "chrome", "chromium", "webkit","iText", "wkhtmltopdf"],
    },
    "trip.com": {
        "keywords": ["trip.com", "ctrip", "www.trip.com"],
        "valid_creators": ["skia", "chrome", "chromium", "iText", "webkit"],
    },
    "airasia": {
        "keywords": ["airasia", "air asia", "capital a", "www.airasia.com"],
        "valid_creators": ["skia", "chrome", "chromium", "iText", "webkit"],
    },
    "garuda": {
        "keywords": ["garuda indonesia", "pt garuda", "citilink", "www.garuda-indonesia.com"],
        "valid_creators": ["iText"],
    },
    "lion_air": {
        "keywords": ["lion air", "pt lion mentari", "batik air", "wings air"],
        "valid_creators": ["iText"],
    },
    "kai": {
        "keywords": ["kereta api indonesia", "pt kai", "kai.id", "tiket.kai.id"],
        "valid_creators": ["skia","iText", "chrome", "chromium", "webkit"],
    },
}

SOFTWARE_LABELS: dict[str, str] = {
    "adobe acrobat": "Adobe Acrobat (software edit PDF)",
    "adobe distiller": "Adobe Distiller (konverter PDF Adobe)",
    "microsoft word": "Microsoft Word (pengolah kata)",
    "microsoft excel": "Microsoft Excel (spreadsheet)",
    "microsoft powerpoint": "Microsoft PowerPoint (presentasi)",
    "libreoffice": "LibreOffice (office suite open-source)",
    "openoffice": "OpenOffice (office suite open-source)",
    "foxit": "Foxit PDF Editor (software edit PDF)",
    "pdf24": "PDF24 (tool online edit PDF)",
    "ilovepdf": "iLovePDF (tool online edit PDF)",
    "smallpdf": "Smallpdf (tool online edit PDF)",
    "pdfsam": "PDFsam (tool split/merge PDF)",
    "pdfedit": "PDFEdit (editor PDF)",
    "pdfcreator": "PDFCreator (pembuat PDF dari dokumen lain)",
    "cutepdf": "CutePDF (virtual printer PDF)",
    "primopdf": "PrimoPDF (virtual printer PDF)",
    "nitro pdf": "Nitro PDF (software edit PDF)",
    "wondershare": "Wondershare PDFelement (software edit PDF)",
    "sejda": "Sejda (tool online edit PDF)",
    "canva": "Canva (aplikasi desain grafis)",
    "inkscape": "Inkscape (editor grafis vektor)",
    "gimp": "GIMP (editor gambar/foto)",
    "phantom pdf": "PhantomPDF (software edit PDF)",
    "pdffiller": "PDFfiller (tool online edit PDF)",
    "pdf-xchange": "PDF-XChange Editor (software edit PDF)"
}

CONFIDENCE_DEDUCTIONS: dict[str, float] = {
    "editing_software_detected": 0.55,
    "modified_after_creation": 0.30,
    "metadata_mismatch": 0.20,
    "unknown_provider": 0.15,
    "missing_metadata": 0.10,
}
