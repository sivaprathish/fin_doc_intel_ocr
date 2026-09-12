const form = document.querySelector('#upload-form');
const input = document.querySelector('#file');
const info = document.querySelector('#file-info');
const zone = document.querySelector('#drop-zone');
function validate() {
  const file = input.files[0];
  input.setCustomValidity('');
  if (!file) return;
  if (!/\.(pdf|jpe?g|png)$/i.test(file.name)) input.setCustomValidity('Choose a PDF, JPG, JPEG or PNG file.');
  if (!file.size || file.size > 10 * 1024 * 1024) input.setCustomValidity('Choose a non-empty file under 10 MB.');
  info.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
}
input.addEventListener('change', validate);
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragging'); });
zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragging'); if (e.dataTransfer.files.length === 1) { input.files = e.dataTransfer.files; validate(); } });
form.addEventListener('submit', e => {
  validate();
  if (!form.reportValidity()) { e.preventDefault(); return; }
  document.querySelector('#submit-button').disabled = true;
  document.querySelector('#submit-button').textContent = 'Processing…';
  document.querySelector('#upload-status').textContent = 'Uploading and processing. This can take several minutes. Please keep this page open.';
});
window.addEventListener('pageshow', () => { document.querySelector('#submit-button').disabled = false; document.querySelector('#submit-button').textContent = 'Extract and validate'; });
