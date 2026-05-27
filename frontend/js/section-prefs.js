// ── Consolidated Settings modal + Section toggles ──────────────────────────
//
// One ⚙ Settings entry-point in the sidebar opens a tabbed modal containing:
//   Sections · AI Model · API Keys · Usage Metrics · Data Management
// Each tab still calls its own load/save handlers (settings.js, keys.js,
// metrics.js, data-mgmt.js) — this file only handles the tab switching, the
// "Sections" pane, and the open/close lifecycle.

// Schema + saved prefs come back together from the backend.
let _secPrefsSchema = null;
let _secPrefsState = { sections: {}, fields: {} };

function openSettingsModal(tab) {
  document.getElementById('settings-modal').classList.add('open');
  // Default tab when none requested.
  switchSettingsTab(tab || 'set-pane-sections');
}

function closeSettingsModal() {
  document.getElementById('settings-modal').classList.remove('open');
}


function onSettingsTabClick(btn) {
  const target = btn.dataset.pane;
  switchSettingsTab(target);
}

function switchSettingsTab(paneId) {
  const modal = document.getElementById('settings-modal');
  if (!modal) return;
  // Only consider the top-level tab buttons in .settings-tabs — there are
  // nested .set-tabs inside the API Keys pane that must not be touched here.
  modal.querySelectorAll('.settings-tabs > .set-tab').forEach(t => {
    t.classList.toggle('on', t.dataset.pane === paneId);
  });
  // Same for panes — only top-level Settings panes (children of .settings-body).
  modal.querySelectorAll('.settings-body > .set-pane').forEach(p => {
    p.classList.toggle('on', p.id === paneId);
  });

  // Lazy-load each tab's data when first shown.
  if (paneId === 'set-pane-sections') loadSectionPrefs();
  if (paneId === 'set-pane-ai')       _hydrateAiTab();
  if (paneId === 'set-pane-keys')     refreshKeysModal();
  if (paneId === 'set-pane-metrics')  loadMetrics();
  if (paneId === 'set-pane-data')     { if (typeof _updateMasterUI === 'function') _updateMasterUI(); }
}

// Existing callers (sidebar buttons, shortcuts, prov pill) keep working — they
// just route into the unified modal with the appropriate tab pre-selected.
function openSettings() { openSettingsModal('set-pane-ai'); _hydrateAiTab(); }
function closeCfg()     { closeSettingsModal(); }
function openKeys()     { openSettingsModal('set-pane-keys'); }
function closeKeys()    { closeSettingsModal(); }
function openMetrics()  { openSettingsModal('set-pane-metrics'); }
function closeMetrics() { closeSettingsModal(); }
function openDataMgmt() { openSettingsModal('set-pane-data'); }
function closeDataMgmt(){ closeSettingsModal(); }

// Replicates the prefill logic that lived inside the old `openSettings()` in
// settings.js. Called whenever the AI Model tab becomes visible.
function _hydrateAiTab() {
  const p = (typeof curProv !== 'undefined' && curProv) ? curProv : 'openai';
  const sel = document.getElementById('prov-sel');
  if (sel) sel.value = p;
  if (typeof showProvSec === 'function') showProvSec(p);
  if (typeof curModel !== 'undefined' && curModel && typeof _modelsByProvider === 'object') {
    _modelsByProvider[p] = curModel;
  }
  if (typeof _hydrateAllProviderInputs === 'function') _hydrateAllProviderInputs();
  fetch(`${API}/api/app-settings`).then(r => r.ok ? r.json() : null).then(s => {
    if (!s) return;
    let srv = s.models_by_provider;
    if (typeof srv === 'string') { try { srv = JSON.parse(srv); } catch (e) { srv = null; } }
    if (srv && typeof srv === 'object' && typeof _modelsByProvider === 'object') {
      Object.assign(_modelsByProvider, srv);
      try { localStorage.setItem('sr_models_by_provider', JSON.stringify(_modelsByProvider)); } catch (e) {}
      if (typeof _hydrateAllProviderInputs === 'function') _hydrateAllProviderInputs();
    }
    // Populate base URL fields.
    const ollamaEl = document.getElementById('model-ollama-url');
    if (ollamaEl && s.ollama_base_url) ollamaEl.value = s.ollama_base_url;
    const customEl = document.getElementById('model-custom-url');
    if (customEl && s.openai_base_url) customEl.value = s.openai_base_url;
  }).catch(() => {});
  const tp = document.getElementById('llm-test-prompt');
  if (tp) tp.value = localStorage.getItem('sr_test_prompt') || 'Reply with one short sentence.';
  const st = document.getElementById('llm-test-status'); if (st) st.textContent = '';
  const rb = document.getElementById('llm-test-response'); if (rb) { rb.style.display = 'none'; rb.textContent = ''; }
}

