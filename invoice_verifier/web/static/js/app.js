'use strict';

// ─── Konstanta ────────────────────────────────────────────────────────────────
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 200; // ~5 menit

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  file: null,
  trxId: null,
  pollTimer: null,
  pollAttempts: 0,
};

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dropZone       = $('drop-zone');
const fileInput      = $('file-input');
const fileInfo       = $('file-info');
const fileName       = $('file-name');
const btnClear       = $('btn-clear');
const btnSubmit      = $('btn-submit');
const progressCard   = $('progress-card');
const progressFill   = $('progress-fill');
const progressStatus = $('progress-status');
const progressPct    = $('progress-pct');
const jobIdLabel     = $('job-id-label');
const activityLog    = $('activity-log');
const logBadge       = $('log-badge');
const resultPanel    = $('result-panel');

// ─── File selection ───────────────────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});
btnClear.addEventListener('click', clearFile);

function setFile(f) {
  if (!f.name.toLowerCase().endsWith('.pdf')) {
    alert('Hanya file PDF yang diterima.');
    return;
  }
  state.file = f;
  fileName.textContent = f.name;
  fileInfo.classList.remove('hidden');
  btnSubmit.disabled = false;
}

function clearFile() {
  state.file = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  btnSubmit.disabled = true;
}

// ─── Submit ───────────────────────────────────────────────────────────────────
btnSubmit.addEventListener('click', startVerification);

async function startVerification() {
  if (!state.file) return;
  resetUI();

  btnSubmit.disabled = true;
  progressCard.classList.remove('hidden');
  setProgressStatus('Mengunggah file...', 5);

  const form = new FormData();
  form.append('file', state.file);

  try {
    const res = await fetch('/api/pinter/upload', { method: 'POST', body: form });
    const body = await res.json();

    if (!res.ok) {
      const msg = body.message || 'Upload gagal.';
      const code = body.error_code || 'UNKNOWN';
      showError(`${msg} (${code})`);
      btnSubmit.disabled = false;
      return;
    }

    state.trxId = body.trx_id;
    jobIdLabel.textContent = `Trx ${body.trx_id.slice(0, 8)}…`;
    addLogEntry({ kind: 'status', author: 'System', text: body.message });
    setProgressStatus('Memproses dokumen...', 15);
    pollResult();
  } catch (e) {
    showError(e.message);
    btnSubmit.disabled = false;
  }
}

// ─── Polling ──────────────────────────────────────────────────────────────────
async function pollResult() {
  if (state.pollAttempts >= MAX_POLL_ATTEMPTS) {
    showError('Timeout — proses ekstraksi terlalu lama.');
    btnSubmit.disabled = false;
    return;
  }
  state.pollAttempts++;

  try {
    const res = await fetch(`/api/pinter/extract?trx_id=${encodeURIComponent(state.trxId)}`);
    const body = await res.json();

    if (!res.ok) {
      const msg = body.message || 'Gagal mengambil hasil.';
      const code = body.error_code || 'UNKNOWN';
      showError(`${msg} (${code})`);
      btnSubmit.disabled = false;
      return;
    }

    if (body.status === 'progress') {
      bumpProgress();
      state.pollTimer = setTimeout(pollResult, POLL_INTERVAL_MS);
      return;
    }

    if (body.status === 'fail') {
      addLogEntry({ kind: 'error', author: 'System', text: body.message });
      showError(body.message || 'Verifikasi gagal.');
      btnSubmit.disabled = false;
      return;
    }

    if (body.status === 'success') {
      setProgressStatus('Verifikasi selesai!', 100);
      progressCard.querySelector('.progress-spinner').style.display = 'none';
      addLogEntry({ kind: 'done', author: 'System', text: 'Ekstraksi berhasil.' });
      renderResult(body.data || {});
      btnSubmit.disabled = false;
    }
  } catch (e) {
    addLogEntry({ kind: 'error', author: 'System', text: e.message });
    state.pollTimer = setTimeout(pollResult, POLL_INTERVAL_MS);
  }
}

function bumpProgress() {
  const current = parseInt(progressFill.style.width) || 15;
  const next = Math.min(85, current + 5);
  progressFill.style.width = `${next}%`;
  progressPct.textContent = `${next}%`;
}

