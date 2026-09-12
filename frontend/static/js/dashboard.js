document.querySelector('#search').addEventListener('input', event => {
  const query = event.target.value.toLowerCase();
  let count = 0;
  document.querySelectorAll('[data-document]').forEach(row => { row.hidden = !row.dataset.document.includes(query); if (!row.hidden) count++; });
  document.querySelector('#search-status').textContent = `${count} matching records on this page`;
});
