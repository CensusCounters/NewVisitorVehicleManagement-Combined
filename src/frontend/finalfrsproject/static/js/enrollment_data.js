(() => {
  'use strict';
  const root = document.getElementById('enrollment-data');
  if (!root) return;
  const base = root.dataset.base;
  const $ = id => document.getElementById(id);
  const pending = new Set();
  const rows = new Map();
  const names = {export: 'Export enrollments', validate: 'Package review', import: 'Import enrollments', reset: 'Reset enrollments'};
  const states = {queued: 'Queued', running: 'In progress', completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled', recovery_required: 'Recovery needed'};
  let connected = false;
  let serviceReady = false;
  let activeJobs = [];
  let validationJobId = null;
  let inputId = null;
  let preview = null;
  let resetPreview = null;
  let fileGeneration = 0;
  let polling = false;

  function node(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }
  function count(value) { return Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0; }
  function counts(value = {}) { return `${count(value.persons)} persons · ${count(value.vehicles)} vehicles`; }
  function message(value, tone = 'info') {
    if ($('maintenance-message').textContent !== value) $('maintenance-message').textContent = value;
    $('maintenance-message').dataset.tone = tone;
  }
  function syncControls() {
    const unavailable = !connected || !serviceReady || activeJobs.length > 0 || pending.size > 0;
    ['export-data', 'validate-data', 'preview-reset'].forEach(id => { $(id).disabled = unavailable; });
    $('validate-data').disabled = unavailable || !$('dataset-file').files.length;
    $('dataset-file').disabled = unavailable;
    $('import-data').disabled = unavailable || !inputId || !preview;
    $('reset-data').disabled = unavailable || !resetPreview;
    rows.forEach(({element}) => element.querySelectorAll('button').forEach(button => {
      button.disabled = !connected || pending.size > 0 || (button.dataset.action === 'resume' && !serviceReady);
    }));
  }
  function ensureAvailable() {
    if (!connected) throw new Error('Maintenance status is unavailable. Wait for the connection before starting an operation.');
    if (!serviceReady) throw new Error('The background service is unavailable. Select Check again and follow the guidance below.');
    if (activeJobs.length) throw new Error('Another operation is queued, running or awaiting recovery. Review recent operations first.');
  }
  async function api(path, body, form = false) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), body === undefined ? 15000 : 120000);
    const options = {credentials: 'same-origin', signal: controller.signal, headers: {}};
    if (body !== undefined) {
      options.method = 'POST';
      options.headers['X-CSRFToken'] = $('enrollment-csrf').value;
      if (form) options.body = body;
      else { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
    }
    try {
      const response = await fetch(base + path, options);
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error('Request could not be confirmed. Check your login and recent operations before trying again.'); }
      if (!response.ok) {
        const error = new Error(data.error || data.msg || 'Operation could not be submitted.');
        error.code = data.code;
        throw error;
      }
      return data;
    } finally { clearTimeout(timer); }
  }
  async function action(button, callback) {
    if (pending.size) return;
    pending.add(button);
    syncControls();
    try { await callback(); }
    catch (error) { message(error.name === 'AbortError' ? 'The request timed out. Check recent operations before trying again.' : error.message, 'error'); }
    finally { pending.delete(button); syncControls(); }
  }
  function metrics(report) {
    const group = node('div', 'ed-metrics');
    [['New records', counts(report.imported)], ['Repair missing data', counts(report.repaired)], ['Identical records', counts(report.skipped)], ['Conflicts to skip', String((report.conflicts || []).length)]].forEach(([label, value]) => {
      const item = node('div', 'ed-metric'); item.append(node('strong', '', value), node('span', '', label)); group.append(item);
    });
    return group;
  }
  async function confirmAction({title, text, button, danger = false, report = null, phrase = null}) {
    if (!window.Swal) throw new Error('The confirmation dialog could not load. Reload this page before continuing.');
    const content = node('div');
    content.append(node('p', '', text));
    if (report) content.append(metrics(report));
    const options = {
      title, html: content, icon: danger ? 'warning' : 'info', showCancelButton: true,
      confirmButtonText: button, cancelButtonText: 'Cancel', reverseButtons: true,
      focusCancel: true, allowEnterKey: false, allowOutsideClick: false, width: 600,
      didOpen: () => Swal.getCancelButton().focus(),
      customClass: {popup: 'enrollment-confirm' + (danger ? ' enrollment-confirm--danger' : '')}
    };
    if (phrase) {
      options.input = 'text'; options.inputLabel = `Type ${phrase} to confirm`;
      options.inputPlaceholder = phrase;
      options.inputAttributes = {autocomplete: 'off', spellcheck: 'false', 'aria-label': `Type ${phrase} to confirm`};
      options.didOpen = () => {
        const input = Swal.getInput();
        const update = () => { Swal.getConfirmButton().disabled = input.value !== phrase; };
        input.addEventListener('input', update); update(); Swal.getCancelButton().focus();
      };
      options.preConfirm = value => {
        if (value !== phrase) { Swal.showValidationMessage(`Type ${phrase} exactly to continue.`); return false; }
        return value;
      };
    }
    return (await Swal.fire(options)).isConfirmed;
  }
  async function submit(path, body, label) {
    await api(path, body);
    message(`${label} requested. Follow its progress in recent operations.`);
    resetPreview = null;
    await refresh();
  }

  $('export-data').onclick = function () {
    action(this, async () => {
      if (!await confirmAction({title: 'Create an enrollment export?', text: 'This creates a downloadable package of persons, vehicles, images and face data. Registration pauses while it is prepared. Store the downloaded file securely.', button: 'Create export'})) return;
      ensureAvailable(); await submit('/export', {}, 'Export');
    });
  };
  $('dataset-file').onchange = () => {
    fileGeneration += 1; validationJobId = null; inputId = null; preview = null;
    $('package-summary').textContent = 'Review this package to see additions, identical records and conflicts.';
    syncControls();
  };
  $('validate-data').onclick = function () {
    action(this, async () => {
      const file = $('dataset-file').files[0];
      if (!file) throw new Error('Choose a dataset ZIP file.');
      const generation = fileGeneration;
      if (!await confirmAction({title: 'Check this enrollment package?', text: `Review ${file.name} for additions, duplicates and conflicts. Registration pauses while the package is checked. No enrollments are imported by this step.`, button: 'Check package'})) return;
      ensureAvailable();
      inputId = null; preview = null; validationJobId = null;
      const body = new FormData(); body.append('dataset', file);
      const data = await api('/import/validate', body, true);
      if (generation !== fileGeneration) return;
      validationJobId = data.job_id;
      $('package-summary').textContent = 'Package review is in progress. Results will appear here when it finishes.';
      message('Package review requested. No records have been imported.');
      resetPreview = null;
      await refresh();
    });
  };
  $('import-data').onclick = function () {
    action(this, async () => {
      if (!inputId || !preview) throw new Error('Review a package first.');
      if (!await confirmAction({title: 'Import the reviewed records?', text: 'New records will be added and missing images or face data repaired. Different existing content is preserved and reported as a conflict. Identical records are skipped. Registration pauses during import.', button: 'Import and repair', report: preview})) return;
      ensureAvailable();
      await submit('/import', {input_id: inputId, validation_job_id: validationJobId}, 'Import');
      inputId = null; validationJobId = null; preview = null;
      $('package-summary').textContent = 'Import submitted. Review the final counts and any conflicts in recent operations.';
    });
  };
  $('preview-reset').onclick = function () {
    action(this, async () => {
      ensureAvailable(); resetPreview = null;
      const data = await api('/reset/preview', {});
      resetPreview = data;
      $('reset-summary').textContent = `${counts(data.counts)} would be removed. ${data.message}`;
      message('Reset preview ready. No records have been deleted.');
    });
  };
  $('reset-data').onclick = function () {
    action(this, async () => {
      if (!resetPreview) throw new Error('Preview the affected records first.');
      if (!await confirmAction({title: 'Reset enrolled data?', text: `${counts(resetPreview.counts)} were found in the preview. This removes enrolled persons, vehicles, their face vectors and private images. A recovery export is created first. This is not required for import.`, button: 'Reset enrollments', danger: true, phrase: 'RESET ENROLLMENTS'})) return;
      ensureAvailable(); await submit('/reset', {confirmation: 'RESET ENROLLMENTS'}, 'Reset');
      $('reset-summary').textContent = 'Reset submitted. Follow the operation below; its recovery export will be available after completion.';
    });
  };

  function makeJob(job) {
    const item = node('article', 'ed-job'); item.dataset.jobId = job.id;
    const result = job.result || {};
    const header = node('div', 'ed-job-header');
    const badge = node('span', 'ed-badge', states[job.status] || job.status);
    if (job.operation === 'import' && job.status === 'completed' && (result.conflicts || []).length) badge.textContent = 'Completed with conflicts';
    badge.dataset.status = job.status;
    header.append(node('h4', '', names[job.operation] || job.operation), badge); item.append(header);
    item.append(node('p', '', job.step === 'Complete' ? 'Operation finished.' : String(job.step || 'Waiting to start').replaceAll('_', ' ')));
    const date = new Date(job.created_at);
    if (!Number.isNaN(date.getTime())) item.append(node('p', 'ed-muted', date.toLocaleString()));
    if (result.imported) {
      item.append(node('p', '', `${job.operation === 'validate' ? 'Ready to add' : 'Added'}: ${counts(result.imported)}. Identical records skipped: ${counts(result.skipped)}.`));
      if (result.repaired) item.append(node('p', '', `${job.operation === 'validate' ? 'Ready to repair' : 'Repaired'}: ${counts(result.repaired)}.`));
      if ((result.conflicts || []).length) {
        const details = node('details', 'ed-conflicts'); details.dataset.reportId = job.id;
        details.append(node('summary', '', `Review ${result.conflicts.length} conflicts`));
        result.conflicts.forEach(conflict => details.append(node('p', '', `${conflict.entity === 'persons' ? 'Person' : 'Vehicle'} ${conflict.identity} — ${conflict.reason}`)));
        item.append(details);
      }
    }
    if (job.error_summary) item.append(node('p', 'ed-error', job.error_summary));
    const actions = node('div', 'ed-actions');
    if (job.status === 'completed' && result.download) {
      const link = node('a', 'ed-button ed-button-secondary', result.recovery_export ? 'Download recovery export' : 'Download dataset');
      link.href = base + '/download/' + encodeURIComponent(job.id); actions.append(link);
    }
    if (job.status === 'queued' && job.checkpoint === 'pending') {
      const cancel = node('button', 'ed-button ed-button-secondary', 'Cancel queued operation'); cancel.type = 'button';
      cancel.onclick = () => action(cancel, () => submit('/jobs/' + encodeURIComponent(job.id) + '/cancel', {}, 'Cancellation'));
      actions.append(cancel);
    }
    if (job.status === 'recovery_required') {
      const resume = node('button', 'ed-button ed-button-secondary', 'Review recovery'); resume.type = 'button';
      resume.dataset.action = 'resume';
      resume.onclick = () => action(resume, async () => {
        if (!await confirmAction({title: `Resume ${names[job.operation] || 'this operation'}?`, text: 'Continue the interrupted operation from its saved progress. This can change enrollment data and will pause registration again. Review the error above before continuing.', button: 'Resume operation', danger: job.operation === 'reset', phrase: job.operation === 'reset' ? 'RESET ENROLLMENTS' : null})) return;
        if (!connected) throw new Error('Wait for maintenance status to reconnect.');
        await submit('/jobs/' + encodeURIComponent(job.id) + '/resume', {}, 'Recovery');
      });
      actions.append(resume);
    }
    if (actions.childElementCount) item.append(actions);
    const identifier = node('details', 'ed-job-id');
    identifier.append(node('summary', '', 'Operation reference'), node('code', '', job.id)); item.append(identifier);
    return item;
  }
  function renderJobs(jobs) {
    const container = $('maintenance-jobs');
    const ids = new Set(jobs.map(job => job.id));
    rows.forEach((row, id) => { if (!ids.has(id)) { row.element.remove(); rows.delete(id); } });
    container.querySelectorAll('.ed-empty').forEach(element => element.remove());
    if (!jobs.length) { container.append(node('p', 'ed-empty', 'No maintenance operations yet.')); return; }
    let previous = null;
    jobs.forEach(job => {
      const signature = JSON.stringify([job.status, job.step, job.result, job.error_summary, job.created_at]);
      let row = rows.get(job.id);
      if (!row || row.signature !== signature) {
        const open = row ? Array.from(row.element.querySelectorAll('details[open]')).map(el => el.className) : [];
        const element = makeJob(job);
        element.querySelectorAll('details').forEach(el => { el.open = open.includes(el.className); });
        if (row) row.element.replaceWith(element);
        row = {element, signature}; rows.set(job.id, row);
      }
      const expected = previous ? previous.nextElementSibling : container.firstElementChild;
      if (row.element !== expected) container.insertBefore(row.element, expected);
      previous = row.element;
    });
  }
  async function refresh() {
    if (polling) return;
    polling = true;
    try {
      const data = await api('/jobs');
      const wasConnected = connected;
      const wasReady = serviceReady;
      connected = true;
      serviceReady = data.availability ? data.availability.ready === true : true;
      activeJobs = data.jobs.filter(job => ['queued', 'running', 'recovery_required'].includes(job.status));
      const validation = data.jobs.find(job => job.id === validationJobId);
      if (validation && validation.status === 'completed') {
        inputId = validation.result.input_id; preview = validation.result;
        const panel = $('package-summary'); panel.replaceChildren(metrics(preview));
        panel.append(node('p', '', 'Conflicts are skipped; unrelated records continue. Review their details in the operation below.'));
      } else if (validation && ['failed', 'cancelled'].includes(validation.status)) {
        inputId = null; preview = null;
        $('package-summary').textContent = validation.error_summary || 'Package review was cancelled. Review the package again to continue.';
      }
      renderJobs(data.jobs);
      if (!serviceReady) message(data.availability.message, 'error');
      else if (!wasConnected || !wasReady) message(activeJobs.length ? 'An operation is active or awaiting recovery. Review its progress below.' : 'Ready. Review an action before starting maintenance.');
    } catch (error) {
      connected = false;
      serviceReady = false;
      message(error.code === 'enrollment_setup_required' ? error.message :
        'Maintenance status is unavailable. Actions are disabled until the connection returns. Check your login or reload this page.', 'error');
      if (!rows.size) $('maintenance-jobs').replaceChildren(node('p', 'ed-empty', 'Operations cannot be loaded until maintenance status is available.'));
    } finally { polling = false; syncControls(); }
  }
  syncControls();
  $('maintenance-retry').onclick = refresh;
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 3000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
