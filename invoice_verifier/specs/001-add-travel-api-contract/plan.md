# Implementation Plan: API Contract Integrasi Travel (ADS-16)

**Track ID:** 001-add-travel-api-contract
**Spec:** [spec.md](./spec.md)
**Created:** 2026-05-18
**Status:** [ ] Not Started

## Overview

Verifikasi dan lengkapi implementasi API contract integrasi travel antara PISmart dan PINTER.
Sebagian besar kode sudah ada — fokus pada gap verification dan perbaikan yang diperlukan.

## Phase 1: Foundation Verification

Verifikasi bahwa semua komponen dasar terdaftar dan terkonfigurasi dengan benar.

### Tasks

- [ ] Task 1.1: Cek router travel sudah di-include di `web/main.py`
- [ ] Task 1.2: Cek `TRAVEL_API_KEY` terdaftar di `web/config.py` dan `.env_example`
- [ ] Task 1.3: Cek `travel.py` router terdaftar dengan prefix `/api/travel`

### Verification

- [ ] `GET /docs` atau `/openapi.json` memperlihatkan endpoint `/api/travel/submit` dan `/api/travel/result/{id}`

## Phase 2: Core API Behavior

Verifikasi kedua alur utama sesuai spec ADS-16.

### Tasks

- [ ] Task 2.1: Verifikasi `POST /api/travel/submit` mengembalikan `transaction_id` + status `processing`
- [ ] Task 2.2: Verifikasi `GET /api/travel/result/{transaction_id}` mengembalikan JSON lengkap
- [ ] Task 2.3: Verifikasi field `document_type` di-echo back di kedua response
- [ ] Task 2.4: Verifikasi validasi `document_type` hanya menerima `"invoice"` atau `"receipt"`
- [ ] Task 2.5: Verifikasi `404` jika `transaction_id` tidak dikenal

### Verification

- [ ] Kedua alur API berjalan end-to-end dengan PDF dummy

## Phase 3: OCR Non-Stopper & Confidence Level

Verifikasi bahwa OCR tidak memblokir alur dan confidence level tampil dengan benar.

### Tasks

- [ ] Task 3.1: Verifikasi agent output mengandung `extraction_confidence` (cek `baca_invoice/models/`)
- [ ] Task 3.2: Verifikasi `_extract_confidence()` membaca nilai dari result agent dengan benar
- [ ] Task 3.3: Verifikasi fallback ke `"hotel"` ketika `doc_type == "unknown"` (tidak raise error)
- [ ] Task 3.4: Verifikasi job error mengembalikan `status: "failed"` bukan HTTP 500
- [ ] Task 3.5: Verifikasi warning muncul saat `ocr_confidence < 0.6`
- [ ] Task 3.6: Verifikasi `authenticity.verdict` trigger warning untuk MENCURIGAKAN / PALSU/DIEDIT

### Verification

- [ ] Semua skenario non-stopper menghasilkan response valid (bukan exception)

## Phase 4: Contract Validation

Verifikasi OpenAPI contract sinkron dengan implementasi aktual.

### Tasks

- [ ] Task 4.1: Bandingkan `travel_api_contract.json` dengan schema FastAPI runtime (`/openapi.json`)
- [ ] Task 4.2: Verifikasi contract menggunakan `"openapi": "3.1.0"`
- [ ] Task 4.3: Verifikasi semua field request/response model tercermin di contract
- [ ] Task 4.4: Verifikasi security scheme `APIKeyHeader` terdefinisi di contract

### Verification

- [ ] Contract JSON valid dan sinkron dengan runtime schema

## Final Verification

- [ ] Semua acceptance criteria di spec.md terpenuhi
- [ ] Tidak ada HTTP 500 pada skenario error normal
- [ ] `docs/api/API.md` dokumentasi sesuai dengan implementasi aktual
- [ ] Postman collection (`docs/api/travel_api_postman_collection.json`) mencakup kedua alur
