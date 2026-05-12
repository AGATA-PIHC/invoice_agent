'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  file: null,
  jobId: null,
  jobToken: null,
  eventSource: null,
  eventCount: 0,
  totalExpectedEvents: 8,
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
    const res = await fetch('/api/verify/upload', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      if (res.status === 422 && err.detail?.code === 'UNSUPPORTED_DOCUMENT') {
        showRejection(err.detail);
        return;
      }
      throw new Error(err.detail?.message || err.detail || 'Upload gagal.');
    }
    const data = await res.json();
    state.jobId    = data.job_id;
    state.jobToken = data.token;
    jobIdLabel.textContent = `Job ${data.job_id.slice(0, 8)}…`;

    setProgressStatus('Terhubung ke agent...', 10);
    connectSSE(state.jobId, state.jobToken);
  } catch (e) {
    showError(e.message);
  }
}

// ─── SSE ──────────────────────────────────────────────────────────────────────
function connectSSE(jobId, token) {
  if (state.eventSource) state.eventSource.close();

  const url = `/api/verify/${jobId}/stream?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
  state.eventSource = es;

  es.onmessage = e => {
    try { handleEvent(JSON.parse(e.data)); } catch (_) {}
  };

  es.onerror = () => {
    es.close();
    if (state.jobId && state.jobToken) {
      setTimeout(() => connectSSE(state.jobId, state.jobToken), 1500);
    }
  };
}

// ─── Event handler ────────────────────────────────────────────────────────────
function handleEvent(ev) {
  state.eventCount++;
  updateProgress();

  switch (ev.type) {
    case 'status':
      addLogEntry({ kind: 'status', author: 'System', text: ev.message });
      setProgressStatus(ev.message, null);
      break;

    case 'agent_event':
      handleAgentEvent(ev);
      break;

    case 'complete':
      setProgressStatus('Verifikasi selesai!', 100);
      progressCard.querySelector('.progress-spinner').style.display = 'none';
      addLogEntry({ kind: 'done', author: 'System', text: 'Verifikasi selesai.' });
      if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
      if (ev.result) renderResult(ev.result);
      btnSubmit.disabled = false;
      break;

    case 'error':
      setProgressStatus('Terjadi kesalahan.', null);
      addLogEntry({ kind: 'error', author: 'System', text: ev.message });
      if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
      showError(ev.message);
      btnSubmit.disabled = false;
      break;
  }
}

function handleAgentEvent(ev) {
  const { author, kind, tool, success, text } = ev;
  let logText = '';

  switch (kind) {
    case 'tool_call':
      logText = `Memanggil ${formatToolName(tool)}…`;
      setProgressStatus(logText, null);
      break;
    case 'tool_result':
      logText = success
        ? `${formatToolName(tool)} selesai`
        : `${formatToolName(tool)} gagal`;
      break;
    case 'text':
      logText = truncate(text, 140);
      break;
    default:
      logText = kind;
  }

  addLogEntry({ kind, author, text: logText });
}

// ─── Animated counter ─────────────────────────────────────────────────────────
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

// ─── Activity log ─────────────────────────────────────────────────────────────
function addLogEntry({ kind, author, text }) {
  const empty = activityLog.querySelector('.log-empty');
  if (empty) empty.remove();

  const agentClass = classifyAgent(author);
  const icon = iconForKind(kind);
  const now = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const entry = document.createElement('div');
  entry.className = `log-entry ${agentClass}`;
  entry.style.animationDelay = `${Math.min(state.eventCount * 30, 200)}ms`;
  entry.innerHTML = `
    <div class="log-dot">${icon}</div>
    <div class="log-body">
      <div class="log-author">${escHtml(author)}</div>
      <div class="log-text">${escHtml(text)}</div>
      <div class="log-time">${now}</div>
    </div>`;

  activityLog.appendChild(entry);
  activityLog.scrollTop = activityLog.scrollHeight;

  logBadge.textContent = state.eventCount;
  logBadge.classList.remove('hidden');
}

// ─── Result rendering ─────────────────────────────────────────────────────────
function renderResult(result) {
  resultPanel.classList.remove('hidden');

  // Unwrap {agent_name_response: {...}} if the LLM returned a wrapped object.
  const keys = Object.keys(result || {});
  const data = (keys.length === 1 && keys[0].endsWith('_response') && result[keys[0]] && typeof result[keys[0]] === 'object')
    ? result[keys[0]]
    : result;

  const isFlight = 'airline' in data || 'route_from' in data;
  const isHotel  = 'hotel_name' in data || 'check_in_date' in data;

  renderSummary(data, isFlight ? 'flight' : isHotel ? 'hotel' : 'unknown');

  if (isFlight) renderFlightDetail(data);
  else if (isHotel) renderHotelDetail(data);
  else renderRawDetail(data);

  renderAuthenticity(data.authenticity || {});
  initTabs();

  resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderSummary(r, docType) {
  const auth    = r.authenticity || {};
  const verdict = verdictNormalized(auth.verdict);
  const verdictClass = resolveVerdictClass(verdict);
  const verdictEmoji = {
    'verdict-autentik':     '✓',
    'verdict-mencurigakan': '⚠',
    'verdict-palsu':        '✗',
  }[verdictClass] || '?';

  const total      = fmt(r.total_payment || 0, r.currency || 'IDR');
  const confidence = Math.round((auth.confidence_score ?? r.extraction_confidence ?? 0) * 100);
  const desc       = (r.summary && r.summary !== '-') ? r.summary : '';

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
          <div class="verdict-label">Hasil Verifikasi</div>
          <div class="verdict-text">${escHtml(verdict || 'TIDAK DIKETAHUI')}</div>
          ${desc ? `<div class="verdict-desc">${escHtml(desc)}</div>` : ''}
        </div>
      </div>
      <div class="verdict-right">
        <div class="verdict-total">${total}</div>
        <div class="verdict-meta">Confidence</div>
        <div class="confidence-bar-wrap">
          <div class="confidence-bar-bg">
            <div class="confidence-bar-fill" id="conf-bar" style="width:0%"></div>
          </div>
          <span class="confidence-pct" id="conf-pct">0%</span>
        </div>
      </div>
    </div>`;

  // Animate confidence bar and counter after paint
  requestAnimationFrame(() => {
    const bar = document.getElementById('conf-bar');
    const pct = document.getElementById('conf-pct');
    if (bar) bar.style.width = `${confidence}%`;
    if (pct) animateCounter(pct, confidence);
  });
}

