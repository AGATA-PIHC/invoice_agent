from google.adk.agents import LlmAgent

from ..models.travel_document import TravelDocumentResult


FORMATTER_PROMPT = """
Anda adalah formatter schema hasil ekstraksi dokumen perjalanan.

Input adalah JSON hasil ekstraksi awal. Tugas Anda:
1. Normalisasi input ke schema Pydantic `TravelDocumentResult`.
2. Pertahankan nilai yang sudah ada.
3. Isi semua field yang hilang atau tidak relevan dengan default:
   string="-", number=0.0, integer=0, boolean=false, list=[].
4. Output akhir harus mengikuti output_schema. Jangan memanggil tool.
5. Jangan menambahkan markdown atau teks penjelasan.
"""


formatter_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="travel_document_schema_formatter",
    description="Normalisasi hasil ekstraksi ke schema TravelDocumentResult.",
    instruction=FORMATTER_PROMPT,
    output_schema=TravelDocumentResult,
)
