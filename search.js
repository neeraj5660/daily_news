// Simple client-side search for Morning Desk
// Fetches search_index.json and does a case-insensitive substring search over title/snippet
(async function(){
  const idxUrl = '/search_index.json';
  let index = [];
  try { const r = await fetch(idxUrl); if (r.ok) index = await r.json(); } catch(e){ console.warn('Search index not available', e); }

  function renderResults(items, container){
    if (!items.length) { container.innerHTML = '<div style="color:var(--text-faint)">No results</div>'; return; }
    container.innerHTML = items.map(it => `
      <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
        <div style="font-weight:600;color:var(--paper)">${escapeHtml(it.title || '(no title)')}</div>
        <div style="font-size:13px;color:var(--text-dim)">${escapeHtml(it.snippet || '')}</div>
        <div style="font-size:12px;color:var(--text-faint);margin-top:6px">${escapeHtml(it.source || '')} · ${escapeHtml(it.date || '')} · <a href='${escapeHtml(it.path || '')}' style='color:var(--amber)'>view</a></div>
      </div>`).join('');
  }

  function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  const input = document.getElementById('site-search');
  const btn = document.getElementById('search-btn');
  const results = document.getElementById('search-results');
  if (!input || !btn || !results) return;

  function search(q){
    const ql = q.trim().toLowerCase();
    if (!ql) { results.style.display='none'; return; }
    const matches = index.filter(it => ((it.title||'')+" "+(it.snippet||'')).toLowerCase().includes(ql));
    results.style.display = 'block';
    renderResults(matches.slice(0,25), results);
  }

  btn.addEventListener('click', ()=> search(input.value));
  input.addEventListener('keydown', (e)=> { if (e.key === 'Enter') search(input.value); });
})();
