"""Check price geometry, independently of axes, annotations and cost lines."""


def check_price_chart(page):
    return page.evaluate("""() => {
      const el = document.querySelector('#chart');
      const chart = window.echarts && echarts.getInstanceByDom(el);
      if (!chart) return ['主图未初始化'];
      const issues = [];
      const series = chart.getModel().getSeries();
      const main = series[0];
      if (!main || !main.getData().count()) return ['主价格序列为空'];
      for (const model of series.filter(s => s.subType === 'candlestick' || s === main)) {
        const data = model.getData();
        const linePoints = data.getLayout('points');
        let valid = 0;
        for (let i = 0; i < data.count(); i++) {
          const layout = data.getItemLayout(i);
          const points = model.subType === 'candlestick' ? layout?.ends
            : layout || (linePoints && [linePoints[i*2], linePoints[i*2+1]]);
          if (data.hasValue(i) && Array.isArray(points) && points.flat().every(Number.isFinite)) valid++;
        }
        if (!valid) issues.push(model.subType + ' 没有有效价格图元');
      }
      const option = chart.getOption();
      if (typeof state !== 'undefined' && state.chart === 'monthly') {
        const labels = option.xAxis[0].data;
        if (!labels.length || labels.some(label => !/^\\d{4}-\\d{2}$/.test(label)))
          issues.push('月度均价横轴必须是实际月份');
        if (state.win !== 'all') {
          const groups = new Map();
          for (const row of D.series[seriesKey(state.win)] || []) {
            const month = row[0].slice(0,7);
            if (!groups.has(month)) groups.set(month, []);
            groups.get(month).push(row[2]);
          }
          const expected = [...groups.values()].map(values=>values.reduce((a,b)=>a+b,0)/values.length);
          if (option.series[0].data.length !== expected.length ||
              expected.some((value,i)=>Math.abs(option.series[0].data[i]-value)>0.0001))
            issues.push('月均数值未按交易日收盘价聚合');
        }
      }
      for (const series of option.series.filter(s => s.type === 'candlestick')) {
        if (series.data.some(row => !Array.isArray(row) || row.length !== 4 || !row.every(Number.isFinite)))
          issues.push('蜡烛必须只含四列数值：开、收、低、高');
      }
      const lower = option.series.find(s => s.name === '区间下沿');
      const band = option.series.find(s => s.name === '区间带');
      if (lower && band && (!lower.stack || lower.stack !== band.stack))
        issues.push('报价区间带未叠在下沿上');
      return issues;
    }""")
