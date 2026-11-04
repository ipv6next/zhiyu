(() => {
  const $ = (selector) => document.querySelector(selector);
  const actor = window.ZhiyuDemo?.actor || '';
  const selectedKey = `zhiyu-service-criteria:${actor || 'guest'}`;
  const preferenceKey = `zhiyu-service-preference:${actor || 'guest'}`;
  const priorityMap = { 年龄: '年龄范围', 身高: '身高范围', 学历: '最低学历', 城市: '是否异地', 婚育情况: '婚育情况', 收入: '最低年收入', 有房: '是否有房', 是否异地: '是否异地' };
  let selected = [];

  const go = (path) => window.ZhiyuDemo ? window.ZhiyuDemo.go(path) : (location.href = path);
  function showTab(name) {
    document.querySelectorAll('.service-tabs button').forEach((button) => button.classList.toggle('active', button.dataset.tab === name));
    document.querySelectorAll('.service-panel').forEach((panel) => {
      const active = panel.id === `panel-${name}`;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function renderCriteria() {
    document.querySelectorAll('#criteria-grid button').forEach((button) => button.classList.toggle('selected', selected.includes(button.dataset.key)));
    $('#criteria-count').textContent = `${selected.length} / 4`;
  }
  function saveSearch() {
    localStorage.setItem(selectedKey, JSON.stringify(selected));
    localStorage.setItem(preferenceKey, $('#preference-text').value.trim());
  }
  async function saveSearchToAccount() {
    if (!actor) return;
    const priorities = [...new Set(selected.map((item) => priorityMap[item]).filter(Boolean))].slice(0, 4);
    const response = await fetch('/api/account', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'save_search_priorities', actor, priorities, note: $('#preference-text').value.trim() }) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || '暂时无法应用搜索条件');
  }

  try { selected = JSON.parse(localStorage.getItem(selectedKey) || '[]').filter((value) => typeof value === 'string').slice(0, 4); } catch (_) { selected = []; }
  $('#preference-text').value = localStorage.getItem(preferenceKey) || '';
  renderCriteria();

  document.querySelectorAll('[data-tab]').forEach((button) => button.addEventListener('click', () => showTab(button.dataset.tab)));
  document.querySelectorAll('[data-tab-target]').forEach((button) => button.addEventListener('click', () => showTab(button.dataset.tabTarget)));
  document.querySelectorAll('[data-go]').forEach((button) => button.addEventListener('click', () => go(button.dataset.go)));
  $('#criteria-grid').addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    const key = button.dataset.key;
    if (selected.includes(key)) selected = selected.filter((item) => item !== key);
    else if (selected.length < 4) selected.push(key);
    else { $('#criteria-count').animate?.([{ transform: 'translateX(-3px)' }, { transform: 'translateX(3px)' }, { transform: 'translateX(0)' }], { duration: 180 }); return; }
    saveSearch(); renderCriteria();
  });
  $('#preference-text').addEventListener('input', saveSearch);
  $('#apply-search').addEventListener('click', async () => {
    saveSearch();
    const button = $('#apply-search'); button.disabled = true; button.textContent = '正在应用条件…';
    try { await saveSearchToAccount(); go('matches.html'); }
    catch (error) { button.disabled = false; button.textContent = '应用条件，查看推荐'; alert(error.message || '暂时无法应用搜索条件'); }
  });
  document.querySelector('[data-more]').addEventListener('click', () => showTab('more'));
})();
