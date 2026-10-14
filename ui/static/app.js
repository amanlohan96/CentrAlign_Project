let currentTaskId = null;
let currentApprovalRequestId = null;

// DOM Elements
const taskInput = document.getElementById('taskInput');
const guardrailLimit = document.getElementById('guardrailLimit');
const btnExecuteTask = document.getElementById('btnExecuteTask');
const btnReset = document.getElementById('btnReset');
const stepsContainer = document.getElementById('stepsContainer');
const currentTaskStatus = document.getElementById('currentTaskStatus');
const systemStatusPill = document.getElementById('systemStatusPill');
const memoryEntities = document.getElementById('memoryEntities');
const memoryScratchpad = document.getElementById('memoryScratchpad');
const erpTableBody = document.getElementById('erpTableBody');
const erpAuditLog = document.getElementById('erpAuditLog');
const verificationCertificate = document.getElementById('verificationCertificate');
const certSummary = document.getElementById('certSummary');
const certChecksList = document.getElementById('certChecksList');
const evidenceDossier = document.getElementById('evidenceDossier');
const evidenceSummaryText = document.getElementById('evidenceSummaryText');
const evidenceMeta = document.getElementById('evidenceMeta');

// Modal Elements
const approvalModal = document.getElementById('approvalModal');
const modalPolicyTag = document.getElementById('modalPolicyTag');
const modalReasonText = document.getElementById('modalReasonText');
const modalProposedAction = document.getElementById('modalProposedAction');
const modalContextJson = document.getElementById('modalContextJson');
const approvalNotes = document.getElementById('approvalNotes');
const btnApprove = document.getElementById('btnApprove');
const btnReject = document.getElementById('btnReject');

// Scenario Chips
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    taskInput.value = chip.dataset.task;
    if (chip.dataset.task.includes('18.5k') || chip.dataset.task.includes('CyberTech')) {
      guardrailLimit.value = 5000;
    }
  });
});

// Initial load
window.addEventListener('DOMContentLoaded', () => {
  refreshERPState();
});

// Refresh ERP Records & Audit Log
async function refreshERPState() {
  try {
    const resInvoices = await fetch('/api/erp/invoices');
    const invoices = await resInvoices.json();
    renderERPTable(invoices);

    const resAudit = await fetch('/api/erp/audit-log');
    const audits = await resAudit.json();
    renderERPAuditLog(audits);
  } catch (err) {
    console.error('Failed to refresh ERP state:', err);
  }
}

function renderERPTable(invoices) {
  if (!invoices || invoices.length === 0) {
    erpTableBody.innerHTML = '<tr><td colspan="6" class="loading-td">No invoices recorded yet.</td></tr>';
    return;
  }
  erpTableBody.innerHTML = invoices.map(inv => `
    <tr>
      <td><strong>${inv.id}</strong></td>
      <td>${inv.vendor}</td>
      <td><code>${inv.invoice_number}</code></td>
      <td>$${Number(inv.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
      <td>${inv.due_date}</td>
      <td><span class="badge-tag" style="color: ${inv.status === 'PAID' ? '#10b981' : '#38bdf8'}">${inv.status}</span></td>
    </tr>
  `).join('');
}

function renderERPAuditLog(audits) {
  if (!audits || audits.length === 0) {
    erpAuditLog.innerHTML = '<div class="audit-entry">No audit entries.</div>';
    return;
  }
  erpAuditLog.innerHTML = audits.map(a => `
    <div class="audit-entry">
      <span style="color: #64748b;">[${a.timestamp.slice(11, 19)}]</span>
      <strong style="color: #a78bfa;">${a.action}:</strong> ${a.details}
    </div>
  `).join('');
}

// Execute Task
btnExecuteTask.addEventListener('click', async () => {
  const goal = taskInput.value.trim();
  if (!goal) return;

  const threshold = parseFloat(guardrailLimit.value) || 5000;
  
  btnExecuteTask.disabled = true;
  systemStatusPill.textContent = 'Running';
  systemStatusPill.className = 'status-pill status-running';
  currentTaskStatus.textContent = 'EXECUTING';

  // Clear previous outputs
  verificationCertificate.classList.add('hidden');
  evidenceDossier.classList.add('hidden');
  stepsContainer.innerHTML = '<div class="empty-state">Starting task execution...</div>';

  try {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal: goal,
        auto_execute: true,
        guardrail_threshold: threshold
      })
    });
    const task = await res.json();
    currentTaskId = task.task_id;
    updateTaskUI(task);
    await refreshERPState();
  } catch (err) {
    alert('Task execution error: ' + err.message);
  } finally {
    btnExecuteTask.disabled = false;
  }
});

