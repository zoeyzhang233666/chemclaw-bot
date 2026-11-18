<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__CHAIN_TITLE__</title>
<style>/*__CHAIN_CSS__*/</style>
</head>
<body>
<div id="app">

  <!-- ================= 顶部信息区 ================= -->
  <header class="topbar">
    <div class="brand">
      <div class="logo">链</div>
      <div class="brandtxt">
        <h1 id="docTitle">__CHAIN_TITLE__</h1>
        <div class="sub" id="docSub"></div>
      </div>
    </div>
    <div class="stamp" id="stamp"></div>
  </header>

  <!-- ================= 覆盖完整度 ================= -->
  <section class="coverage" id="coverageBar">
    <div class="cov-gauge">
      <svg viewBox="0 0 120 120" class="gauge" aria-label="资料覆盖完整度">
        <circle cx="60" cy="60" r="50" class="gauge-bg"></circle>
        <circle cx="60" cy="60" r="50" class="gauge-fg" id="gaugeFg"></circle>
        <text x="60" y="58" class="gauge-num" id="gaugeTxt">--</text>
        <text x="60" y="76" class="gauge-cap">覆盖完整度</text>
      </svg>
      <div class="cov-note" id="gaugeNote"></div>
    </div>
    <div class="cov-cards" id="covCards"></div>
    <div class="cov-gaps" id="covGaps"></div>
    <div class="cov-scope" id="covScope"></div>
  </section>

  <!-- ================= 工具条 ================= -->
  <section class="toolbar">
    <div class="tb-group">
      <input id="search" class="search" type="search" placeholder="搜索节点（名称/别名/CAS）…" autocomplete="off">
      <div id="searchDrop" class="search-drop"></div>
    </div>
    <div class="tb-group" id="typeChips"></div>
    <div class="tb-group">
      <span class="tb-label">工艺筛选</span>
      <select id="routeSel" class="sel"><option value="">全部工艺路线</option></select>
      <select id="relSel" class="sel"><option value="">全部关系类型</option></select>
    </div>
    <div class="tb-group right">
      <button class="btn" id="btnZoomOut" title="缩小">−</button>
      <button class="btn" id="btnZoomIn" title="放大">＋</button>
      <button class="btn" id="btnFit" title="按可读比例聚焦目标品种">适应</button>
      <button class="btn" id="btnFitAll" title="整图缩放到一屏（总览）">总览</button>
      <button class="btn" id="btnReset" title="重置视图">重置</button>
      <button class="btn" id="btnCovToggle" title="折叠/展开覆盖面板">覆盖面板</button>
      <button class="btn" id="btnTableMode" title="切换层级关系表">层级表</button>
      <button class="btn primary" id="btnPriceLink" title="选中两个产品做价格联动">价格联动</button>
    </div>
  </section>

  <!-- ================= 选中状态条 ================= -->
  <div class="selbar" id="selbar">
    <span class="sel-hint">提示：单击节点看详情；按住 <b>Ctrl/⌘</b> 再点第二个节点可做价格联动；单击连线看工艺与单耗来源。</span>
    <span class="sel-chips" id="selChips"></span>
  </div>

  <!-- ================= 主体：画布 + 侧栏 ================= -->
  <main class="stage">
    <div class="canvas-wrap" id="canvasWrap">
      <div class="hint" id="hint">滚轮缩放 · 拖拽平移 · 双击空白处复位</div>
      <svg id="svg" xmlns="http://www.w3.org/2000/svg">
        <defs id="defs"></defs>
        <g id="viewport">
          <g id="laneLayer"></g>
          <g id="edgeLayer"></g>
          <g id="labelLayer"></g>
          <g id="nodeLayer"></g>
        </g>
      </svg>
      <div class="minimap-wrap" id="minimapWrap">
        <svg id="minimap" viewBox="0 0 1000 320" preserveAspectRatio="xMidYMid meet">
          <g id="miniNodes"></g>
          <rect id="miniView" class="mini-view" x="0" y="0" width="120" height="60"></rect>
        </svg>
      </div>
      <div class="canvas-legend" id="legend"></div>
    </div>

    <aside class="sidebar" id="sidebar">
      <div class="sb-head">
        <div class="sb-tabs">
          <button class="sb-tab active" data-tab="node">节点</button>
          <button class="sb-tab" data-tab="rel">关系</button>
          <button class="sb-tab" data-tab="link">联动</button>
        </div>
        <button class="sb-close" id="sbClose" title="收起侧栏">⟩</button>
      </div>
      <div class="sb-body" id="sbBody"></div>
    </aside>
    <button class="sb-open" id="sbOpen" title="展开侧栏">⟨</button>
  </main>

  <!-- ================= 层级关系表（兜底视图） ================= -->
  <section class="tablemode" id="tableMode">
    <div class="tm-head">
      <h2>层级关系表（可操作兜底视图）</h2>
      <div class="tm-note" id="tmNote"></div>
    </div>
    <div class="tm-scroll" id="tmScroll"></div>
  </section>

  <footer class="foot" id="foot"></footer>
</div>
<script>window.CHAIN_DATA = /*__CHAIN_DATA__*/null;</script>
<script>//__CHAIN_JS__</script>
</body>
</html>
