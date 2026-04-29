/* LLM Pricing Tracker — app entry point */
(function () {
  'use strict';

  // State
  let pricingData = null;
  let historyData = null;
  let allModels = [];
  let sortCol = 'name';
  let sortDir = 'asc';
  let searchQuery = '';
  let activeProviders = new Set();

  // DOM refs
  const $body = document.getElementById('table-body');
  const $search = document.getElementById('search-input');
  const $clear = document.getElementById('search-clear');
  const $filters = document.getElementById('filter-chips');
  const $reset = document.getElementById('filter-reset');
  const $stats = document.getElementById('stats-bar');
  const $updateTime = document.getElementById('update-time');
  const $rate = document.getElementById('rate-value');
  const $loading = document.getElementById('loading');
  const $noResults = document.getElementById('no-results');
  const $error = document.getElementById('error-state');

  // Provider color palette
  const COLORS = [
    '#2563eb','#7c3aed','#0891b2','#059669','#d97706',
    '#dc2626','#db2777','#4f46e5','#0284c7','#65a30d','#9333ea',
  ];

  function init() {
    loadData();
    bindEvents();
  }

  async function loadData() {
    try {
      const [pResp, hResp] = await Promise.all([
        fetch('data/pricing.json'),
        fetch('data/history/summary.json').catch(() => null),
      ]);
      if (!pResp.ok) throw new Error('Failed to fetch pricing');
      pricingData = await pResp.json();
      historyData = hResp ? await hResp.json() : null;
      render();
    } catch (err) {
      console.error(err);
      $loading.classList.add('hidden');
      $error.classList.remove('hidden');
    }
  }

  function bindEvents() {
    $search.addEventListener('input', function () {
      searchQuery = this.value.trim().toLowerCase();
      $clear.classList.toggle('hidden', !searchQuery);
      renderTable();
    });
    $clear.addEventListener('click', function () {
      $search.value = '';
      searchQuery = '';
      $clear.classList.add('hidden');
      $search.focus();
      renderTable();
    });
    $reset.addEventListener('click', function () {
      activeProviders = new Set(allModels.map(m => m._providerId));
      $filters.querySelectorAll('.chip').forEach(c => c.classList.add('active'));
      $reset.classList.add('hidden');
      renderTable();
    });

    // Sort on header click
    document.getElementById('pricing-table').addEventListener('click', function (e) {
      const th = e.target.closest('th[data-sort]');
      if (!th) return;
      const col = th.dataset.sort;
      if (sortCol === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortCol = col;
        sortDir = 'asc';
      }
      updateSortHeaders();
      renderTable();
    });
  }

  function render() {
    $loading.classList.add('hidden');

    // Update header meta
    $updateTime.textContent = pricingData.last_updated
      ? new Date(pricingData.last_updated).toLocaleString('zh-CN')
      : '--';
    $rate.textContent = pricingData.usd_to_cny_rate || '--';

    // Flatten models
    allModels = flattenModels(pricingData);
    activeProviders = new Set(allModels.map(m => m._providerId));

    // Build filter chips
    buildFilters();

    // Render table
    updateSortHeaders();
    renderTable();
  }

  function flattenModels(data) {
    const models = [];
    (data.providers || []).forEach(function (prov, pi) {
      (prov.models || []).forEach(function (m) {
        models.push(Object.assign({}, m, {
          _providerId: prov.id,
          _providerName: prov.name,
          _providerWebsite: prov.website,
          _pricingUrl: prov.pricing_page_url,
          _color: COLORS[pi % COLORS.length],
          _updated: (data.last_updated || '').slice(0, 10),
        }));
      });
    });
    return models;
  }

  function buildFilters() {
    $filters.innerHTML = '';
    var providers = pricingData.providers || [];
    providers.forEach(function (prov, i) {
      var chip = document.createElement('button');
      chip.className = 'chip active';
      chip.style.setProperty('--c', COLORS[i % COLORS.length]);
      chip.innerHTML = '<span class="badge-dot" style="background:' + COLORS[i % COLORS.length] + '"></span>' + prov.name + ' <span class="count">' + (prov.models || []).length + '</span>';
      chip.addEventListener('click', function () {
        chip.classList.toggle('active');
        if (chip.classList.contains('active')) {
          activeProviders.add(prov.id);
        } else {
          activeProviders.delete(prov.id);
        }
        $reset.classList.toggle('hidden', activeProviders.size === allModels.length);
        renderTable();
      });
      $filters.appendChild(chip);
    });
  }

  function updateSortHeaders() {
    document.querySelectorAll('#pricing-table th[data-sort]').forEach(function (th) {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.dataset.sort === sortCol) {
        th.classList.add('sort-' + sortDir);
      }
    });
  }

  function renderTable() {
    // Filter
    var filtered = allModels.filter(function (m) {
      if (!activeProviders.has(m._providerId)) return false;
      if (!searchQuery) return true;
      return (m.display_name || m.name).toLowerCase().indexOf(searchQuery) !== -1
        || m._providerName.toLowerCase().indexOf(searchQuery) !== -1;
    });

    // Sort
    filtered.sort(function (a, b) {
      var va = getSortValue(a, sortCol);
      var vb = getSortValue(b, sortCol);
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    // Stats
    $stats.textContent = '共 ' + filtered.length + ' 个模型';

    // Toggle empty state
    $noResults.classList.toggle('hidden', filtered.length > 0 || !!pricingData);
    document.querySelector('.table-wrap').classList.toggle('hidden', filtered.length === 0);

    // Render rows
    $body.innerHTML = filtered.map(function (m) {
      return buildRow(m);
    }).join('');

    if (historyData) {
      renderSparklines(filtered);
    }
  }

  function getSortValue(m, col) {
    switch (col) {
      case 'provider': return m._providerName.toLowerCase();
      case 'name': return (m.display_name || m.name).toLowerCase();
      case 'context': return m.context_window || 0;
      case 'input': return m.input_price || 0;
      case 'cached': return m.cached_input_price != null ? m.cached_input_price : -1;
      case 'output': return m.output_price || 0;
      case 'updated': return m._updated || '';
      default: return '';
    }
  }

  function buildRow(m) {
    var inputHtml = formatPrice(m.input_price);
    var cachedHtml = m.cached_input_price != null ? formatPrice(m.cached_input_price) : '<span class="price-na">--</span>';
    var outputHtml = formatPrice(m.output_price);
    var ctxHtml = m.context_window ? formatContext(m.context_window) : '<span class="price-na">--</span>';
    var notes = m.notes ? '<span class="model-notes">' + escHtml(m.notes) + '</span>' : '';

    return '<tr>' +
      '<td><span class="badge"><span class="badge-dot" style="background:' + m._color + '"></span>' + escHtml(m._providerName) + '</span></td>' +
      '<td><span class="model-name">' + escHtml(m.display_name || m.name) + '</span>' + notes + '</td>' +
      '<td class="num"><span class="context">' + ctxHtml + '</span></td>' +
      '<td class="num">' + inputHtml + '</td>' +
      '<td class="num">' + cachedHtml + '</td>' +
      '<td class="num">' + outputHtml + '</td>' +
      '<td class="num">' + (m._updated || '--') + '</td>' +
      '<td class="sparkline-wrap" data-model="' + escHtml(m._providerId + ':' + m.name) + '"></td>' +
      '<td><a class="link-icon" href="' + escHtml(m._pricingUrl || m._providerWebsite) + '" target="_blank" rel="noopener" title="查看官网定价">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>' +
      '</a></td>' +
      '</tr>';
  }

  function renderSparklines(models) {
    var hModels = (historyData && historyData.models) ? historyData.models : {};
    models.forEach(function (m) {
      var key = m._providerId + ':' + m.name;
      var cell = document.querySelector('.sparkline-wrap[data-model="' + CSS.escape(key) + '"]');
      if (!cell) return;
      var series = hModels[key];
      if (!series || !series.series || series.series.length < 2) {
        cell.innerHTML = '<span class="trend-no-data">--</span>';
        return;
      }
      cell.innerHTML = '';
      cell.appendChild(buildSparkline(series.series, 80, 28));
    });
  }

  function buildSparkline(series, width, height) {
    var data = series.map(function (p) { return p.o; }); // output price
    var min = Math.min.apply(null, data);
    var max = Math.max.apply(null, data);
    if (min === max) { max = min + 0.01; min = min - 0.01; } // flat line

    var pad = 2;
    var len = data.length;
    var points = data.map(function (v, i) {
      var x = pad + (i / Math.max(len - 1, 1)) * (width - 2 * pad);
      var y = height - pad - ((v - min) / (max - min)) * (height - 2 * pad);
      return x + ',' + y;
    }).join(' ');

    var color = data[data.length - 1] > data[0] ? '#dc2626' : '#059669';

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.style.overflow = 'visible';

    var polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.setAttribute('points', points);
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', color);
    polyline.setAttribute('stroke-width', '1.5');
    polyline.setAttribute('stroke-linecap', 'round');
    polyline.setAttribute('stroke-linejoin', 'round');

    // Dot at last point
    var lastPt = points.split(' ').pop().split(',');
    var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', lastPt[0]);
    dot.setAttribute('cy', lastPt[1]);
    dot.setAttribute('r', '2');
    dot.setAttribute('fill', color);

    // Title for tooltip
    var title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = series.map(function (p) { return p.d + ': ¥' + p.o.toFixed(2); }).join('\n');
    svg.appendChild(title);

    svg.appendChild(polyline);
    svg.appendChild(dot);
    return svg;
  }

  // Utilities
  function formatPrice(p) {
    if (p == null) return '<span class="price-na">--</span>';
    var cls = p === 0 ? ' price-zero' : '';
    return '<span class="' + cls + '">' + p.toFixed(2) + '</span>';
  }

  function formatContext(t) {
    if (t >= 1000000) return (t / 1000000).toFixed(1) + 'M';
    if (t >= 1000) return (t / 1000).toFixed(0) + 'K';
    return String(t);
  }

  function escHtml(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // CSS.escape polyfill
  if (!CSS.escape) {
    CSS.escape = function (v) { return v.replace(/([^\w-])/g, '\\$1'); };
  }

  // Start
  init();
})();