// Update UI from TaskRun object
function updateTaskUI(task) {
  currentTaskStatus.textContent = task.status;

  if (task.status === 'COMPLETED') {
    systemStatusPill.textContent = 'Success';
    systemStatusPill.className = 'status-pill status-ready';
  } else if (task.status === 'WAITING_FOR_APPROVAL') {
    systemStatusPill.textContent = 'Approval Required';
    systemStatusPill.className = 'status-pill';
    systemStatusPill.style.background = 'rgba(245, 158, 11, 0.2)';
    systemStatusPill.style.color = '#f59e0b';
    handleApprovalModalTrigger(task);
  } else if (task.status === 'FAILED') {
    systemStatusPill.textContent = 'Failed';
    systemStatusPill.className = 'status-pill';
    systemStatusPill.style.background = 'rgba(244, 63, 94, 0.2)';
    systemStatusPill.style.color = '#f43f5e';
  }

  // Render Plan Steps DAG
  renderSteps(task.steps);

  // Render Memory
  memoryEntities.textContent = JSON.stringify(task.memory.discovered_entities, null, 2);
  memoryScratchpad.innerHTML = task.memory.scratchpad.map(note => `
    <div class="scratchpad-item">${note}</div>
  `).join('');
  memoryScratchpad.scrollTop = memoryScratchpad.scrollHeight;

  // Render Verification & Evidence
  if (task.evidence && task.evidence.verification) {
    renderVerification(task.evidence.verification);
  }
  if (task.evidence) {
    renderEvidence(task.evidence);
  }
}

function renderSteps(steps) {
  if (!steps || steps.length === 0) {
    stepsContainer.innerHTML = '<div class="empty-state">No steps in plan.</div>';
    return;
  }

  stepsContainer.innerHTML = steps.map((step, idx) => {
    let outputPreview = '';
    if (step.result && step.result.output) {
      const outStr = typeof step.result.output === 'object' 
        ? JSON.stringify(step.result.output, null, 1) 
        : String(step.result.output);
      outputPreview = `<div class="step-output-box">&bull; Output: ${outStr.slice(0, 180)}</div>`;
    } else if (step.result && step.result.error) {
      outputPreview = `<div class="step-output-box" style="color: #f43f5e;">&bull; Error: ${step.result.error}</div>`;
    }

    return `
      <div class="step-card ${step.status}">
        <div class="step-header">
          <span class="step-title">${idx + 1}. ${step.title}</span>
          <span class="step-badge badge-${step.status}">${step.status}</span>
        </div>
        <p class="step-desc">${step.description}</p>
        <div class="step-tool">&gt; Tool: ${step.tool_name || 'internal_logic'}</div>
        ${outputPreview}
      </div>
    `;
  }).join('');
}

function renderVerification(verification) {
  verificationCertificate.classList.remove('hidden');
  certSummary.textContent = verification.summary;

  certChecksList.innerHTML = verification.checks.map(c => `
    <div class="check-item">
      <span class="check-name">${c.check_name} (${c.target_system})</span>
      <span class="${c.passed ? 'check-badge-pass' : 'check-badge-fail'}">
        ${c.passed ? '&check; PASSED' : '&cross; FAILED'}
      </span>
    </div>
  `).join('');
}

function renderEvidence(evidence) {
  evidenceDossier.classList.remove('hidden');
  evidenceSummaryText.textContent = evidence.summary;
  evidenceMeta.innerHTML = `
    Duration: ${evidence.duration_seconds}s | 
    Affected Records: ${evidence.system_records_affected.map(r => r.record_id).join(', ') || 'None'} |
    Audit Events Recorded: ${evidence.audit_trail_events.length}
  `;
}

// Handle HITL Approval Trigger
function handleApprovalModalTrigger(task) {
  const pendingReq = task.approval_requests.find(r => r.status === 'PENDING');
  if (!pendingReq) return;

  currentApprovalRequestId = pendingReq.id;
  modalPolicyTag.textContent = pendingReq.policy_triggered;
  modalReasonText.textContent = pendingReq.reason;
  modalProposedAction.textContent = pendingReq.proposed_action;
  modalContextJson.textContent = JSON.stringify(pendingReq.context, null, 2);
  approvalNotes.value = '';
  approvalModal.classList.remove('hidden');
}

// Modal Actions
btnApprove.addEventListener('click', async () => {
  if (!currentTaskId || !currentApprovalRequestId) return;
  await submitApproval(true);
});

btnReject.addEventListener('click', async () => {
  if (!currentTaskId || !currentApprovalRequestId) return;
  await submitApproval(false);
});

async function submitApproval(approved) {
  const notes = approvalNotes.value.trim() || (approved ? 'Authorized by operator' : 'Rejected by operator');
  approvalModal.classList.add('hidden');

  try {
    const res = await fetch(`/api/tasks/${currentTaskId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: currentApprovalRequestId,
        approved: approved,
        user_response: notes
      })
    });
    const updatedTask = await res.json();
    updateTaskUI(updatedTask);
    await refreshERPState();
  } catch (err) {
    alert('Failed to submit approval: ' + err.message);
  }
}

// Reset Sandbox
btnReset.addEventListener('click', async () => {
  if (!confirm('Reset simulated database and document vault to clean state?')) return;
  try {
    await fetch('/api/reset', { method: 'POST' });
    stepsContainer.innerHTML = '<div class="empty-state">Ready to plan and execute tasks autonomously. Click "Execute Autonomous Worker" above.</div>';
    memoryEntities.textContent = '{}';
    memoryScratchpad.innerHTML = '';
    verificationCertificate.classList.add('hidden');
    evidenceDossier.classList.add('hidden');
    currentTaskStatus.textContent = 'Idle';
    systemStatusPill.textContent = 'Ready';
    systemStatusPill.className = 'status-pill status-ready';
    await refreshERPState();
  } catch (err) {
    alert('Reset failed: ' + err.message);
  }
});
