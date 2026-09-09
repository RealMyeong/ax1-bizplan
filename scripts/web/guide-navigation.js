(() => {
  const panels = [...document.querySelectorAll('[role="tabpanel"]')];
  if (!panels.length || document.querySelector('.guide-toc')) return;
  const compact = window.matchMedia('(max-width: 1000px)');
  const toc = document.createElement('details');
  toc.className = 'guide-toc';
  toc.open = !compact.matches;
  const summary = document.createElement('summary');
  summary.textContent = '목차 · 바로 이동';
  toc.append(summary);
  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', '사용 안내 목차');
  toc.append(nav);
  const entries = [];
  panels.forEach((panel) => {
    const label = document.createElement('p');
    label.textContent = document.getElementById(panel.getAttribute('aria-labelledby'))?.textContent || panel.id;
    nav.append(label);
    const list = document.createElement('ul');
    nav.append(list);
    panel.querySelectorAll('h2, h3').forEach((heading, index) => {
      if (!heading.id) {
        const base = `toc-${panel.id}-${index + 1}`;
        let id = base;
        let suffix = 1;
        while (document.getElementById(id)) id = `${base}-${suffix++}`;
        heading.id = id;
      }
      const link = document.createElement('a');
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent.trim();
      link.className = heading.tagName === 'H2' ? 'toc-section' : 'toc-detail';
      const item = document.createElement('li');
      item.append(link);
      list.append(item);
      heading.tabIndex = -1;
      entries.push({ panel, heading, link });
      link.addEventListener('click', (event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (window.location.hash !== link.hash) history.pushState(null, '', link.hash);
        navigate(heading.id, true);
      });
    });
  });
  document.body.append(toc);
  document.body.classList.add('has-guide-toc');
  function activate(panel) {
    panels.forEach((item) => item.classList.toggle('is-active', item === panel));
    document.querySelectorAll('[role="tab"]').forEach((tab) => {
      tab.setAttribute('aria-selected', String(tab.dataset.target === panel.id));
    });
  }
  function mark(entry) {
    entries.forEach((item) => {
      if (item === entry) item.link.setAttribute('aria-current', 'location');
      else item.link.removeAttribute('aria-current');
    });
  }
  function navigate(id, focus) {
    const entry = entries.find((item) => item.heading.id === id);
    if (!entry) {
      const panel = panels.find((item) => item.id === id);
      if (panel) activate(panel);
      return;
    }
    activate(entry.panel);
    if (compact.matches) toc.open = false;
    // Instant scrolling avoids racing the existing tab handler's smooth scroll.
    entry.heading.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'instant' });
    if (focus) entry.heading.focus({ preventScroll: true });
    mark(entry);
  }
  function syncLocation() {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
    navigate(id, false);
  }
  let pending = false;
  function updateCurrent() {
    pending = false;
    const visible = entries.filter((entry) => entry.panel.classList.contains('is-active'));
    let current = visible[0];
    for (const entry of visible) {
      const top = entry.heading.getBoundingClientRect().top;
      if (top <= 110) {
        const sameRow = current && Math.abs(current.heading.getBoundingClientRect().top - top) < 2;
        if (!sameRow || !current.link.hasAttribute('aria-current')) current = entry;
      }
    }
    if (current) mark(current);
  }
  function scheduleCurrent() {
    if (!pending) { pending = true; requestAnimationFrame(updateCurrent); }
  }
  window.addEventListener('scroll', scheduleCurrent, { passive: true });
  window.addEventListener('resize', scheduleCurrent);
  window.addEventListener('hashchange', syncLocation);
  window.addEventListener('popstate', syncLocation);
  document.querySelectorAll('[role="tab"]').forEach((tab) => tab.addEventListener('click', scheduleCurrent));
  compact.addEventListener('change', () => { toc.open = !compact.matches; });
  syncLocation();
  scheduleCurrent();
})();
