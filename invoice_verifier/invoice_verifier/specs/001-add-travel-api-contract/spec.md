# Specification: API Contract Integrasi Travel (ADS-16)

**Track ID:** 001-add-travel-api-contract
**Linear Issue:** ADS-16
**Type:** Feature
**Created:** 2026-05-18
**Status:** In Review

## Summary

Membuat dan memverifikasi API contract untuk integrasi travel antara PISmart (A) dan PINTER (B),
mencakup dua alur utama: pengiriman dokumen dengan return transaction_id, dan pengambilan hasil
verifikasi dengan return JSON.

## Context

Sistem Invoice Verifier (PINTER) menerima dokumen PDF dari PISmart, menjalankan OCR dan verifikasi
AI, lalu menyediakan hasil verifikasi melalui API. Integrasi bersifat machine-to-machine (M2M).

## User Story

As a PISmart system, I want to submit travel documents (invoice/receipt) and receive verification
results so that I can validate travel expense claims automatically.

## Acceptance Criteria

- [ ] A (PISmart) dapat mengirim data dokumen PDF → B (PINTER) mengembalikan `transaction_id`
- [ ] A (PISmart) dapat mengirim `transaction_id` → B (PINTER) mengembalikan JSON hasil verifikasi
- [ ] Invoice (tagihan) dan Receipt (bukti bayar) dapat dibedakan via field `document_type`
- [ ] OCR tidak menjadi stopper: hasil selalu dikembalikan meski OCR gagal atau confidence rendah
- [ ] Confidence/authentic level ditampilkan di response (`ocr_confidence`, `authenticity`)
- [ ] API contract tersedia dalam format OpenAPI 3.1.0
- [ ] Autentikasi via `X-API-Key` header

## API Alur

### Alur 1: Kirim dokumen → Return transaction_id
```
POST /api/travel/submit
Body: { document_type, source_system, reference_id, filename, file_base64 }
Response: { transaction_id, reference_id, status: "processing", submitted_at }
```

### Alur 2: Kirim transaction_id → Return JSON
```
GET /api/travel/result/{transaction_id}
Response: { transaction_id, reference_id, document_type, status, ocr_confidence, result, warning, error, completed_at }
```

## Dependencies

- `web/api/travel.py` — endpoint handler
- `web/models/travel_contract.py` — Pydantic models
- `web/services/agent_runner.py` — OCR & AI agent runner
- `baca_invoice/` — OCR agent (flight & hotel)
- `web/travel_api_contract.json` — OpenAPI 3.1.0 contract

## Out of Scope

- Perubahan pada alur verifikasi OCR internal (baca_invoice/)
- Persistent storage untuk transaction history
- Horizontal scaling / multi-worker
- Webhook callback ke PISmart

## Technical Notes

- Framework: FastAPI (Python)
- Auth: API Key via `X-API-Key` header, dikonfigurasi via env `TRAVEL_API_KEY`
- Non-blocking: submit langsung return, proses berjalan di background (asyncio)
- Fallback: jika doc_type tidak terdeteksi, fallback ke "hotel" dengan warning
- Threshold OCR confidence rendah: < 0.6 → tampilkan warning, tetap return hasil
