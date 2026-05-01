/* LLM Pricing Tracker */
(function () {
  'use strict';

  var pricingData = null, historyData = null, allModels = [];
  var sortCol = 'provider', sortDir = 'asc';
  var searchQuery = '', activeTier = 'all';
  var activeProviders = new Set();
  var expandedModel = null;

  var COLORS = [
    '#2563eb','#7c3aed','#0891b2','#059669','#d97706',
    '#dc2626','#db2777','#4f46e5','#0284c7','#65a30d','#9333ea',
  ];
  var SPARKLINE_MAX_POINTS = 60;

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
          _providerOrder: pi,
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
      if (sortCol === 'provider') {
        var providerCmp = a._providerName.localeCompare(b._providerName, 'en', { sensitivity: 'base' });
        if (providerCmp !== 0) return sortDir === 'asc' ? providerCmp : -providerCmp;
        var aName = (a.display_name || a.name).toLowerCase();
        var bName = (b.display_name || b.name).toLowerCase();
        if (aName < bName) return sortDir === 'asc' ? 1 : -1;
        if (aName > bName) return sortDir === 'asc' ? -1 : 1;
        return 0;
      }
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
    var tierBadge = m._tier !== 'none' ? '<span class="badge-tier">' + (m._tier === 'pro' ? 'Pro' : 'Lite') + '</span>' : '';
    var notes = m.notes ? '<span class="model-notes">' + escHtml(m.notes) + '</span>' : '';
    var linkUrl = m._pricingUrl || m._providerWebsite || '#';
    var modelKey = escHtml(m._providerId + ':' + m.name);

    return '<tr id="' + domSafeId('row', m._providerId + ':' + m.name) + '">' +
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
      var mergedSeries = getMergedSeries(m, hModels[key]);
      var comparableSeries = getComparableSeries(mergedSeries);
      var sparklineSeries = getSparklineSeries(comparableSeries);
      cell.innerHTML = '';
      cell.title = '点击展开价格趋势图';
      cell.style.cursor = 'pointer';
      cell.classList.add('clickable');

      if (sparklineSeries.length === 1) {
        // Single point: show expand hint
        var hint = document.createElement('span');
        hint.className = 'trend-hint'; hint.textContent = '展开';
        cell.appendChild(hint);
      } else {
        cell.appendChild(buildSparkline(sparklineSeries));
        // Expand arrow
        var arrow = document.createElement('span');
        arrow.className = 'trend-arrow';
        arrow.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>';
        cell.appendChild(arrow);
      }
      cell.addEventListener('click', function () { toggleChart(m, key, comparableSeries); });
    });
  }

  function domSafeId(prefix, key) {
    return prefix + '-' + String(key).replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  function getMergedSeries(m, historyEntry) {
    var currentDate = (pricingData.last_updated || '').slice(0, 10);
    var currentPoint = {
      d: currentDate,
      i: m.input_price,
      c: m.cached_input_price,
      o: m.output_price,
      ri: m.raw_input_price,
      rc: m.raw_cached_input_price,
      ro: m.raw_output_price,
      cur: m.raw_price_currency || m.price_currency || 'CNY',
    };
    var series = normalizeSeries(historyEntry && historyEntry.series ? historyEntry.series : []);
    if (!currentDate) return series.length ? series : [currentPoint];
    if (!series.length) return [currentPoint];

    var last = series[series.length - 1];
    if (last && last.d === currentDate) {
      series[series.length - 1] = currentPoint;
      return series;
    }
    series.push(currentPoint);
    return series;
  }

  function normalizeSeries(series) {
    if (!series || !series.length) return [];
    var byDate = new Map();
    series.forEach(function (point) {
      if (!point || !point.d) return;
      byDate.set(point.d, point);
    });
    return Array.from(byDate.entries())
      .sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; })
      .map(function (entry) { return entry[1]; });
  }

  function normalizeComparablePoint(point) {
    if (!point) return point;
    var rate = pricingData && pricingData.usd_to_cny_rate ? Number(pricingData.usd_to_cny_rate) : null;
    if (point.cur !== 'USD' || !rate) return point;
    return {
      d: point.d,
      i: point.ri != null ? roundTo2(point.ri * rate) : point.i,
      c: point.rc != null ? roundTo2(point.rc * rate) : point.c,
      o: point.ro != null ? roundTo2(point.ro * rate) : point.o,
      ri: point.ri,
      rc: point.rc,
      ro: point.ro,
      cur: point.cur,
    };
  }

  function getComparableSeries(series) {
    return (series || []).map(normalizeComparablePoint);
  }

  function getSparklineSeries(series) {
    if (!series || series.length <= SPARKLINE_MAX_POINTS) return series || [];
    return series.slice(series.length - SPARKLINE_MAX_POINTS);
  }

  function roundTo2(value) {
    return Math.round(Number(value) * 100) / 100;
  }

  function buildSparkline(series) {
    var data = series.map(function (p) { return p.o; });
    var min = Math.min.apply(null, data), max = Math.max.apply(null, data);
    if (min === max) { max = min + 0.01; min = min - 0.01; }

    var w = 90, h = 32, pad = 3;
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
    var existing = document.querySelector('.chart-row');
    if (existing) {
      var wasSame = expandedModel === key;
      var prevRow = document.querySelector('.row-expanded');
      if (prevRow) prevRow.classList.remove('row-expanded');
      existing.remove();
      if (wasSame) { expandedModel = null; return; }
    }

    expandedModel = key;
    var row = document.getElementById(domSafeId('row', key));
    if (!row) return;
    row.classList.add('row-expanded');

    var chartId = domSafeId('chart', key);
    var infoId = domSafeId('chart-info', key);
    var chartRow = document.createElement('tr');
    chartRow.className = 'chart-row';
    chartRow.innerHTML = '<td colspan="9"><div class="chart-panel"><div class="chart-area"><div id="' + chartId + '" style="width:100%;height:300px"></div></div><div class="chart-info" id="' + infoId + '"></div></div></td>';

    row.insertAdjacentElement('afterend', chartRow);

    requestAnimationFrame(function () { drawChart(chartId, key, m, series); });
  }

  function drawChart(chartId, key, m, series) {
    var dom = document.getElementById(chartId);
    if (!dom) return;
    if (window.echarts) {
      renderECharts(dom, window.echarts, series);
    } else {
      dom.innerHTML = buildTrendChartMarkup(series);
    }

    // Info table
    var last = series[series.length - 1];
    var first = series[0];
    var infoEl = document.getElementById(domSafeId('chart-info', key));
    if (infoEl) {
      var rows = '<tr><th>输入</th><td>' + (last.i != null ? '¥' + last.i.toFixed(2) : '--') + '</td></tr>' +
        (last.c != null ? '<tr><th>缓存输入</th><td>¥' + last.c.toFixed(2) + '</td></tr>' : '') +
        '<tr><th>输出</th><td>' + (last.o != null ? '¥' + last.o.toFixed(2) : '--') + '</td></tr>';
      if (series.length >= 2) {
        rows += '<tr><th>首次记录</th><td>' + first.d + '</td></tr>';
      }
      rows += '<tr><th>数据点</th><td>' + series.length + (series.length < 2 ? '（积累中）' : '') + '</td></tr>';
      infoEl.innerHTML = '<table>' + rows + '</table>';
    }
  }

  function renderECharts(dom, echarts, series) {
    var chart = echarts.init(dom);
    var dates = series.map(function (p) { return p.d; });
    var iData = series.map(function (p) { return p.i; });
    var cData = series.map(function (p) { return p.c; });
    var oData = series.map(function (p) { return p.o; });
    var hasCache = cData.some(function (v) { return v != null; });

    var seriesArr = [
      {
        name: '输出', type: 'line',
        data: oData, smooth: series.length >= 4,
        lineStyle: { color: '#dc2626', width: 2 },
        itemStyle: { color: '#dc2626' },
        symbol: 'circle', symbolSize: series.length <= 3 ? 8 : 4,
      },
      {
        name: '输入', type: 'line',
        data: iData, smooth: series.length >= 4,
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
        symbol: 'circle', symbolSize: series.length <= 3 ? 8 : 4,
      },
    ];
    if (hasCache) {
      seriesArr.push({
        name: '缓存输入', type: 'line',
        data: cData, smooth: series.length >= 4,
        lineStyle: { color: '#7c3aed', width: 2, type: 'dashed' },
        itemStyle: { color: '#7c3aed' },
        symbol: 'diamond', symbolSize: series.length <= 3 ? 8 : 4,
      });
    }

    chart.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        valueFormatter: function (value) { return value != null ? '¥' + value.toFixed(4) : '--'; },
        backgroundColor: '#fff',
        borderColor: '#e5e7eb',
        textStyle: { color: '#1a1a2e', fontSize: 12, fontFamily: document.body.style.fontFamily || 'sans-serif' },
      },
      legend: {
        data: hasCache ? ['输出', '输入', '缓存输入'] : ['输出', '输入'],
        bottom: 0, textStyle: { fontSize: 12 },
      },
      grid: { left: 55, right: 20, top: 20, bottom: 35 },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLabel: { fontSize: 11, formatter: function (v) { return v.slice(5); } },
        axisTick: { alignWithLabel: true },
      },
      yAxis: {
        type: 'value',
        axisLabel: { fontSize: 11, formatter: function (v) { return '¥' + v; } },
        splitLine: { lineStyle: { color: '#f3f4f6' } },
      },
      series: seriesArr,
    });

    var resizeHandler = function () { chart.resize(); };
    window.addEventListener('resize', resizeHandler);
    var observer = new MutationObserver(function () {
      if (!document.getElementById(dom.id)) {
        window.removeEventListener('resize', resizeHandler);
        chart.dispose();
        observer.disconnect();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function buildTrendChartMarkup(series) {
    var specs = [
      { key: 'o', label: '输出', color: '#dc2626', dashed: false },
      { key: 'i', label: '输入', color: '#2563eb', dashed: false },
      { key: 'c', label: '缓存输入', color: '#7c3aed', dashed: true },
    ].filter(function (spec) {
      return series.some(function (point) { return point[spec.key] != null; });
    });

    var width = 760, height = 300;
    var pad = { top: 18, right: 14, bottom: 40, left: 58 };
    var chartW = width - pad.left - pad.right;
    var chartH = height - pad.top - pad.bottom;
    var values = [];
    series.forEach(function (point) {
      specs.forEach(function (spec) {
        if (point[spec.key] != null) values.push(point[spec.key]);
      });
    });
    var max = values.length ? Math.max.apply(null, values) : 1;
    max = max <= 0 ? 1 : max * 1.08;
    var ticks = 5;

    function xAt(idx) {
      return pad.left + (idx / Math.max(series.length - 1, 1)) * chartW;
    }
    function yAt(value) {
      return pad.top + chartH - (value / max) * chartH;
    }
    function fmtAxis(value) {
      if (value >= 100) return '¥' + Math.round(value);
      if (value >= 10) return '¥' + value.toFixed(0);
      return '¥' + value.toFixed(1).replace(/\\.0$/, '');
    }

    var parts = [];
    for (var i = 0; i <= ticks; i++) {
      var v = max * (i / ticks);
      var y = yAt(v);
      parts.push('<line x1="' + pad.left + '" y1="' + y + '" x2="' + (width - pad.right) + '" y2="' + y + '" stroke="#f3f4f6" stroke-width="1"/>');
      parts.push('<text x="' + (pad.left - 8) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" fill="#6b7280">' + fmtAxis(v) + '</text>');
    }

    parts.push('<line x1="' + pad.left + '" y1="' + (pad.top + chartH) + '" x2="' + (width - pad.right) + '" y2="' + (pad.top + chartH) + '" stroke="#94a3b8" stroke-width="1.2"/>');

    series.forEach(function (point, idx) {
      parts.push('<text x="' + xAt(idx) + '" y="' + (height - 8) + '" text-anchor="middle" font-size="11" fill="#6b7280">' + escHtml(point.d.slice(5)) + '</text>');
    });

    specs.forEach(function (spec) {
      var path = [];
      series.forEach(function (point, idx) {
        var value = point[spec.key];
        if (value == null) return;
        path.push((path.length ? 'L' : 'M') + xAt(idx) + ' ' + yAt(value));
      });
      if (path.length) {
        parts.push('<path d="' + path.join(' ') + '" fill="none" stroke="' + spec.color + '" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"' + (spec.dashed ? ' stroke-dasharray="6 4"' : '') + '/>');
      }
      series.forEach(function (point, idx) {
        var value = point[spec.key];
        if (value == null) return;
        parts.push('<circle cx="' + xAt(idx) + '" cy="' + yAt(value) + '" r="4" fill="' + spec.color + '"/>');
      });
    });

    var legend = specs.map(function (spec) {
      return '<span class="chart-legend-item" style="color:' + spec.color + '"><span class="chart-legend-line' + (spec.dashed ? ' dashed' : '') + '"></span><span>' + spec.label + '</span></span>';
    }).join('');

    return '<div class="simple-chart"><svg viewBox="0 0 ' + width + ' ' + height + '" aria-label="价格趋势图">' + parts.join('') + '</svg><div class="chart-legend">' + legend + '</div></div>';
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
