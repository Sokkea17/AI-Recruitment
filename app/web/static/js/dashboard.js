// Toast System
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'danger' || type === 'error') icon = '❌';
  if (type === 'warning') icon = '⚠️';

  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// JD File Upload & Parsing Handler
function initJDUpload(dropzoneId, fileInputId, formId) {
  const dropzone = document.getElementById(dropzoneId);
  const fileInput = document.getElementById(fileInputId);
  if (!dropzone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length) {
      fileInput.files = files;
      handleJDFileSelected(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (fileInput.files.length) {
      handleJDFileSelected(fileInput.files[0]);
    }
  });
}

async function handleJDFileSelected(file) {
  const previewBox = document.getElementById('extraction-preview');
  const loadingIndicator = document.getElementById('upload-loading');
  
  if (loadingIndicator) loadingIndicator.style.display = 'block';
  if (previewBox) previewBox.style.display = 'none';

  const formData = new FormData();
  formData.append('jd_file', file);

  try {
    const resp = await fetch('/vacancies/upload-jd', {
      method: 'POST',
      body: formData
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || 'Failed to extract JD information.');
    }

    // Populate extracted fields into form
    if (data.extracted) {
      const ext = data.extracted;
      setVal('title', ext.title);
      setVal('department', ext.department);
      setVal('location', ext.location);
      setVal('employment_type', ext.employment_type);
      setVal('salary_range', ext.salary_range);
      setVal('short_description', ext.short_description);
      setVal('responsibilities', ext.responsibilities);
      setVal('requirements', ext.requirements);
      setVal('education', ext.education);
      setVal('experience', ext.experience);
      setVal('skills', ext.skills);
      setVal('instructions', ext.instructions);
      setVal('full_description', ext.full_description);

      // Multi-position indicator
      const multiBox = document.getElementById('multi-position-alert');
      if (multiBox) {
        if (ext.positions_detected && ext.positions_detected.length > 1) {
          multiBox.style.display = 'block';
          const posList = ext.positions_detected.map(p => `<b>${p.title}</b>`).join(', ');
          multiBox.innerHTML = `⚠️ <b>Multiple Positions Detected:</b> ${posList}. You can review and create this vacancy, or split them.`;
        } else {
          multiBox.style.display = 'none';
        }
      }
    }

    if (previewBox) previewBox.style.display = 'block';
    showToast('JD extracted successfully! Please review before publishing.', 'success');
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (loadingIndicator) loadingIndicator.style.display = 'none';
  }
}

function setVal(id, value) {
  const el = document.getElementById(id);
  if (el && value !== null && value !== undefined) {
    el.value = value;
  }
}

// Quick Status Update
async function updateApplicationStatus(appId, newStatus) {
  try {
    const resp = await fetch(`/applications/${appId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Failed to update status');
    showToast(`Status updated to ${newStatus}`, 'success');
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Mobile sidebar toggle
  const toggleBtn = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }
});