function renderFlightDetail(r) {
  $('tab-detail').innerHTML = sections([
    ['Informasi Booking', {
      'No. Receipt':        r.receipt_number,
      'No. PO':             r.po_number,
      'Tanggal Booking':    r.booking_date,
      'Status Transaksi':   r.transaction_status,
    }],
    ['Data Pemesan', {
      'Nama':    r.traveler_name,
      'Email':   r.traveler_email,
      'Telepon': r.traveler_phone,
    }],
    ['Detail Penerbangan', {
      'Maskapai':         r.airline,
      'Rute':             `${r.route_from || '—'} → ${r.route_to || '—'}`,
      'Tanggal Terbang':  r.flight_date,
      'Kelas':            r.seat_class,
      'Tipe Penumpang':   r.passenger_type,
    }],
    ['Rincian Biaya', {
      'Harga Tiket':       fmt(r.ticket_price, r.currency),
      'Subtotal':          fmt(r.subtotal, r.currency),
      'Biaya Layanan':     fmt(r.service_fee, r.currency),
      'Total Pembayaran':  fmt(r.total_payment, r.currency),
      'Metode Pembayaran': r.payment_method,
    }],
    ['Provider', {
      'Provider':    r.provider,
      'Perusahaan':  r.provider_company,
      'NPWP':        r.provider_npwp,
    }],
  ]);

  if (r.addons && r.addons.length) {
    const rows = r.addons.map(a =>
      `<div class="addon-row">
        <span class="addon-label">${escHtml(a.description || '—')}</span>
        <span class="addon-value">${fmt(a.price, r.currency)}</span>
      </div>`
    ).join('');
    $('tab-detail').innerHTML += `
      <div class="field-section">
        <div class="field-section-title">Add-ons</div>
        <div class="addons-list">${rows}</div>
      </div>`;
  }
}

function renderHotelDetail(r) {
  $('tab-detail').innerHTML = sections([
    ['Informasi Booking', {
      'Order ID':          r.order_id,
      'Order Detail ID':   r.order_detail_id,
      'Tanggal Booking':   r.booking_date,
      'Tanggal Pembayaran':r.payment_date,
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

function renderRawDetail(r) {
  const entries = Object.entries(r)
    .filter(([k]) => k !== 'authenticity')
    .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)]);
  $('tab-detail').innerHTML = sections([['Data', Object.fromEntries(entries)]]);
}

function renderAuthenticity(auth) {
  const verdict = verdictNormalized(auth.verdict);

  // ── Logic fix: is_suspicious is derived from verdict, not just the raw flag ──
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

// ─── Helpers ──────────────────────────────────────────────────────────────────
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

/** Normalise verdict string: trim, uppercase, map Indonesian variants. */
function verdictNormalized(raw) {
  if (!raw || raw === '-') return '';
  const v = String(raw).trim().toUpperCase();
  // Map common synonyms so keyword checks stay consistent
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

function classifyAgent(author = '') {
  const a = author.toLowerCase();
  if (a.includes('coordinator') || a.includes('invoice_verification')) return 'agent-coord';
  if (a.includes('authenticity'))                                       return 'agent-flight';
  if (a.includes('parser') || a.includes('document'))                  return 'agent-hotel';
  return 'agent-system';
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

function formatToolName(tool = '') {
  return tool.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function truncate(str = '', max = 140) {
  return str.length > max ? str.slice(0, max) + '…' : str;
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

function updateProgress() {
  const raw     = Math.min(90, 10 + (state.eventCount / state.totalExpectedEvents) * 80);
  const current = parseInt(progressFill.style.width) || 0;
  if (raw > current) {
    progressFill.style.width = `${Math.round(raw)}%`;
    progressPct.textContent  = `${Math.round(raw)}%`;
  }
}

function showError(msg) {
  progressStatus.textContent = `Gagal: ${msg}`;
  progressFill.style.width   = '100%';
  progressFill.style.background = '#ef4444';
  const spinner = progressCard.querySelector('.progress-spinner');
  if (spinner) spinner.style.display = 'none';
}

function showRejection(detail) {
  setProgressStatus('Dokumen ditolak', 100);
  progressFill.style.background = '#f59e0b';
  const spinner = progressCard.querySelector('.progress-spinner');
  if (spinner) spinner.style.display = 'none';
  addLogEntry({ kind: 'error', author: 'System', text: detail.message });
  if (detail.hint) addLogEntry({ kind: 'status', author: 'System', text: detail.hint });
  btnSubmit.disabled = false;
}

function resetUI() {
  state.eventCount = 0;
  state.jobId      = null;
  state.jobToken   = null;
  if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }

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
