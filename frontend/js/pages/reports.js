async function renderReports(container) {
  container.innerHTML = `
    <h2>Reports & Email</h2>
    <div class="card" style="margin-bottom:16px">
      <h3>Export Report</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0">
        <div class="form-group"><label>Filename</label><input type="text" id="report-filename" value="killara_report"></div>
        <div class="form-group"><label>Format</label>
          <select id="report-format"><option value="PDF">PDF</option><option value="HTML">HTML</option></select>
        </div>
      </div>
      <div class="form-group"><label>Charts to Include</label>
        <div><label><input type="checkbox" class="report-chart" value="Summary Statistics" checked> Summary Statistics</label></div>
        <div><label><input type="checkbox" class="report-chart" value="Time Series" checked> Time Series</label></div>
        <div><label><input type="checkbox" class="report-chart" value="Distribution" checked> Distribution</label></div>
        <div><label><input type="checkbox" class="report-chart" value="Cohorts"> Cohorts</label></div>
      </div>
      <button class="btn btn-primary" id="generate-report"><i class="fa fa-file-pdf"></i> Generate Report</button>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h3>Send Email Now</h3>
      <div class="form-group"><label>Recipient Email</label><input type="email" id="email-to" placeholder="manager@farm.com"></div>
      <div class="form-group"><label>Subject</label><input type="text" id="email-subject" value="Automated Livestock Report"></div>
      <div class="form-group"><label>Message</label><textarea id="email-body" rows="3" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;font-family:var(--font)">Please find your livestock performance report attached.</textarea></div>
      <button class="btn btn-primary" id="send-now"><i class="fa fa-paper-plane"></i> Send Now</button>
    </div>
    <div class="card">
      <h3>Schedule Email</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="form-group"><label>Schedule Name</label><input type="text" id="sched-name" placeholder="Weekly Summary"></div>
        <div class="form-group"><label>Recipient</label><input type="email" id="sched-email"></div>
        <div class="form-group"><label>Frequency</label>
          <select id="sched-freq"><option value="daily">Daily</option><option value="weekly" selected>Weekly</option><option value="monthly">Monthly</option><option value="once">Once</option></select>
        </div>
        <div class="form-group"><label>Send Time</label><input type="time" id="sched-time" value="09:00"></div>
        <div class="form-group" id="sched-dow-group"><label>Day of Week</label>
          <select id="sched-dow"><option value="1">Monday</option><option value="2">Tuesday</option><option value="3">Wednesday</option><option value="4">Thursday</option><option value="5">Friday</option></select>
        </div>
      </div>
      <button class="btn btn-primary" id="create-schedule" style="margin-top:12px"><i class="fa fa-clock"></i> Create Schedule</button>
      <h4 style="margin-top:24px">Active Schedules</h4>
      <div id="schedules-list"></div>
    </div>`;

  document.getElementById('generate-report').onclick = generateReport;
  document.getElementById('send-now').onclick = sendNow;
  document.getElementById('create-schedule').onclick = createSchedule;
  document.getElementById('sched-freq').onchange = () => {
    document.getElementById('sched-dow-group').style.display =
      document.getElementById('sched-freq').value === 'weekly' ? 'block' : 'none';
  };
  loadSchedules();
}

async function generateReport() {
  const charts = [...document.querySelectorAll('.report-chart:checked')].map(c => c.value);
  const body = {
    farm_id: getFarmId(),
    filters: getFilters(),
    filename: document.getElementById('report-filename').value,
    format: document.getElementById('report-format').value,
    charts,
  };
  try {
    const ext = body.format === 'HTML' ? 'html' : 'pdf';
    await apiPostDownload('/reports/generate', body, `${body.filename}.${ext}`);
    showToast('Report generated', 'success');
  } catch (err) { showToast(err.message, 'error'); }
}

async function sendNow() {
  const recipient = (document.getElementById('email-to').value || '').trim();
  if (!recipient || !recipient.includes('@')) {
    showToast('Enter a valid recipient email', 'error');
    return;
  }
  const charts = [...document.querySelectorAll('.report-chart:checked')].map(c => c.value);
  const body = {
    farm_id: getFarmId(),
    recipient_email: recipient,
    email_subject: document.getElementById('email-subject').value,
    email_body: document.getElementById('email-body').value,
    report_filters: getFilters(),
    report_charts: charts.length ? charts : ['Summary Statistics', 'Distribution'],
    report_format: 'PDF',
  };
  const btn = document.getElementById('send-now');
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
  try {
    const res = await apiFetch('/email/send-now', { method: 'POST', body: JSON.stringify(body) });
    if (res.dry_run) {
      showToast(res.detail || 'Dry-run only — email was not sent', 'warning');
    } else {
      showToast(res.detail || 'Email sent', 'success');
    }
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa fa-paper-plane"></i> Send Now';
    }
  }
}

async function createSchedule() {
  const body = {
    farm_id: getFarmId(),
    schedule_name: document.getElementById('sched-name').value,
    recipient_email: document.getElementById('sched-email').value,
    frequency: document.getElementById('sched-freq').value,
    send_time: document.getElementById('sched-time').value,
    day_of_week: parseInt(document.getElementById('sched-dow').value),
    email_subject: 'Automated Livestock Report',
    report_filters: getFilters(),
    report_charts: ['Distribution', 'Summary Statistics'],
    report_format: 'PDF',
  };
  try {
    await apiFetch('/email/schedules', { method: 'POST', body: JSON.stringify(body) });
    showToast('Schedule created', 'success');
    loadSchedules();
  } catch (err) { showToast(err.message, 'error'); }
}

async function loadSchedules() {
  const list = document.getElementById('schedules-list');
  if (!list) return;
  try {
    const schedules = await apiFetch(`/email/schedules?farm_id=${getFarmId()}`);
    if (!schedules.length) {
      list.innerHTML = '<p style="font-size:13px;color:var(--text-secondary)">No scheduled emails</p>';
      return;
    }
    list.innerHTML = `<table class="data-table"><thead><tr><th>Name</th><th>Recipient</th><th>Frequency</th><th>Next Send</th><th>Status</th><th></th></tr></thead>
      <tbody>${schedules.map(s => `<tr>
        <td>${s.schedule_name || '—'}</td><td>${s.recipient_email}</td><td>${s.frequency}</td>
        <td>${s.next_send_at ? new Date(s.next_send_at).toLocaleString() : '—'}</td>
        <td><span class="badge ${s.is_active ? 'badge-active' : 'badge-inactive'}">${s.is_active ? 'Active' : 'Inactive'}</span></td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="toggleSchedule(${s.id},${!s.is_active})">${s.is_active ? 'Pause' : 'Activate'}</button>
          <button class="btn btn-sm btn-danger" onclick="deleteSchedule(${s.id})">Delete</button>
        </td></tr>`).join('')}</tbody></table>`;
  } catch (err) {
    list.innerHTML = `<p class="alert alert-warning">${err.message}</p>`;
  }
}

async function toggleSchedule(id, active) {
  await apiFetch(`/email/schedules/${id}`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) });
  loadSchedules();
}

async function deleteSchedule(id) {
  await apiFetch(`/email/schedules/${id}`, { method: 'DELETE' });
  showToast('Schedule deleted', 'success');
  loadSchedules();
}

window.renderReports = renderReports;
window.toggleSchedule = toggleSchedule;
window.deleteSchedule = deleteSchedule;
