/* LLM Pricing Tracker */
(function () {
  'use strict';

  var pricingData = null, historyData = null, allModels = [];
  var sortCol = 'updated', sortDir = 'desc';
  var searchQuery = '', activeTier = 'all';
  var activeProviders = new Set();
  var expandedModel = null;

  var COLORS = [
    '#2563eb','#7c3aed','#0891b2','#059669','#d97706',
    '#dc2626','#db2777','#4f46e5','#0284c7','#65a30d','#9333ea',
  ];

  var $ = function(id) { return document.getElementById(id); };

  function init() {
    loadData();
  }

  async function loadData() {
    try {
      var _a = await Promise.all([
        fetch('data/pricing.json'),
        fetch('data/history/summary.json').catch(function() { return null; }),
      ]), pResp = _a[0], hResp = _a[1];
      if (!pResp.ok) throw new Error('Failed to fetch');
      pricingData = await pResp.json();
      historyData = hResp ? await hResp.json() : null;
      render();
    } catch (err) {
      console.error(err);
      $('loading').classList.add('hidden');
      $('error-state').classList.remove('hidden');
    }
  }

  function bindEvents() {
    $('search-input').addEventListener('input', function () {
      searchQuery = this.value.trim().toLowerCase();
      $('search-clear').classList.toggle('hidden', !searchQuery);
      renderTable();
    });
    $('search-clear').addEventListener('click', function () {
      $('search-input').value = '';
      searchQuery = '';
      this.classList.add('hidden');
      $('search-input').focus();
      renderTable();
    });

    // Tier filter
    $('tier-filters').addEventListener('click', function (e) {
      var btn = e.target.closest('.tier-btn');
      if (!btn) return;
      this.querySelectorAll('.tier-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      activeTier = btn.dataset.tier;
      renderTable();
    });

    // Provider dropdown
    setupDropdown();

    // Sort
    $('pricing-table').addEventListener('click', function (e) {
      var th = e.target.closest('th[data-sort]');
      if (!th) return;
      var col = th.dataset.sort;
      if (sortCol === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortCol = col;
        sortDir = 'asc';
      }
      updateSortHeaders();
      renderTable();
    });

    // Click outside dropdown to close
    document.addEventListener('click', function (e) {
      var drop = $('provider-dropdown');
      if (drop && !drop.contains(e.target)) {
        $('dropdown-menu').classList.add('hidden');
        $('dropdown-toggle').classList.remove('open');
      }
    });
  }

  function setupDropdown() {
    var toggle = $('dropdown-toggle');
    var menu = $('dropdown-menu');
    var list = $('dropdown-list');
    var psearch = $('provider-search');

    toggle.addEventListener('click', function () {
      var isOpen = !menu.classList.contains('hidden');
      menu.classList.toggle('hidden', isOpen);
      toggle.classList.toggle('open', !isOpen);
      if (!isOpen) {
        psearch.value = '';
        psearch.focus();
        renderDropdownItems('');
      }
    });

    psearch.addEventListener('input', function () {
      renderDropdownItems(this.value.trim().toLowerCase());
    });

    $('select-all').addEventListener('click', function () {
      activeProviders = new Set(allModels.map(function (m) { return m._providerId; }));
      renderDropdownItems(psearch.value.trim().toLowerCase());
      updateDropdownLabel();
      renderTable();
    });

    $('deselect-all').addEventListener('click', function () {
      activeProviders = new Set();
      renderDropdownItems(psearch.value.trim().toLowerCase());
      updateDropdownLabel();
      renderTable();
    });

    list.addEventListener('change', function (e) {
      if (e.target.type === 'checkbox') {
        var pid = e.target.value;
        if (e.target.checked) { activeProviders.add(pid); }
        else { activeProviders.delete(pid); }
        updateDropdownLabel();
        renderTable();
      }
    });
  }

  function renderDropdownItems(filter) {
    var list = $('dropdown-list');
    var providers = pricingData.providers || [];
    var filtered = filter
      ? providers.filter(function (p) { return p.name.toLowerCase().indexOf(filter) !== -1; })
      : providers;

    if (filtered.length === 0) {
      list.innerHTML = '<div class="dropdown-no-results">没有匹配的厂商</div>';
      return;
    }

    list.innerHTML = filtered.map(function (p, i) {
      var pid = pricingData.providers.indexOf(p);
      return '<label class="dropdown-item">' +
        '<input type="checkbox" value="' + p.id + '"' + (activeProviders.has(p.id) ? ' checked' : '') + '>' +
        '<span class="dot" style="background:' + COLORS[pid % COLORS.length] + '"></span>' +
        escHtml(p.name) +
        '<span class="count">' + (p.models || []).length + '</span>' +
        '</label>';
    }).join('');
  }

  function updateDropdownLabel() {
    var providers = pricingData.providers || [];
    var total = providers.length;
    var sel = activeProviders.size;
    if (sel === 0) {
      $('dropdown-label').textContent = '未选择厂商';
    } else if (sel === total) {
      $('dropdown-label').textContent = '全部厂商 (' + total + ')';
    } else {
      $('dropdown-label').textContent = '已选 ' + sel + ' / ' + total;
    }
  }

  function render() {
    $('loading').classList.add('hidden');
    $('update-time').textContent = pricingData.last_updated
      ? new Date(pricingData.last_updated).toLocaleString('zh-CN', { hour12: false })
      : '--';
    $('rate-value').textContent = pricingData.usd_to_cny_rate || '--';

    allModels = flattenModels(pricingData);
    activeProviders = new Set(allModels.map(function (m) { return m._providerId; }));
    updateDropdownLabel();
    renderDropdownItems('');
    updateSortHeaders();
    renderTable();
    bindEvents();
  }

  function flattenModels(data) {
    var models = [];
    (data.providers || []).forEach(function (prov, pi) {
      (prov.models || []).forEach(function (m) {
        var tier = m.tier || detectTier(m);
        models.push(Object.assign({}, m, {
          _providerId: prov.id,
          _providerName: prov.name,
          _providerWebsite: prov.website,
          _pricingUrl: prov.pricing_page_url,
          _color: COLORS[pi % COLORS.length],
          _updated: (data.last_updated || '').slice(0, 10),
          _tier: tier,
        }));
      });
    });
    return models;
  }

  function detectTier(m) {
    var name = ((m.display_name || '') + ' ' + (m.name || '')).toLowerCase();
    if (/flash|lite|mini|nano|air|turbo|speed|haiku/.test(name)) return 'lite';
    if (/pro|max|opus|plus|preview|sonnet/.test(name)) return 'pro';
    return 'none';
  }

  function updateSortHeaders() {
    document.querySelectorAll('#pricing-table th[data-sort]').forEach(function (th) {
      th.classList.remove('sort-asc', 'sort-desc', 'sort-default');
      if (th.dataset.sort === sortCol) {
        th.classList.add('sort-' + sortDir);
      }
    });
  }

  function renderTable() {
    var filtered = allModels.filter(function (m) {
      if (!activeProviders.has(m._providerId)) return false;
      if (activeTier !== 'all' && m._tier !== activeTier) return false;
      if (!searchQuery) return true;
      return (m.display_name || m.name).toLowerCase().indexOf(searchQuery) !== -1
        || m._providerName.toLowerCase().indexOf(searchQuery) !== -1;
    });

    filtered.sort(function (a, b) {
      var va = getSortValue(a, sortCol), vb = getSortValue(b, sortCol);
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    $('stats-bar').textContent = '共 ' + filtered.length + ' 个模型';
    $('no-results').classList.toggle('hidden', filtered.length > 0);
    document.querySelector('.table-wrap').classList.toggle('hidden', filtered.length === 0);

    expandedModel = null;
    $('table-body').innerHTML = filtered.map(function (m) { return buildRow(m); }).join('');

    renderSparklines(filtered);
  }

  function getSortValue(m, col) {
    switch (col) {
      case 'provider': return m._providerName;
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
    var tierBadge = m._tier !== 'none' ? '<span class="badge-tier">' + (m._tier === 'pro' ? 'Pro' : 'Lite') + '</span>' : '';
    var notes = m.notes ? '<span class="model-notes">' + escHtml(m.notes) + '</span>' : '';
    var linkUrl = m._pricingUrl || m._providerWebsite || '#';
    var modelKey = escHtml(m._providerId + ':' + m.name);

    return '<tr id="row-' + modelKey + '">' +
      '<td><span class="badge"><span class="badge-dot" style="background:' + m._color + '"></span>' + escHtml(m._providerName) + '</span></td>' +
      '<td><span class="model-name">' + escHtml(m.display_name || m.name) + '</span>' + tierBadge + notes + '</td>' +
      '<td class="num"><span class="context">' + ctxHtml + '</span></td>' +
      '<td class="num">' + inputHtml + '</td>' +
      '<td class="num">' + cachedHtml + '</td>' +
      '<td class="num">' + outputHtml + '</td>' +
      '<td class="num">' + (m._updated || '--') + '</td>' +
      '<td class="sparkline-wrap" data-model="' + modelKey + '" title="点击展开趋势图"></td>' +
      '<td><a class="link-icon" href="' + escHtml(linkUrl) + '" target="_blank" rel="noopener" title="' + escHtml(m._providerName) + ' 官网定价">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>' +
      '</a></td></tr>';
  }

  function renderSparklines(models) {
    var hModels = (historyData && historyData.models) ? historyData.models : {};
    models.forEach(function (m) {
      var key = m._providerId + ':' + m.name;
      var cell = document.querySelector('.sparkline-wrap[data-model="' + CSS.escape(key) + '"]');
      if (!cell) return;
      var series = hModels[key];
      var hasData = series && series.series && series.series.length >= 1;
      if (!hasData) {
        // Use current model as a single data point
        series = { series: [{ d: (pricingData.last_updated || '').slice(0, 10), i: m.input_price, c: m.cached_input_price, o: m.output_price }] };
      }
      cell.innerHTML = '';
      cell.title = '点击展开趋势图';
      cell.style.cursor = 'pointer';
      if (series.series.length === 1) {
        // Single point: show a dot indicator
        var dot = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        dot.setAttribute('width', '16'); dot.setAttribute('height', '16');
        dot.setAttribute('viewBox', '0 0 16 16');
        var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', '8'); c.setAttribute('cy', '8'); c.setAttribute('r', '3.5');
        c.setAttribute('fill', '#2563eb');
        dot.appendChild(c);
        cell.appendChild(dot);
        var hint = document.createElement('span');
        hint.className = 'trend-expand-hint'; hint.textContent = '+';
        cell.appendChild(hint);
      } else {
        cell.appendChild(buildSparkline(series.series));
      }
      cell.addEventListener('click', function () { toggleChart(m, key, series.series); });
    });
  }

  function buildSparkline(series) {
    var data = series.map(function (p) { return p.o; });
    var min = Math.min.apply(null, data), max = Math.max.apply(null, data);
    if (min === max) { max = min + 0.01; min = min - 0.01; }

    var w = 72, h = 26, pad = 2;
    var n = data.length;
    var points = data.map(function (v, i) {
      return (pad + (i / Math.max(n - 1, 1)) * (w - 2 * pad)) + ',' +
        (h - pad - ((v - min) / (max - min)) * (h - 2 * pad));
    }).join(' ');

    var color = data[n - 1] > data[0] ? '#dc2626' : '#059669';

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', String(w));
    svg.setAttribute('height', String(h));
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.style.overflow = 'visible';

    var polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.setAttribute('points', points);
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', color);
    polyline.setAttribute('stroke-width', '1.5');
    polyline.setAttribute('stroke-linecap', 'round');
    polyline.setAttribute('stroke-linejoin', 'round');

    var lastPt = points.split(' ').pop().split(',');
    var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', lastPt[0]);
    dot.setAttribute('cy', lastPt[1]);
    dot.setAttribute('r', '2');
    dot.setAttribute('fill', color);

    svg.appendChild(polyline);
    svg.appendChild(dot);
    return svg;
  }

  function toggleChart(m, key, series) {
    // Remove any existing chart row
    var existing = document.querySelector('.chart-row');
    if (existing) {
      var wasSame = expandedModel === key;
      existing.remove();
      if (wasSame) { expandedModel = null; return; }
    }

    expandedModel = key;
    var row = document.getElementById('row-' + CSS.escape(key));
    if (!row) return;

    var chartRow = document.createElement('tr');
    chartRow.className = 'chart-row';
    chartRow.innerHTML = '<td colspan="9"><div class="chart-panel"><div class="chart-area"><div class="chart-legend" id="chart-legend-' + CSS.escape(key) + '"></div><canvas id="chart-canvas-' + CSS.escape(key) + '" height="280"></canvas></div><div class="chart-info" id="chart-info-' + CSS.escape(key) + '"></div></div></td>';

    row.insertAdjacentElement('afterend', chartRow);

    // Build chart
    requestAnimationFrame(function () { drawChart(key, series); });
  }

  function drawChart(key, series) {
    var canvas = document.getElementById('chart-canvas-' + CSS.escape(key));
    if (!canvas) return;
    var rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = 260 * (window.devicePixelRatio || 1);
    canvas.style.width = rect.width + 'px';
    canvas.style.height = '260px';

    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    ctx.scale(dpr, dpr);

    var W = rect.width, H = 260;
    var pad = { top: 20, right: 30, bottom: 50, left: 55 };
    var pw = W - pad.left - pad.right;
    var ph = H - pad.top - pad.bottom;

    var dates = series.map(function (p) { return p.d; });
    var iData = series.map(function (p) { return p.i; });
    var cData = series.map(function (p) { return p.c; });
    var oData = series.map(function (p) { return p.o; });

    var allVals = iData.concat(oData).filter(function (v) { return v != null; });
    if (cData.some(function (v) { return v != null; })) {
      allVals = allVals.concat(cData.filter(function (v) { return v != null; }));
    }
    if (allVals.length === 0) { allVals = [0, 1]; }
    var yMin = Math.min.apply(null, allVals) * 0.9;
    var yMax = Math.max.apply(null, allVals) * 1.1;
    if (yMin === yMax) { yMax = yMin + 1; yMin = yMin - 1; }

    function x(i) { return pad.left + (i / Math.max(series.length - 1, 1)) * pw; }
    function y(v) { return pad.top + ph - ((v - yMin) / (Math.max(yMax - yMin, 0.01))) * ph; }

    // Grid lines
    ctx.strokeStyle = '#f0f0f0';
    ctx.lineWidth = 1;
    var gridLines = 5;
    for (var g = 0; g <= gridLines; g++) {
      var gy = pad.top + (g / gridLines) * ph;
      ctx.beginPath();
      ctx.moveTo(pad.left, gy);
      ctx.lineTo(W - pad.right, gy);
      ctx.stroke();
      // Y label
      var label = (yMax - (g / gridLines) * (yMax - yMin)).toFixed(2);
      ctx.fillStyle = '#9ca3af';
      ctx.font = '11px ' + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = 'right';
      ctx.fillText(label, pad.left - 6, gy + 4);
    }

    // X labels
    var xStep = Math.max(1, Math.floor(series.length / 6));
    for (var xi = 0; xi < series.length; xi += xStep) {
      var xx = x(xi);
      var dateLabel = dates[xi].slice(5);
      ctx.fillStyle = '#9ca3af';
      ctx.font = '10px ' + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = 'center';
      ctx.fillText(dateLabel, xx, H - pad.bottom + 16);
    }

    // Draw lines
    var colors = { input: '#2563eb', cached: '#7c3aed', output: '#dc2626' };
    var names = { input: '输入', cached: '缓存输入', output: '输出' };

    var legendHtml = '';
    [['output', oData, colors.output], ['input', iData, colors.input], ['cached', cData, colors.cached]].forEach(function (d) {
      var lbl = d[0], data = d[1], color = d[2];
      var hasData = data.some(function (v) { return v != null; });
      if (!hasData) return;

      legendHtml += '<span><span class="legend-dot" style="background:' + color + '"></span>' + names[lbl] + '</span>';

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      var first = true;
      for (var i = 0; i < data.length; i++) {
        if (data[i] == null) continue;
        var px = x(i), py = y(data[i]);
        if (first) { ctx.moveTo(px, py); first = false; }
        else { ctx.lineTo(px, py); }
      }
      ctx.stroke();

      // Dots
      for (var di = 0; di < data.length; di++) {
        if (data[di] == null) continue;
        var dx = x(di), dy = y(data[di]);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(dx, dy, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    var legendEl = document.getElementById('chart-legend-' + CSS.escape(key));
    if (legendEl) legendEl.innerHTML = legendHtml;

    // Info table
    var last = series[series.length - 1];
    var first = series[0];
    var infoEl = document.getElementById('chart-info-' + CSS.escape(key));
    if (infoEl) {
      var rows = '<tr><th>输入</th><td>' + (last.i != null ? '¥' + last.i.toFixed(2) : '--') + '</td></tr>' +
        (last.c != null ? '<tr><th>缓存输入</th><td>¥' + last.c.toFixed(2) + '</td></tr>' : '') +
        '<tr><th>输出</th><td>' + (last.o != null ? '¥' + last.o.toFixed(2) : '--') + '</td></tr>';
      if (series.length >= 2) {
        rows += '<tr><th>首次记录</th><td>' + first.d + '</td></tr>';
      }
      rows += '<tr><th>数据点</th><td>' + series.length + (series.length < 2 ? '（需更多天积累）' : '') + '</td></tr>';
      infoEl.innerHTML = '<table>' + rows + '</table>';
    }
  }

  // Formatting
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

  function escHtml(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  if (!CSS.escape) {
    CSS.escape = function (v) { return v.replace(/([^\w-])/g, '\\$1'); };
  }

  init();
})();