// ─── Result rendering ─────────────────────────────────────────────────────────
function renderResult(data) {
  resultPanel.classList.remove('hidden');

  const docType = data.doc_type || 'unknown';
  renderSummary(data, docType);

  switch (docType) {
    case 'invoice': renderInvoiceDetail(data); break;
    case 'receipt': renderReceiptDetail(data); break;
    case 'unknown': renderUnknownDetail(data); break;
    default:        renderRawDetail(data);
  }

  renderAuthenticity(data.authenticity || {});
  initTabs();
  resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderSummary(r, docType) {
  const auth = r.authenticity || {};
  const verdict = verdictNormalized(auth.verdict);
  const verdictClass = resolveVerdictClass(verdict);
  const verdictEmoji = {
    'verdict-autentik':     '✓',
    'verdict-mencurigakan': '⚠',
    'verdict-palsu':        '✗',
  }[verdictClass] || '?';

  const total = fmt(r.total_payment || 0, r.currency || 'IDR');
  const confidence = Math.round((auth.confidence_score ?? r.extraction_confidence ?? 0) * 100);
  const desc = (r.summary && r.summary !== '-') ? r.summary : '';

  const docTypeLabel = {
    invoice: 'INVOICE',
    receipt: 'RECEIPT',
    unknown: 'TIDAK TERKLASIFIKASI',
  }[docType] || docType.toUpperCase();

  const manualHtml = r.requires_manual_review
    ? `<div class="manual-alert">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        Memerlukan review manual
      </div>`
    : '';

  $('result-summary').innerHTML = `
    ${manualHtml}
    <div class="verdict-banner ${verdictClass}">
      <div class="verdict-left">
        <div class="verdict-icon-wrap">${verdictEmoji}</div>
        <div class="verdict-info">
          <div class="verdict-label">Hasil Verifikasi — ${docTypeLabel}</div>
          <div class="verdict-text">${escHtml(verdict || 'TIDAK DIKETAHUI')}</div>
          ${desc ? `<div class="verdict-desc">${escHtml(desc)}</div>` : ''}
        </div>
      </div>
      <div class="verdict-right">
        <div class="verdict-total">${total}</div>
        <div class="verdict-meta">Authentic Level</div>
        <div class="confidence-bar-wrap">
          <div class="confidence-bar-bg">
            <div class="confidence-bar-fill" id="conf-bar" style="width:0%"></div>
          </div>
          <span class="confidence-pct" id="conf-pct">0%</span>
        </div>
      </div>
    </div>`;

  requestAnimationFrame(() => {
    const bar = document.getElementById('conf-bar');
    const pct = document.getElementById('conf-pct');
    if (bar) bar.style.width = `${confidence}%`;
    if (pct) animateCounter(pct, confidence);
  });
}

function renderInvoiceDetail(r) {
  // Support BOTH the new InvoiceResult schema AND the legacy HotelInvoiceResult schema
  // (when stage-2 routing picked hotel_agent, output uses hotel fields with doc_type=invoice).
  const isHotelShape = 'hotel_name' in r || 'check_in_date' in r;

  if (isHotelShape) {
    return renderHotelInvoiceDetail(r);
  }

  const items = (r.line_items || []).map(it =>
    `<div class="addon-row">
      <span class="addon-label">${escHtml(it.description || '—')} (x${it.quantity || 0})</span>
      <span class="addon-value">${fmt(it.subtotal, r.currency)}</span>
    </div>`
  ).join('');

  $('tab-detail').innerHTML = sections([
    ['Informasi Invoice', {
      'Nomor Invoice':   r.invoice_number,
      'Tanggal Terbit':  r.issue_date,
      'Jatuh Tempo':     r.due_date,
      'Termin':          r.payment_terms,
    }],
    ['Vendor / Penjual', {
      'Nama':    r.vendor_name,
      'Alamat':  r.vendor_address,
      'NPWP':    r.vendor_npwp,
      'Telepon': r.vendor_phone,
      'Email':   r.vendor_email,
    }],
    ['Pembeli', {
      'Nama':   r.buyer_name,
      'Alamat': r.buyer_address,
      'NPWP':   r.buyer_npwp,
    }],
    ['Rincian Biaya', {
      'Subtotal':         fmt(r.subtotal, r.currency),
      'Diskon':           fmt(r.discount, r.currency),
      'Pajak (PPN)':      fmt(r.tax, r.currency),
      'Total Pembayaran': fmt(r.total_payment, r.currency),
    }],
  ]);

  if (items) {
    $('tab-detail').innerHTML += `
      <div class="field-section">
        <div class="field-section-title">Line Items</div>
        <div class="addons-list">${items}</div>
      </div>`;
  }
}

function renderHotelInvoiceDetail(r) {
  $('tab-detail').innerHTML = sections([
    ['Informasi Booking', {
      'Order ID':           r.order_id,
      'Order Detail ID':    r.order_detail_id,
      'Tanggal Booking':    r.booking_date,
      'Tanggal Pembayaran': r.payment_date,
    }],
    ['Data Pemesan', {
      'Nama':    r.booker_name,
      'Email':   r.booker_email,
      'Telepon': r.booker_phone,
    }],
    ['Detail Hotel', {
      'Nama Hotel': r.hotel_name,
      'Alamat':     r.hotel_address,
      'Kota':       r.hotel_city,
      'Telepon':    r.hotel_phone,
    }],
    ['Detail Kamar', {
      'Tipe Kamar':    r.room_type,
      'Jumlah Kamar':  r.total_rooms,
      'Kapasitas':     r.room_capacity,
      'Check-in':      `${r.check_in_date || '—'} ${r.check_in_time || ''}`.trim(),
      'Check-out':     `${r.check_out_date || '—'} ${r.check_out_time || ''}`.trim(),
      'Jumlah Malam':  r.total_nights,
      'Sarapan':       r.breakfast_included ? 'Termasuk' : 'Tidak termasuk',
      'Fasilitas':     r.facilities,
    }],
    ['Rincian Biaya', {
      'Subtotal':          fmt(r.subtotal, r.currency),
      'Diskon':            fmt(r.discount, r.currency),
      'Pajak':             fmt(r.tax, r.currency),
      'Total Pembayaran':  fmt(r.total_payment, r.currency),
      'Metode Pembayaran': r.payment_method,
    }],
    ['Provider', {
      'Provider':   r.provider,
      'Perusahaan': r.provider_company,
      'Alamat':     r.provider_address,
    }],
  ]);
}

function renderReceiptDetail(r) {
  // Support both new ReceiptResult and legacy FlightTicketResult shapes
  const isFlightShape = 'airline' in r || 'route_from' in r;
  if (isFlightShape) {
    return renderFlightReceiptDetail(r);
  }

  const items = (r.items_purchased || []).map(it =>
    `<div class="addon-row">
      <span class="addon-label">${escHtml(it.description || '—')} (x${it.quantity || 0})</span>
      <span class="addon-value">${fmt(it.price, r.currency)}</span>
    </div>`
  ).join('');

  $('tab-detail').innerHTML = sections([
    ['Informasi Receipt', {
      'Nomor Receipt':    r.receipt_number,
      'Tanggal Transaksi':r.transaction_date,
      'Tanggal Bayar':    r.payment_date,
    }],
    ['Merchant', {
      'Nama':    r.merchant_name,
      'Alamat':  r.merchant_address,
      'Telepon': r.merchant_phone,
    }],
    ['Pembayar', {
      'Nama':    r.payer_name,
      'Email':   r.payer_email,
      'Telepon': r.payer_phone,
    }],
    ['Rincian Biaya', {
      'Subtotal':         fmt(r.subtotal, r.currency),
      'Pajak':            fmt(r.tax, r.currency),
      'Biaya Layanan':    fmt(r.service_fee, r.currency),
      'Total Pembayaran': fmt(r.total_payment, r.currency),
      'Metode Bayar':     r.payment_method,
      'Status Bayar':     r.payment_status,
    }],
  ]);

  if (items) {
    $('tab-detail').innerHTML += `
      <div class="field-section">
        <div class="field-section-title">Items Dibeli</div>
        <div class="addons-list">${items}</div>
      </div>`;
  }
}

function renderFlightReceiptDetail(r) {
  $('tab-detail').innerHTML = sections([
    ['Informasi Booking', {
      'No. Receipt':       r.receipt_number,
      'No. PO':            r.po_number,
      'Tanggal Booking':   r.booking_date,
      'Status Transaksi':  r.transaction_status,
    }],
    ['Data Pemesan', {
      'Nama':    r.traveler_name,
      'Email':   r.traveler_email,
      'Telepon': r.traveler_phone,
    }],
    ['Detail Penerbangan', {
      'Maskapai':        r.airline,
      'Rute':            `${r.route_from || '—'} → ${r.route_to || '—'}`,
      'Tanggal Terbang': r.flight_date,
      'Kelas':           r.seat_class,
      'Tipe Penumpang':  r.passenger_type,
    }],
    ['Rincian Biaya', {
      'Harga Tiket':       fmt(r.ticket_price, r.currency),
      'Subtotal':          fmt(r.subtotal, r.currency),
      'Biaya Layanan':     fmt(r.service_fee, r.currency),
      'Total Pembayaran':  fmt(r.total_payment, r.currency),
      'Metode Pembayaran': r.payment_method,
    }],
    ['Provider', {
      'Provider':   r.provider,
      'Perusahaan': r.provider_company,
      'NPWP':       r.provider_npwp,
    }],
  ]);
}

function renderUnknownDetail(r) {
  const reasons = (r.review_reasons || []).map(x => `<li>${escHtml(x)}</li>`).join('');
  $('tab-detail').innerHTML = `
    <div class="field-section">
      <div class="field-section-title">Status Klasifikasi</div>
      <div class="analysis-note">
        ${escHtml(r.summary || 'Dokumen tidak terklasifikasi sebagai invoice atau receipt.')}
      </div>
    </div>
    ${reasons ? `
      <div class="field-section">
        <div class="field-section-title">Alasan</div>
        <ul class="evidence-list">${reasons}</ul>
      </div>
    ` : ''}
    <div class="field-section">
      <div class="field-section-title">Catatan</div>
      <div class="analysis-note">
        Tidak ada data ekstraksi yang dilakukan untuk dokumen ini. Authenticity tetap dianalisis berdasarkan metadata PDF (lihat tab Authenticity).
      </div>
    </div>`;
}

function renderRawDetail(r) {
  const entries = Object.entries(r)
    .filter(([k]) => k !== 'authenticity' && k !== 'doc_type')
    .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)]);
  $('tab-detail').innerHTML = sections([['Data', Object.fromEntries(entries)]]);
}