// ── Sections pane ──────────────────────────────────────────────────────────

async function loadSectionPrefs() {
  const list = document.getElementById('sec-prefs-list');
  if (!list) return;
  if (_secPrefsSchema) {
    // Already loaded — re-render with whatever's in state (lets the user pop
    // between tabs without losing in-flight toggle changes).
    renderSectionPrefs();
    return;
  }
  try {
    const r = await fetch(`${API}/api/app-settings/section-preferences`);
    if (!r.ok) throw new Error('Failed to load section preferences');
    const d = await r.json();
    _secPrefsSchema = d.schema || [];
    _secPrefsState = {
      sections: (d.preferences && d.preferences.sections) || {},
      fields:   (d.preferences && d.preferences.fields)   || {},
    };
    renderSectionPrefs();
  } catch (e) {
    list.innerHTML = `<div style="color:var(--red);font-size:13px;padding:14px 0">⚠ ${esc(e.message)}</div>`;
  }
}

function _secSectionEnabled(key) {
  // Default = enabled when no override saved.
  return _secPrefsState.sections[key] !== false;
}

function _secFieldEnabled(secKey, fieldKey) {
  return _secPrefsState.fields[`${secKey}.${fieldKey}`] !== false;
}

function renderSectionPrefs() {
  const list = document.getElementById('sec-prefs-list');
  if (!list || !_secPrefsSchema) return;
  let html = '';
  _secPrefsSchema.forEach(sec => {
    const enabled = _secSectionEnabled(sec.key);
    const required = !!sec.required;
    const fields = sec.fields || [];
    html += `
      <div class="sec-pref-card${enabled ? '' : ' off'}" data-section="${esc(sec.key)}">
        <div class="sec-pref-head">
          <div class="sec-pref-label" title="${esc(sec.key)}">
            <div class="sec-pref-name">${esc(sec.label)}${required ? ' <span class="sec-pref-required">required</span>' : ''}</div>
          </div>
          ${required
            ? `<div class="toggle-sw on" style="opacity:.4;cursor:not-allowed" title="This section is required"></div>`
            : `<div class="toggle-sw${enabled ? ' on' : ''}" onclick="toggleSectionPref('${esc(sec.key)}',this)" title="Enable / disable this section"></div>`
          }
        </div>
        ${fields.length ? `
          <div class="sec-pref-fields"${enabled ? '' : ' style="opacity:.4;pointer-events:none"'}>
            ${fields.map(f => `
              <label class="sec-pref-field" title="${esc(f.key)}">
                <input type="checkbox" ${_secFieldEnabled(sec.key, f.key) ? 'checked' : ''}
                       onchange="toggleSectionField('${esc(sec.key)}','${esc(f.key)}',this.checked)">
                <span>${esc(f.label)}</span>
              </label>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  });
  list.innerHTML = html;
}

function toggleSectionPref(key, swEl) {
  const next = !swEl.classList.contains('on');
  _secPrefsState.sections[key] = next;
  // Re-render so the disabled-state styling on the subfields updates.
  renderSectionPrefs();
}

function toggleSectionField(secKey, fieldKey, enabled) {
  _secPrefsState.fields[`${secKey}.${fieldKey}`] = !!enabled;
}

function secPrefsBulk(allOn) {
  if (!_secPrefsSchema) return;
  _secPrefsSchema.forEach(sec => {
    if (sec.required) {
      _secPrefsState.sections[sec.key] = true;
    } else {
      _secPrefsState.sections[sec.key] = allOn;
    }
    (sec.fields || []).forEach(f => {
      _secPrefsState.fields[`${sec.key}.${f.key}`] = allOn;
    });
  });
  renderSectionPrefs();
}

function secPrefsReset() {
  if (!_secPrefsSchema) return;
  _secPrefsState = { sections: {}, fields: {} };
  renderSectionPrefs();
}

async function saveSectionPrefs() {
  try {
    const r = await fetch(`${API}/api/app-settings/section-preferences`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_secPrefsState),
    });
    if (!r.ok) throw new Error(await r.text());
    showToast('✓ Section preferences saved');
    closeSettingsModal();
  } catch (e) {
    showToast('⚠ ' + (e.message || 'Save failed'));
  }
}
