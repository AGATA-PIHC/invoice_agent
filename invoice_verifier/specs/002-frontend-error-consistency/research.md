# Research: Frontend & Error Response Consistency

**Phase**: 0

## Keputusan 1: Polling vs SSE/WebSocket

**Decision**: Pakai HTTP polling dengan interval 1.5 detik, max 5 menit total.

**Rationale**:
- Backend sudah expose `GET /api/pinter/extract` polling-style untuk konsumen PISmart
- SSE memerlukan endpoint streaming baru (sudah dihapus di konsolidasi PINTER)
- WebSocket overkill untuk use case dengan AI processing 10-30 detik
- Polling lebih sederhana, kompatibel dengan HTTP proxy/load balancer
- Interval 1.5s = trade-off antara latency UX (terasa instant) dan beban server (40 req/menit per user)

**Alternatif**:
- SSE → ditolak, butuh endpoint baru
- WebSocket → ditolak, overkill
- Long-polling → ditolak, klien browser butuh modifikasi connection timeout

## Keputusan 2: Error Code Mapping Strategy

**Decision**: Pakai field-path matching di handler `RequestValidationError`.

**Rationale**:
- `RequestValidationError.errors()` mengembalikan list of dicts dengan `loc` (tuple of strings) yang menandakan lokasi error
- Untuk `MISSING_FILE`: `loc == ('body', 'file')`
- Untuk `MISSING_TRX_ID`: `loc == ('query', 'trx_id')`
- Field error lain → fallback ke `VALIDATION_ERROR`

**Implementasi**:
```python
@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    errors = exc.errors()
    loc_paths = [tuple(e["loc"]) for e in errors]
    if ("body", "file") in loc_paths:
        return _error("File PDF wajib diisi.", "MISSING_FILE")
    if ("query", "trx_id") in loc_paths:
        return _error("Parameter trx_id wajib diisi.", "MISSING_TRX_ID")
    msg = errors[0]["msg"] if errors else "Permintaan tidak valid."
    return _error(msg, "VALIDATION_ERROR")
```

**Alternatif**:
- Pakai middleware → ditolak, lebih kompleks, sulit di-unit-test
- Custom dependency yang raise V1ApiError → ditolak, tidak menangkap error dari UploadFile validation

## Keputusan 3: HTTP Status Code

**Decision**: Ubah 422 default FastAPI → 400 untuk semua validation error.

**Rationale**:
- Endpoint `/api/pinter/*` sudah konsisten pakai 400 untuk client error
- 422 Unprocessable Entity secara teknis valid, tapi mismatch dengan error code lain (`MISSING_FILE` sudah 400 di `V1ApiError`)
- 400 lebih familiar untuk klien API
- Konsistensi > kebenaran spec HTTP

**Alternatif**:
- Pertahankan 422 → ditolak, inkonsisten dengan error code lain

## Keputusan 4: Polling Backoff

**Decision**: Polling konstan 1.5 detik, tidak exponential backoff.

**Rationale**:
- AI processing biasanya 10-30 detik, jarang lebih dari 1 menit
- Exponential backoff akan terasa lambat untuk processing pendek
- 1.5s × 200 attempts = 5 menit timeout total (cukup untuk worst case)

## Keputusan 5: Render Strategy Berdasarkan doc_type

**Decision**: Switch-case pada `data.doc_type`, tidak duck-typing field.

**Rationale**:
- Frontend lama pakai `'airline' in data` untuk deteksi tipe — fragile, breaks ketika schema berubah
- `doc_type` sudah dijamin ada di setiap response success (FR-4 spec 001)
- Switch-case eksplisit lebih mudah di-debug dan extend

**Mapping**:
- `"invoice"` → render section: invoice info, vendor, buyer, line items, totals
- `"receipt"` → render section: receipt info, merchant, payer, items purchased, totals
- `"unknown"` → render section: info "tidak terklasifikasi" + authenticity saja (tidak ada data ekstraksi)
- field lain → tetap render sebagai raw key-value (defensive untuk schema lama hotel/flight kalau routing internal)

## Konsolidasi NEEDS CLARIFICATION

Tidak ada. Semua keputusan teknis sudah dipilih.
