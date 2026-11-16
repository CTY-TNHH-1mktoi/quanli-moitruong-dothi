'use strict';

(() => {
  const sidebar = document.querySelector('#dashboardSidebar');
  const toggle = document.querySelector('#sidebarToggle');
  const backdrop = document.querySelector('#sidebarBackdrop');
  const links = [...document.querySelectorAll('[data-section-link]')];
  const label = document.querySelector('#currentSectionLabel');
  const refresh = document.querySelector('#refreshDashboard');
  const main = document.querySelector('#mainContent');
  const mobile = matchMedia('(max-width: 991px)');
  const views = new Map(links.map((link) => [link.hash.slice(1), link]));
  const sections = [...main.querySelectorAll(':scope > section')];
  const overviewSections = new Set(['overview', 'air', 'environmentMap']);
  const viewContext = document.querySelector('#dashboardViewContext');

  function setMenu(open, returnFocus = false) {
    document.body.classList.toggle('sidebar-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Đóng menu điều hướng' : 'Mở menu điều hướng');
    backdrop.hidden = !open || !mobile.matches;
    sidebar.inert = !open;
    sidebar.setAttribute('aria-hidden', String(!open));
    if (open) sidebar.querySelector('a')?.focus();
    else if (returnFocus) toggle.focus();
    // Resizing the content also changes the canvas chart and Leaflet map width.
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }

  toggle.addEventListener('click', () => setMenu(!document.body.classList.contains('sidebar-open')));
  backdrop.addEventListener('click', () => setMenu(false, true));
  document.querySelector('#sidebarClose').addEventListener('click', () => setMenu(false, true));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
      setMenu(false, true);
    }
  });
  mobile.addEventListener('change', () => setMenu(false));
  setMenu(false);

  function activate(link) {
    links.forEach((item) => {
      const active = item === link;
      item.classList.toggle('active', active);
      if (active) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
    label.textContent = link.querySelector('span').textContent;
  }

  function syncViewLocation() {
    document.querySelector('#dashboardViewLocation').textContent = window.EnvironmentLocation?.current.Ten || 'Địa điểm đang chọn';
  }

  function showView(identifier, {push = false, focus = false} = {}) {
    const view = views.has(identifier) ? identifier : 'overview';
    for (const section of sections) {
      section.hidden = view === 'overview' ? !overviewSections.has(section.id) : section.id !== view;
    }
    document.body.dataset.dashboardView = view;
    viewContext.hidden = view === 'overview';
    syncViewLocation();
    activate(views.get(view));
    document.title = `${label.textContent} · Giám sát môi trường đô thị`;
    if (push && location.hash !== `#${view}`) window.history.pushState(null, '', `#${view}`);
    closeSearch();
    setNotifications(false);
    window.scrollTo({top: 0, left: 0, behavior: 'instant'});
    if (focus) main.focus({preventScroll: true});
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'));
      document.dispatchEvent(new CustomEvent('dashboardviewchange', {detail: {view}}));
    });
  }

  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    showView(link.hash.slice(1), {push: true, focus: true});
    if (mobile.matches) setMenu(false);
  }));
  sidebar.querySelector('[data-open-chat]')?.addEventListener('click', () => {
    if (mobile.matches) setMenu(false);
  });
  document.querySelector('#chatLauncher')?.addEventListener('click', () => {
    if (mobile.matches) setMenu(false);
  });
  sidebar.querySelector('.sidebar-brand')?.addEventListener('click', (event) => {
    event.preventDefault();
    showView('overview', {push: true, focus: true});
    if (mobile.matches) setMenu(false);
  });
  document.querySelector('#backToOverview').addEventListener('click', (event) => {
    event.preventDefault();
    showView('overview', {push: true, focus: true});
  });

  refresh.addEventListener('click', () => window.loadAll?.());
  const syncLoading = () => { refresh.disabled = main.getAttribute('aria-busy') === 'true'; };
  new MutationObserver(syncLoading).observe(main, { attributes: true, attributeFilter: ['aria-busy'] });
  syncLoading();

  const search = document.querySelector('#locationSearch');
  const searchBox = document.querySelector('.header-search');
  const results = document.querySelector('#headerSearchResults');
  const notificationCenter = document.querySelector('.notification-center');
  const bell = document.querySelector('#notificationToggle');
  const notifications = document.querySelector('#alerts');
  const notificationCount = document.querySelector('#notificationCount');
  const warningHistory = document.querySelector('#warningHistory');
  const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
  let matches = [];
  let activeResult = -1;

  function closeSearch() {
    results.hidden = true;
    search.setAttribute('aria-expanded', 'false');
    search.removeAttribute('aria-activedescendant');
    activeResult = -1;
  }

  function setNotifications(open, returnFocus = false) {
    notifications.hidden = !open;
    bell.setAttribute('aria-expanded', String(open));
    if (open) {
      closeSearch();
      if (mobile.matches) setMenu(false);
    } else if (returnFocus) bell.focus();
  }

  function syncAlerts() {
    const count = Number(warningHistory.dataset.alertCount || 0);
    const status = warningHistory.dataset.alertStatus;
    notificationCount.textContent = count > 99 ? '99+' : String(count);
    notificationCount.hidden = status !== 'ready' || count === 0;
    bell.setAttribute('aria-label', status === 'ready' && count
      ? `Lịch sử cảnh báo, ${count} cảnh báo gần nhất` : 'Lịch sử cảnh báo');
    warningHistory.setAttribute('aria-busy', String(status === 'loading'));
    document.querySelector('#notificationLocation').textContent = window.EnvironmentLocation?.current.Ten || 'Địa điểm đang chọn';
  }

  bell.addEventListener('click', () => setNotifications(notifications.hidden));
  document.querySelector('#notificationClose').addEventListener('click', () => setNotifications(false, true));
  document.addEventListener('alertschanged', syncAlerts);
  document.addEventListener('locationchange', () => {
    syncAlerts();
    syncViewLocation();
    closeSearch();
  });
  window.addEventListener('hashchange', () => {
    if (location.hash === '#alerts') setNotifications(true);
    else if (views.has(location.hash.slice(1)) || !location.hash) showView(location.hash.slice(1), {focus: true});
  });
  syncAlerts();

  function highlightResult(index) {
    activeResult = index;
    results.querySelectorAll('[role="option"][data-search-index]').forEach((button, offset) => {
      button.setAttribute('aria-selected', String(offset === index));
    });
    const button = results.querySelector(`[data-search-index="${index}"]`);
    if (button) {
      search.setAttribute('aria-activedescendant', button.id);
      button.scrollIntoView({block: 'nearest'});
    } else search.removeAttribute('aria-activedescendant');
  }

  function chooseResult(index) {
    const result = matches[index];
    if (!result) return;
    if (result.notifications) {
      search.value = '';
      setNotifications(true);
      bell.focus();
      return;
    } else if (result.place) {
      if (!window.EnvironmentLocation.select(result.place.MaDiaDiem)) return;
    } else result.link.click();
    search.value = '';
    closeSearch();
    search.focus();
  }

  function renderSearch() {
    const term = normalize(search.value.trim());
    results.replaceChildren();
    matches = [];
    activeResult = -1;
    search.removeAttribute('aria-activedescendant');
    if (!term) { closeSearch(); return; }
    setNotifications(false);
    const functions = links.filter((link) => normalize(link.textContent).includes(term))
      .map((link) => ({link, name: link.textContent.trim(), group: 'Chức năng'}));
    if (normalize('Lịch sử cảnh báo thông báo').includes(term)) {
      functions.push({notifications: true, name: 'Lịch sử cảnh báo', group: 'Chức năng'});
    }
    const places = (window.EnvironmentLocation?.places || [])
      .filter((place) => normalize(`${place.Ten} ${place.Nhom || ''}`).includes(term))
      .map((place) => ({place, name: place.Ten, group: 'Địa điểm'}));
    matches = [...functions, ...places].slice(0, 8);
    let previousGroup = null;
    matches.forEach((result, index) => {
      if (result.group !== previousGroup) {
        const heading = document.createElement('div');
        heading.className = 'search-result-group';
        heading.setAttribute('role', 'presentation');
        heading.textContent = result.group;
        results.append(heading);
        previousGroup = result.group;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.id = `headerSearchResult-${index}`;
      button.className = 'header-search-result';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', 'false');
      button.tabIndex = -1;
      button.dataset.searchIndex = String(index);
      button.textContent = result.name;
      button.addEventListener('pointerdown', (event) => event.preventDefault());
      button.addEventListener('click', () => chooseResult(index));
      results.append(button);
    });
    if (!matches.length) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.setAttribute('role', 'option');
      empty.setAttribute('aria-disabled', 'true');
      empty.textContent = 'Không tìm thấy kết quả. Hãy thử tên khác.';
      results.append(empty);
    }
    results.hidden = false;
    search.setAttribute('aria-expanded', 'true');
  }

  search.addEventListener('input', renderSearch);
  search.addEventListener('focus', renderSearch);
  search.addEventListener('keydown', (event) => {
    if (event.isComposing) return;
    if (event.key === 'Escape') { closeSearch(); return; }
    if (event.key === 'Enter' && !results.hidden) {
      event.preventDefault();
      chooseResult(activeResult < 0 ? 0 : activeResult);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (results.hidden) renderSearch();
      if (matches.length) {
        const index = activeResult < 0 ? (event.key === 'ArrowDown' ? 0 : matches.length - 1)
          : (activeResult + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length;
        highlightResult(index);
      }
    }
  });
  search.addEventListener('blur', closeSearch);
  document.addEventListener('pointerdown', (event) => {
    if (!notificationCenter.contains(event.target)) setNotifications(false);
    if (!searchBox.contains(event.target)) closeSearch();
  });
  notificationCenter.addEventListener('focusout', (event) => {
    if (event.relatedTarget && !notificationCenter.contains(event.relatedTarget)) setNotifications(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !notifications.hidden) setNotifications(false, true);
  });
  window.EnvironmentLocation.ready.then(() => {
    syncAlerts();
    syncViewLocation();
    if (document.activeElement === search) renderSearch();
  });
  showView(location.hash.slice(1));
  if (location.hash === '#alerts') setNotifications(true);
})();
