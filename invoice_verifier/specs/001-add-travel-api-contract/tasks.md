# Tasks: API Contract Integrasi Travel (ADS-16)

**Track ID:** 001-add-travel-api-contract
**Plan:** [plan.md](./plan.md)
**Created:** 2026-05-18

## Phase 1: Foundation Verification

| ID  | Task | File | Status |
|-----|------|------|--------|
| 1.1 | Cek router travel di-include di `web/main.py` | `web/main.py` | [X] |
| 1.2 | Cek `TRAVEL_API_KEY` di `web/config.py` dan `.env_example` | `web/config.py`, `baca_invoice/.env_example` | [X] |
| 1.3 | Cek router prefix `/api/travel` terdaftar | `web/main.py`, `web/api/travel.py` | [X] |

**Phase 1 Gate:** `/docs` menampilkan endpoint travel ✓

---

## Phase 2: Core API Behavior

| ID  | Task | File | Status |
|-----|------|------|--------|
| 2.1 | Verifikasi POST /submit → return `transaction_id` + `processing` | `web/api/travel.py:40-117` | [X] |
| 2.2 | Verifikasi GET /result → return JSON lengkap | `web/api/travel.py:120-190` | [X] |
| 2.3 | Verifikasi `document_type` di-echo di response | `web/api/travel.py` | [X] |
| 2.4 | Verifikasi validasi Literal["invoice","receipt"] | `web/models/travel_contract.py:10` | [X] |
| 2.5 | Verifikasi 404 untuk transaction_id tidak dikenal | `web/api/travel.py:136-138` | [X] |

**Phase 2 Gate:** Kedua alur end-to-end berjalan ✓

---

## Phase 3: OCR Non-Stopper & Confidence

| ID  | Task | File | Status |
|-----|------|------|--------|
| 3.1 | Cek `extraction_confidence` di output model agent | `baca_invoice/models/` | [X] |
| 3.2 | Cek `_extract_confidence()` membaca nilai dengan benar | `web/api/travel.py:193-200` | [X] |
| 3.3 | Verifikasi fallback doc_type "unknown" → "hotel" + tidak raise | `web/api/travel.py:88-93` | [X] |
| 3.4 | Verifikasi job error → `status: "failed"` bukan HTTP 500 | `web/api/travel.py:162-174` | [X] |
| 3.5 | Verifikasi warning muncul saat confidence < 0.6 | `web/api/travel.py:203-210` | [X] |
| 3.6 | Verifikasi authenticity verdict trigger warning | `web/api/travel.py:211-218` | [X] |

**Phase 3 Gate:** Semua skenario error return response valid ✓
**Perbaikan:** Fallback warning kini dikomunikasikan ke PISmart via field `warning` di response.

---

## Phase 4: Contract Validation

| ID  | Task | File | Status |
|-----|------|------|--------|
| 4.1 | Bandingkan `travel_api_contract.json` vs FastAPI runtime schema | `docs/api/travel_api_contract.json` | [X] |
| 4.2 | Verifikasi `"openapi": "3.1.0"` di contract | `docs/api/travel_api_contract.json:2` | [X] |
| 4.3 | Verifikasi semua field model tercermin di contract | `docs/api/travel_api_contract.json` | [X] |
| 4.4 | Verifikasi `APIKeyHeader` security scheme | `docs/api/travel_api_contract.json:449-455` | [X] |

**Phase 4 Gate:** Contract valid dan sinkron ✓
