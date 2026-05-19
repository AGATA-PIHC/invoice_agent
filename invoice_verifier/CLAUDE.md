# Project: Invoice Verifier

Aplikasi verifikasi dokumen perjalanan dinas (invoice & receipt) menggunakan Google ADK + FastAPI.

## Active Feature Work

<!-- SPECKIT START -->
**Current spec**: [Frontend & Error Response Consistency](specs/002-frontend-error-consistency/spec.md)
**Plan**: [specs/002-frontend-error-consistency/plan.md](specs/002-frontend-error-consistency/plan.md)
**Status**: Planning complete — ready for `/speckit-tasks`

**Previous**: [Invoice & Receipt Classification](specs/001-invoice-receipt-classification/spec.md) ✅ Implemented
<!-- SPECKIT END -->

## Key Conventions

- API endpoint utama: `/api/pinter/upload` dan `/api/pinter/extract` (PINTER pattern)
- Storage: SQLite via `aiosqlite` (path di env `SQLITE_DB_PATH`)
- Auth: `X-API-Key` header (env `PINTER_API_KEY`; disabled jika tidak di-set)
- Pydantic v2 untuk semua schema validation
- Tests di `tests/` (`unit/`, `integration/`, `security/`) — pakai pytest + httpx

## Doc Type Classification

Setelah implementasi spec 001:
- `invoice` — tagihan formal dengan invoice_number, PPN, vendor info
- `receipt` — bukti pembayaran dengan receipt_number, payment_method
- `unknown` — tidak dikenali; sistem TIDAK panggil AI, kembalikan default + authenticity