function renderAuthenticity(auth) {
  const verdict = verdictNormalized(auth.verdict);
  const isActuallySuspicious = auth.is_suspicious ||
    verdict.includes('MENCURIGAKAN') ||
    verdict.includes('PALSU') ||
    verdict.includes('DIEDIT');

  const score = Math.round((auth.confidence_score ?? 1) * 100);

  const suspiciousHtml = isActuallySuspicious
    ? `<span class="suspicious-yes">⚠ Ya</span>`
    : `<span class="suspicious-no">✓ Tidak</span>`;

  let html = `
    <div class="field-section">
      <div class="field-section-title">Analisis Dokumen</div>
      <div class="field-grid">
        ${fieldItem('Verdict', escHtml(verdict || '—'))}
        ${fieldItem('Mencurigakan', suspiciousHtml, true)}
        ${fieldItem('Confidence Score', `${score}%`)}
        ${fieldItem('Provider Terdeteksi', escHtml(auth.detected_provider || '—'))}
        ${fieldItem('PDF Creator', escHtml(auth.pdf_creator || '—'))}
        ${fieldItem('PDF Producer', escHtml(auth.pdf_producer || '—'))}
        ${fieldItem('Tanggal Dibuat', escHtml(auth.creation_date || '—'))}
        ${fieldItem('Tanggal Dimodifikasi', escHtml(auth.modification_date || '—'))}
        ${fieldItem('Dokumen Dimodifikasi', auth.was_modified ? '<span style="color:#d97706;font-weight:600">Ya</span>' : 'Tidak', true)}
      </div>
    </div>`;

  if (auth.warning_flags && auth.warning_flags.length) {
    const chips = auth.warning_flags.map(f =>
      `<span class="flag-chip">${escHtml(f)}</span>`
    ).join('');
    html += `<div class="field-section">
      <div class="field-section-title">Warning Flags</div>
      <div class="flags-list">${chips}</div>
    </div>`;
  }

  if (auth.fake_evidence && auth.fake_evidence.length) {
    const items = auth.fake_evidence.map(e =>
      `<li class="evidence-item">
        <svg class="evidence-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        ${escHtml(e)}
      </li>`
    ).join('');
    html += `<div class="field-section">
      <div class="field-section-title">Bukti Kecurangan</div>
      <ul class="evidence-list">${items}</ul>
    </div>`;
  }

  if (auth.analysis_notes && auth.analysis_notes !== '-') {
    html += `<div class="field-section">
      <div class="field-section-title">Catatan Analisis</div>
      <div class="analysis-note">${escHtml(auth.analysis_notes)}</div>
    </div>`;
  }

  $('tab-authenticity').innerHTML = html;
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      $(`tab-${btn.dataset.tab}`).classList.add('active');
    });
  });
}

