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
