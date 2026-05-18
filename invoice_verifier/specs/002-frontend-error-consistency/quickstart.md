# Quickstart: Frontend & Error Consistency

**Tujuan**: Panduan singkat developer untuk mengeksekusi spec ini.

## Yang Berubah dalam 1 Menit

| Sebelum | Sesudah |
|---------|---------|
| Frontend `POST /api/verify/upload` + SSE | `POST /api/pinter/upload` + polling `GET /api/pinter/extract` |
| Render duck-type (`'airline' in data`) | Switch `data.doc_type` |
| 422 default FastAPI `{detail: [...]}` | 400 seragam `{status, message, error_code}` |

## Urutan Pekerjaan

### Tahap 1 — Backend Exception Handler

Edit `web/main.py`:

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

def _err(message: str, code: str, http: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=http,
        content={"status": "fail", "message": message, "error_code": code},
    )

@app.exception_handler(RequestValidationError)
async def _validation_handler(request, exc):
    errors = exc.errors()
    loc_paths = [tuple(e["loc"]) for e in errors]
    if ("body", "file") in loc_paths:
        return _err("File PDF wajib diisi.", "MISSING_FILE")
    if ("query", "trx_id") in loc_paths:
        return _err("Parameter trx_id wajib diisi.", "MISSING_TRX_ID")
    msg = errors[0]["msg"] if errors else "Permintaan tidak valid."
    return _err(msg, "VALIDATION_ERROR")
```

**Penting**: Pastikan handler ini di-register **sebelum** `app.mount(...)` static files.

### Tahap 2 — Frontend Rewrite

Rewrite `web/static/js/app.js` (sketsa):

```javascript
const state = { file: null, trxId: null, pollTimer: null };

async function startVerification() {
  resetUI();
  const form = new FormData();
  form.append('file', state.file);

  const res = await fetch('/api/pinter/upload', { method: 'POST', body: form });
  const body = await res.json();
  if (!res.ok) return showError(body.message, body.error_code);

  state.trxId = body.trx_id;
  setStatus(body.message, 10);
  pollResult();
}

async function pollResult() {
  const res = await fetch(`/api/pinter/extract?trx_id=${encodeURIComponent(state.trxId)}`);
  const body = await res.json();

  if (body.status === 'progress') {
    bumpProgress();
    state.pollTimer = setTimeout(pollResult, 1500);
    return;
  }
  if (body.status === 'fail') {
    return showError(body.message, body.error_code);
  }
  if (body.status === 'success') {
    setStatus('Selesai!', 100);
    renderResult(body.data);
  }
}

function renderResult(data) {
  switch (data.doc_type) {
    case 'invoice': renderInvoiceDetail(data); break;
    case 'receipt': renderReceiptDetail(data); break;
    case 'unknown': renderUnknownDetail(data); break;
    default:        renderRawDetail(data);
  }
  renderAuthenticity(data.authenticity || {});
}
```

**Catatan**: Hapus semua `EventSource`, `state.jobId`, `state.jobToken`, dan agent_event handling — semua diganti oleh polling sederhana.

### Tahap 3 — Tests

Edit `tests/integration/test_upload.py`:

```python
async def test_upload_reject_missing_file_returns_uniform_error(client):
    resp = await client.post("/api/pinter/upload")
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "fail"
    assert body["error_code"] == "MISSING_FILE"
```

Edit `tests/integration/test_pinter_extract.py`:

```python
async def test_extract_missing_trx_id_returns_400(client):
    resp = await client.get("/api/pinter/extract")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "MISSING_TRX_ID"
```

### Tahap 4 — Update Dokumentasi

Tambahkan ke README.md tabel error codes:
- `MISSING_TRX_ID` (400)
- `VALIDATION_ERROR` (400)

## Smoke Test Manual

```bash
# 1. Start server
python run_web.py

# 2. Open browser → http://localhost:8080
# Upload PDF, harus berhasil sampai render hasil

# 3. Test error format via curl
curl -i -X POST http://localhost:8080/api/pinter/upload
# Expect: HTTP/1.1 400, body { status: "fail", error_code: "MISSING_FILE", ... }

curl -i http://localhost:8080/api/pinter/extract
# Expect: HTTP/1.1 400, body { status: "fail", error_code: "MISSING_TRX_ID", ... }
```

Kunci sukses:
- UI bisa upload dan render hasil tanpa error console
- Test `pytest tests/ -q` → ≥ 41 passed (39 existing + 2 baru)
- curl tanpa file/trx_id → response seragam HTTP 400

## Next Steps

1. Run `/speckit-tasks` untuk breakdown granular
2. Run `/speckit-implement` untuk eksekusi