// ─── Activity log ─────────────────────────────────────────────────────────────
let _logCount = 0;
function addLogEntry({ kind, author, text }) {
  const empty = activityLog.querySelector('.log-empty');
  if (empty) empty.remove();

  _logCount++;
  const icon = iconForKind(kind);
  const now = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const entry = document.createElement('div');
  entry.className = `log-entry agent-system`;
  entry.style.animationDelay = `${Math.min(_logCount * 30, 200)}ms`;
  entry.innerHTML = `
    <div class="log-dot">${icon}</div>
    <div class="log-body">
      <div class="log-author">${escHtml(author)}</div>
      <div class="log-text">${escHtml(text)}</div>
      <div class="log-time">${now}</div>
    </div>`;

  activityLog.appendChild(entry);
  activityLog.scrollTop = activityLog.scrollHeight;

  logBadge.textContent = _logCount;
  logBadge.classList.remove('hidden');
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function animateCounter(el, target, duration = 900) {
  const start = performance.now();
  const tick = now => {
    const t = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = `${Math.round(ease * target)}%`;
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function sections(defs) {
  return defs.map(([title, fields]) => {
    const items = Object.entries(fields).map(([label, val]) => {
      const v = (val === null || val === undefined || val === '-' || val === '') ? null : String(val);
      return fieldItem(label, v ? escHtml(v) : null);
    }).join('');
    return `<div class="field-section">
      <div class="field-section-title">${escHtml(title)}</div>
      <div class="field-grid">${items}</div>
    </div>`;
  }).join('');
}

function fieldItem(label, valueHtml, rawHtml = false) {
  const isEmpty = !valueHtml || valueHtml === 'null';
  return `<div class="field-item">
    <div class="field-label">${label}</div>
    <div class="field-value ${isEmpty ? 'empty' : ''}">${isEmpty ? '—' : valueHtml}</div>
  </div>`;
}

function verdictNormalized(raw) {
  if (!raw || raw === '-') return '';
  const v = String(raw).trim().toUpperCase();
  if (v === 'SUSPICIOUS') return 'MENCURIGAKAN';
  if (v === 'FAKE' || v === 'EDITED' || v === 'PALSU' || v.includes('DIEDIT')) return 'PALSU/DIEDIT';
  if (v === 'AUTHENTIC' || v === 'ASLI') return 'AUTENTIK';
  return v;
}

function resolveVerdictClass(verdict) {
  if (!verdict) return 'verdict-unknown';
  if (verdict.includes('PALSU') || verdict.includes('DIEDIT')) return 'verdict-palsu';
  if (verdict.includes('MENCURIGAKAN'))                         return 'verdict-mencurigakan';
  if (verdict.includes('AUTENTIK'))                             return 'verdict-autentik';
  return 'verdict-unknown';
}

function fmt(amount, currency = 'IDR') {
  const n = Number(amount) || 0;
  if (n === 0) return '—';
  try {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `${currency} ${n.toLocaleString('id-ID')}`;
  }
}

function iconForKind(kind) {
  const map = {
    status:      '·',
    tool_call:   '⚙',
    tool_result: '✓',
    text:        '💬',
    error:       '✗',
    done:        '✓',
  };
  return map[kind] || '·';
}

function escHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function setProgressStatus(msg, pct) {
  progressStatus.textContent = msg;
  if (pct !== null) {
    progressFill.style.width = `${pct}%`;
    progressPct.textContent  = `${pct}%`;
  }
}

function showError(msg) {
  progressStatus.textContent = `Gagal: ${msg}`;
  progressFill.style.width   = '100%';
  progressFill.style.background = '#ef4444';
  const spinner = progressCard.querySelector('.progress-spinner');
  if (spinner) spinner.style.display = 'none';
}

function resetUI() {
  _logCount = 0;
  state.trxId = null;
  state.pollAttempts = 0;
  if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }

  activityLog.innerHTML = `<div class="log-empty">
    <svg viewBox="0 0 48 48" fill="none" width="40" height="40">
      <circle cx="24" cy="24" r="20" stroke="#e2e8f0" stroke-width="2"/>
      <path d="M16 24h12M24 16v12" stroke="#cbd5e1" stroke-width="2.5" stroke-linecap="round"/>
    </svg>
    <p>Memulai verifikasi...</p>
  </div>`;

  logBadge.classList.add('hidden');
  resultPanel.classList.add('hidden');

  progressFill.style.background = '';
  progressFill.style.width      = '0%';
  progressPct.textContent       = '0%';
  jobIdLabel.textContent        = '';

  const spinner = progressCard.querySelector('.progress-spinner');
  if (spinner) spinner.style.display = '';
}
