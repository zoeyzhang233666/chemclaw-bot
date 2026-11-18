/* 历史价格位置报告 —— 图表与交互 */
(function () {
  "use strict";
  var D = window.__DATA__;
  if (!D) return;
  var A = D.analysis, SER = D.series;
  var CH = {};

  var C = {
    s1: "#12304F", s2: "#2E8B7A", s3: "#C8892B",
    band: "rgba(46,111,158,0.10)", grid: "#E8EDF2",
    ink: "#0F1720", grey: "#6B7A8C", red: "#B0303F", amber: "#C8892B"
  };

  function el(id) { return document.getElementById(id); }
  function fmt(n, d) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return Number(n).toFixed(d === undefined ? 2 : d);
  }

  /* ---------------- 主价格图 ---------------- */
  var state = { win: 365, ser: "S1", band: false, anom: false };

  function seriesRows(key) {
    var s = SER[key];
    return (s && s.data) || [];
  }

  function buildPriceOption() {
    var asof = new Date(D.meta.asof);
    var cut = state.win ? new Date(asof.getTime() - state.win * 864e5) : null;

    function filt(rows) {
      return rows.filter(function (r) {
        return !cut || new Date(r.date) > cut;
      });
    }

    var useKeys = state.ser === "ALL" ? ["S1", "S2", "S3"] : [state.ser];
    var colors = { S1: C.s1, S2: C.s2, S3: C.s3 };
    var names = { S1: "华东重质纯碱（区间中值）", S2: "华东轻质纯碱（区间中值)", S3: "全国重质纯碱（生意社基准价）" };

    var series = [];
    var allDates = [];

    useKeys.forEach(function (k) {
      var rows = filt(seriesRows(k));
      if (!rows.length && k !== "S1") return;
      var data = rows.map(function (r) {
        var v = (r.mid !== undefined) ? r.mid : r.value;
        return [r.date, v];
      });
      allDates = allDates.concat(rows.map(function (r) { return r.date; }));
      series.push({
        name: names[k], type: "line", smooth: false, showSymbol: false,
        symbolSize: 6, lineStyle: { width: state.ser === "ALL" ? 1.6 : 2.1, color: colors[k] },
        itemStyle: { color: colors[k] }, emphasis: { focus: "series" },
        data: data,
        z: k === "S1" ? 5 : 3
      });
    });

    /* 分位带：只对当前选中单一序列，用窗口内真实观测的分位值画水平带 */
    var markArea = null, markLine = null;
    if (state.band && state.ser !== "ALL") {
      var w = A[state.ser === "S1" ? "S1_mid" : state.ser === "S2" ? "S2_mid" : "S3_value"];
      var winKey = String(state.win || 1826);
      var st = w && w.windows[winKey] && w.windows[winKey].stats;
      if (st) {
        markArea = {
          silent: true,
          itemStyle: { color: "rgba(46,111,158,0.07)" },
          data: [
            [{ yAxis: st.p25, name: "P25" }, { yAxis: st.p75, name: "P75" }]
          ],
          label: { show: true, position: "insideTopLeft", color: C.grey, fontSize: 11, formatter: "P25–P75 区间" }
        };
        markLine = {
          silent: true, symbol: "none",
          lineStyle: { type: "dashed", color: C.grey, width: 1 },
          label: { color: C.grey, fontSize: 11, formatter: function (p) { return p.name + " " + fmt(p.value, 0); } },
          data: [
            { yAxis: st.median, name: "中位" },
            { yAxis: st.p10, name: "P10" },
            { yAxis: st.p90, name: "P90" }
          ]
        };
      }
    }
    if (series.length && (markArea || markLine)) {
      series[0].markArea = markArea || undefined;
      series[series.length - 1].markLine = markLine || undefined;
    }

    /* 异常点散点 */
    if (state.anom && state.ser !== "ALL") {
      var key = state.ser === "S1" ? "S1_mid" : state.ser === "S2" ? "S2_mid" : "S3_value";
      var an = (A[key] && A[key].anomalies) || { level: [], jump: [] };
      var seen = {};
      var pts = [];
      (an.level || []).forEach(function (a) { if (!seen[a.date]) { seen[a.date] = 1; pts.push([a.date, a.value, "level"]); } });
      (an.jump || []).forEach(function (a) { if (!seen[a.date]) { seen[a.date] = 1; pts.push([a.date, a.value, "jump"]); } });
      series.push({
        name: "异常点", type: "scatter", symbolSize: 9, z: 12,
        itemStyle: {
          color: function (p) { return p.data[2] === "jump" ? C.red : C.amber; },
          borderColor: "#fff", borderWidth: 1.2
        },
        data: pts,
        tooltip: { formatter: function (p) { return p.data[0] + "<br>异常点 " + fmt(p.data[1], 2) + " 元/吨"; } }
      });
    }

    allDates.sort();
    return {
      animationDuration: 420,
      grid: { left: 62, right: 22, top: 42, bottom: 62 },
      legend: { top: 6, left: 4, itemWidth: 16, itemHeight: 8, textStyle: { color: "#33414F", fontSize: 12 } },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", label: { backgroundColor: C.s1 } },
        backgroundColor: "rgba(255,255,255,.97)", borderColor: "#DCE3EB",
        textStyle: { color: "#0F1720", fontSize: 12.5 },
        extraCssText: "box-shadow:0 8px 24px -8px rgba(16,24,40,.25);border-radius:9px;padding:10px 13px",
        formatter: function (ps) {
          if (!ps.length) return "";
          var date = ps[0].axisValue;
          var h = '<div style="font-weight:700;margin-bottom:5px">' + date + "</div>";
          ps.forEach(function (p) {
            if (p.seriesType === "scatter") return;
            var k = p.seriesName;
            var row = null;
            var key = k.indexOf("重质") === 0 && k.indexOf("华东") === 0 ? "S1" : (k.indexOf("轻质") >= 0 ? "S2" : "S3");
            var rows = seriesRows(key);
            for (var i = 0; i < rows.length; i++) if (rows[i].date === p.axisValue) { row = rows[i]; break; }
            h += '<div style="display:flex;gap:10px;justify-content:space-between">' +
              "<span>" + p.marker + k + "</span><b>" + fmt(p.value, 2) + "</b></div>";
            if (row && row.lo !== undefined) {
              h += '<div style="color:#6B7A8C;font-size:11.5px;padding-left:14px">区间 ' +
                fmt(row.lo, 0) + "–" + fmt(row.hi, 0) + " 元/吨</div>";
            }
            if (row && row.url) {
              h += '<div style="font-size:11px;padding-left:14px"><a href="' + row.url +
                '" target="_blank" style="color:#1E4A73">查看当日报价原文</a></div>';
            }
          });
          h += '<div style="color:#6B7A8C;font-size:11px;margin-top:4px">来源：生意社（100ppi.com）</div>';
          return h;
        }
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#C6D0DA" } },
        axisLabel: { color: C.grey, fontSize: 11.5 },
        splitLine: { show: false }
      },
      yAxis: {
        type: "value", scale: true,
        name: "元/吨", nameTextStyle: { color: C.grey, fontSize: 11.5, padding: [0, 0, 6, 0] },
        axisLabel: { color: C.grey, fontSize: 11.5, formatter: function (v) { return v.toFixed(0); } },
        splitLine: { lineStyle: { color: C.grid } }
      },
      dataZoom: [
        { type: "inside", throttle: 60 },
        { type: "slider", height: 22, bottom: 12, borderColor: "#DCE3EB",
          fillerColor: "rgba(18,48,79,.07)", handleStyle: { color: "#12304F" },
          textStyle: { color: C.grey, fontSize: 10.5 } }
      ],
      series: series
    };
  }

  function renderPrice() {
    var dom = el("priceChart");
    if (!dom) return;
    if (!CH.price) CH.price = echarts.init(dom, null, { renderer: "canvas" });
    CH.price.setOption(buildPriceOption(), true);
    var note = el("chartNote");
    if (note) {
      var s = SER[state.ser];
      var rows = s ? s.data : [];
      note.innerHTML = rows.length
        ? "序列：" + s.name + "；共 " + rows.length + " 条真实观测（" + rows[0].date + " 至 " +
          rows[rows.length - 1].date + "）。" + (s.note || "")
        : "该序列在当前数据集中无观测。";
    }
  }

  /* ---------------- 季节性图 ---------------- */
  function renderSeason() {
    var a = A.S1_mid || A.S2_mid;
    if (!a || !a.seasonality) return;
    var m = a.seasonality.matrix || {};
    var years = [];
    Object.keys(m).forEach(function (mo) {
      Object.keys(m[mo]).forEach(function (y) { if (years.indexOf(y) < 0) years.push(y); });
    });
    years.sort();
    var palette = ["#C8D6E0", "#8FB3C9", "#4E86AD", "#12304F"];

    var dom = el("seasonChart");
    if (dom) {
      if (!CH.season) CH.season = echarts.init(dom, null, { renderer: "canvas" });
      CH.season.setOption({
        grid: { left: 46, right: 14, top: 34, bottom: 34 },
        legend: { top: 0, itemWidth: 12, itemHeight: 7, textStyle: { fontSize: 11, color: "#33414F" } },
        tooltip: { trigger: "axis", textStyle: { fontSize: 12 } },
        xAxis: {
          type: "category", data: ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
          axisLabel: { fontSize: 11, color: C.grey }, axisLine: { lineStyle: { color: "#C6D0DA" } }
        },
        yAxis: {
          type: "value", scale: true,
          axisLabel: { fontSize: 11, color: C.grey, formatter: function (v) { return v.toFixed(0); } },
          splitLine: { lineStyle: { color: C.grid } }
        },
        series: years.map(function (y, i) {
          return {
            name: y + "年", type: "line", connectNulls: false,
            lineStyle: { width: i === years.length - 1 ? 2.4 : 1.5, color: palette[i % palette.length] },
            itemStyle: { color: palette[i % palette.length] }, symbolSize: 5,
            data: [1,2,3,4,5,6,7,8,9,10,11,12].map(function (mo) {
              var v = m[String(mo)] && m[String(mo)][y];
              return v === undefined ? null : v;
            })
          };
        })
      }, true);
    }

    var dom2 = el("seasonIdxChart");
    var si = a.seasonality.season_index || {};
    if (dom2) {
      if (!CH.seasonIdx) CH.seasonIdx = echarts.init(dom2, null, { renderer: "canvas" });
      var vals = [1,2,3,4,5,6,7,8,9,10,11,12].map(function (mo) { return si[String(mo)] || null; });
      CH.seasonIdx.setOption({
        grid: { left: 46, right: 14, top: 22, bottom: 34 },
        tooltip: { trigger: "axis", valueFormatter: function (v) { return v === null ? "无观测" : v + ""; } },
        xAxis: {
          type: "category", data: ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
          axisLabel: { fontSize: 11, color: C.grey }, axisLine: { lineStyle: { color: "#C6D0DA" } }
        },
        yAxis: {
          type: "value", scale: true, name: "指数",
          axisLabel: { fontSize: 11, color: C.grey }, nameTextStyle: { fontSize: 11, color: C.grey },
          splitLine: { lineStyle: { color: C.grid } }
        },
        series: [{
          type: "bar", barWidth: "52%",
          itemStyle: {
            color: function (p) { return p.value >= 100 ? "#C8892B" : "#4E86AD"; },
            borderRadius: [3, 3, 0, 0]
          },
          label: { show: true, position: "top", fontSize: 10, color: C.grey,
                   formatter: function (p) { return p.value === null ? "" : p.value.toFixed(1); } },
          data: vals
        }]
      }, true);
    }
  }

  /* ---------------- 交互 ---------------- */
  function bind() {
    var seg = el("winSeg");
    if (seg) seg.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      [].forEach.call(seg.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      state.win = parseInt(b.dataset.w, 10);
      renderPrice(); renderSeason();
    });
    var seg2 = el("serSeg");
    if (seg2) seg2.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      [].forEach.call(seg2.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      state.ser = b.dataset.s;
      renderPrice();
    });
    var bb = el("btnBand");
    if (bb) bb.addEventListener("click", function () {
      state.band = !state.band;
      bb.classList.toggle("pri", state.band);
      renderPrice();
    });
    var ba = el("btnAnom");
    if (ba) ba.addEventListener("click", function () {
      state.anom = !state.anom;
      ba.classList.toggle("pri", state.anom);
      renderPrice();
    });
    var bc = el("btnCsv");
    if (bc) bc.addEventListener("click", exportCsv);

    window.addEventListener("resize", function () {
      Object.keys(CH).forEach(function (k) { CH[k] && CH[k].resize(); });
    });
  }

  /* ---------------- CSV 导出 ---------------- */
  function exportCsv() {
    var lines = [];
    lines.push("序列,日期,数值,区间低,区间高,单位,口径说明,原文链接");
    ["S1", "S2", "S3"].forEach(function (k) {
      var s = SER[k]; if (!s) return;
      s.data.forEach(function (r) {
        var v = (r.mid !== undefined) ? r.mid : r.value;
        lines.push([s.name, r.date, v, r.lo === undefined ? "" : r.lo,
                    r.hi === undefined ? "" : r.hi, "元/吨",
                    D.meta.region + " / " + D.meta.tax, r.url || ""].join(","));
      });
    });
    var blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = D.meta.product + "-" + D.meta.region + "-历史价格序列-" + D.meta.asof + ".csv";
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1200);
  }

  /* ---------------- 启动 ---------------- */
  function start() {
    bind();
    renderPrice();
    renderSeason();
    /* 点击异常点 -> 滚动到事件区 */
    if (CH.price) {
      CH.price.on("click", function (p) {
        if (p.seriesType === "scatter") {
          var sec = document.querySelectorAll("section");
          for (var i = 0; i < sec.length; i++) {
            if (sec[i].textContent.indexOf("历史异常点与可核验事件") >= 0) {
              sec[i].scrollIntoView({ behavior: "smooth", block: "start" }); break;
            }
          }
        }
      });
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  window.__CH__ = CH;
})();
