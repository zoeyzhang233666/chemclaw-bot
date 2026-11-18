'use strict';
/**
 * geo.cjs —— 区域采购成本模型 · 地理距离与运费模块
 *
 * 设计原则（与 SKILL.md「三条硬规矩」一致）：
 *   1) 距离只来自两种来源：用户填写的「实测里程」或「按途经点计算的陆路里程」；
 *      两者都标注依据（source/basis），绝不静默生成。
 *   2) 运费绝不自动填数。calculate() 只会：用用户输入的单价 × 里程计算（派生），
 *      或使用用户填写的总运费；两者都没有 → 该线路标记 full_landed=false。
 *
 * 里程算法：沿「途经城市」多边形链的大圆距离之和 × 线路曲折系数（detour_factor）。
 * 曲折系数默认 1.0 —— 已用 11 条真实公路里程标定（scripts/calibrate.cjs）：
 *   · 途经点足够密（每 100~200 km 一个枢纽）时，折线和本身已贴合高速走向，
 *     平均偏差 -2.3%、相对 RMSE 9.5%；
 *   · 若改用 1.15 的经验系数，平均偏差会变成 +12.3%，属系统性高估，故不采用。
 * 途经点过疏（省掉关键枢纽城市）时折线会低估，此时应由用户提高 detour_factor 或改用实测里程。
 *
 * 坐标系：WGS84 近似的球面（地心均半径 6371.0088 km）。
 */

const R_EARTH = 6371.0088;

/* ------------------------------------------------------------------ *
 * 1. 中国地级市参考坐标（市政府驻地，WGS84，保留四位小数）
 *    用于「从产地城市 / 收货地 → 途经城市」的大圆距离求和。
 *    坐标只需支撑 5~10 km 一档的精度；若需更高精度请用实测里程覆盖。
 * ------------------------------------------------------------------ */
const CITY_COORDS = {
  // —— 华东 ——
  上海: [121.4737, 31.2304],
  南京: [118.7969, 32.0603],
  苏州: [120.5853, 31.2989],
  无锡: [120.3119, 31.4912],
  常州: [119.9741, 31.8112],
  南通: [120.8943, 31.9802],
  扬州: [119.4129, 32.3942],
  镇江: [119.4250, 32.1878],
  泰州: [119.9229, 32.4557],
  盐城: [120.1396, 33.3776],
  淮安: [119.0153, 33.6104],
  连云港: [119.2216, 34.5967],
  徐州: [117.1848, 34.2618],
  宿迁: [118.2752, 33.9631],
  杭州: [120.1551, 30.2741],
  宁波: [121.5503, 29.8746],
  嘉兴: [120.7555, 30.7461],
  湖州: [120.0868, 30.8943],
  绍兴: [120.5820, 30.0297],
  合肥: [117.2272, 31.8206],
  芜湖: [118.4329, 31.3525],
  蚌埠: [117.3885, 32.9166],
  淮北: [116.7946, 33.9551],
  宿州: [116.9642, 33.6462],
  阜阳: [115.8142, 32.8901],
  淮南: [117.0183, 32.6534],
  滁州: [118.3171, 32.3005],
  六安: [116.5219, 31.7350],
  安庆: [117.0430, 30.5082],
  铜陵: [117.8121, 30.9452],
  福州: [119.2965, 26.0745],
  厦门: [118.0894, 24.4798],
  泉州: [118.6757, 24.8741],
  南昌: [115.8582, 28.6829],
  九江: [116.0018, 29.7051],
  赣州: [114.9337, 25.8309],
  济南: [117.1201, 36.6512],
  青岛: [120.3826, 36.0671],
  淄博: [118.0548, 36.8135],
  枣庄: [117.3237, 34.8107],
  东营: [118.6748, 37.4340],
  烟台: [121.3914, 37.5393],
  潍坊: [119.1618, 36.7069],
  济宁: [116.5871, 35.4149],
  泰安: [117.0879, 36.2001],
  临沂: [118.3564, 35.1047],
  德州: [116.3575, 37.4355],
  聊城: [115.9850, 36.4560],
  滨州: [117.9707, 37.3820],
  菏泽: [115.4806, 35.2332],
  日照: [119.5268, 35.4164],
  威海: [122.1204, 37.5131],
  莱州: [119.9425, 37.1776],
  龙口: [120.4774, 37.6466],
  沂水: [118.6294, 35.7901],
  寿光: [118.7912, 36.8556],
  高密: [119.7556, 36.3817],
  // —— 华北 ——
  北京: [116.4074, 39.9042],
  天津: [117.2010, 39.0842],
  石家庄: [114.5149, 38.0428],
  唐山: [118.1802, 39.6304],
  秦皇岛: [119.6005, 39.9354],
  邯郸: [114.4905, 36.6122],
  邢台: [114.5046, 37.0716],
  保定: [115.4646, 38.8739],
  张家口: [114.8840, 40.8119],
  承德: [117.9629, 40.9541],
  沧州: [116.8388, 38.3045],
  廊坊: [116.6837, 39.5383],
  衡水: [115.6706, 37.7389],
  沙河: [114.5038, 36.8549],
  涉县: [113.6914, 36.5846],
  吴桥: [116.3919, 37.6269],
  太原: [112.5489, 37.8706],
  大同: [113.3001, 40.0768],
  阳泉: [113.5805, 37.8572],
  长治: [113.1163, 36.1956],
  晋城: [112.8513, 35.4975],
  银川: [106.2782, 38.4664],
  呼和浩特: [111.7492, 40.8423],
  包头: [109.8403, 40.6574],
  // —— 华中 ——
  郑州: [113.6254, 34.7466],
  开封: [114.3076, 34.7972],
  洛阳: [112.4540, 34.6197],
  平顶山: [113.1926, 33.7663],
  安阳: [114.3925, 36.0977],
  新乡: [113.9268, 35.3030],
  焦作: [113.2418, 35.2159],
  濮阳: [115.0292, 35.7619],
  许昌: [113.8523, 34.0357],
  漯河: [114.0165, 33.5815],
  三门峡: [111.2003, 34.7726],
  南阳: [112.5286, 32.9908],
  商丘: [115.6564, 34.4143],
  信阳: [114.0911, 32.1475],
  周口: [114.6969, 33.6264],
  驻马店: [114.0229, 33.0117],
  桐柏: [113.4287, 32.3804],
  武汉: [114.3054, 30.5931],
  黄石: [115.0389, 30.1997],
  十堰: [110.7879, 32.6291],
  宜昌: [111.2865, 30.6919],
  襄阳: [112.1224, 32.0420],
  鄂州: [114.8948, 30.3915],
  荆门: [112.1993, 31.0354],
  荆州: [112.2388, 30.3269],
  孝感: [113.9168, 30.9243],
  黄冈: [114.8722, 30.4539],
  咸宁: [114.3225, 29.8412],
  随州: [113.3827, 31.7173],
  长沙: [112.9388, 28.2282],
  株洲: [113.1340, 27.8274],
  湘潭: [112.9444, 27.8297],
  衡阳: [112.5617, 26.8939],
  岳阳: [113.1289, 29.3572],
  常德: [111.6985, 29.0316],
  益阳: [112.3551, 28.5538],
  郴州: [113.0146, 25.7936],
  冷水江: [111.4350, 27.6864],
  // —— 华南 ——
  广州: [113.2644, 23.1291],
  深圳: [114.0579, 22.5431],
  珠海: [113.5767, 22.2707],
  佛山: [113.1214, 23.0215],
  东莞: [113.7518, 23.0207],
  中山: [113.3927, 22.5170],
  惠州: [114.4126, 23.0790],
  江门: [113.0819, 22.5789],
  南宁: [108.3665, 22.8170],
  柳州: [109.4117, 24.3255],
  桂林: [110.2991, 25.2736],
  海口: [110.1999, 20.0440],
  湛江: [110.3594, 21.2707],
  北海: [109.1193, 21.4733],
  // —— 西南 ——
  重庆: [106.5516, 29.5630],
  成都: [104.0665, 30.5728],
  自贡: [104.7784, 29.3392],
  泸州: [105.4419, 28.8718],
  德阳: [104.3979, 31.1269],
  乐山: [103.7655, 29.5522],
  宜宾: [104.6433, 28.7529],
  昆明: [102.8329, 24.8801],
  贵阳: [106.6302, 26.6470],
  遵义: [106.9274, 27.7257],
  // —— 西北 ——
  西安: [108.9398, 34.3416],
  宝鸡: [107.2379, 34.3613],
  咸阳: [108.7051, 34.3330],
  渭南: [109.5097, 34.4997],
  榆林: [109.7348, 38.2853],
  兰州: [103.8343, 36.0611],
  西宁: [101.7782, 36.6171],
  格尔木: [94.9033, 36.4020],
  德令哈: [97.3707, 37.3745],
  海西: [97.3707, 37.3745],
  乌鲁木齐: [87.6168, 43.8256],
  哈密: [93.5151, 42.8193],
  嘉峪关: [98.2894, 39.7729],
  张掖: [100.4498, 38.9257],
  酒泉: [98.4943, 39.7325],
  // —— 东北 ——
  沈阳: [123.4315, 41.8057],
  大连: [121.6147, 38.9140],
  鞍山: [122.9946, 41.1085],
  锦州: [121.1270, 41.0952],
  营口: [122.2356, 40.6674],
  盘锦: [122.0707, 41.1199],
  长春: [125.3240, 43.8868],
  吉林市: [126.5494, 43.8379],
  哈尔滨: [126.5349, 45.8038],
  大庆: [125.1036, 46.5892],
};

/* 省级政府驻地：用于「收货地只给到省」时的退化处理 */
const PROVINCE_CAPITAL = {
  山东: '济南', 河北: '石家庄', 河南: '郑州', 江苏: '南京', 安徽: '合肥',
  浙江: '杭州', 江西: '南昌', 福建: '福州', 湖北: '武汉', 湖南: '长沙',
  广东: '广州', 广西: '南宁', 海南: '海口', 四川: '成都', 重庆: '重庆',
  贵州: '贵阳', 云南: '昆明', 陕西: '西安', 甘肃: '兰州', 青海: '西宁',
  宁夏: '银川', 山西: '太原', 内蒙古: '呼和浩特', 辽宁: '沈阳', 吉林: '长春',
  黑龙江: '哈尔滨', 北京: '北京', 天津: '天津', 上海: '上海', 新疆: '乌鲁木齐',
  西藏: '拉萨', 香港: '广州', 澳门: '广州',
};

const PROVINCES = Object.keys(PROVINCE_CAPITAL).filter((p) => !['香港', '澳门'].includes(p));

/* ------------------------------------------------------------------ *
 * 2. 基础几何
 * ------------------------------------------------------------------ */
function toRad(d) { return (d * Math.PI) / 180; }

/** 大圆距离（km），Haversine 公式 */
function haversine(a, b) {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** 地名标准化：去掉「省/市/县/区/旗」等尾缀与空白 */
function normPlace(name) {
  if (!name) return '';
  return String(name)
    .replace(/\s+/g, '')
    .replace(/(省|市|县|区|旗|镇|街道)$/g, '')
    .replace(/(省|市|县|区)人民政府$/g, '');
}

/** 解析「山东济南」「济南」→ {province?, city, coord}；失败返回 null */
function resolvePlace(name) {
  if (!name) return null;
  const raw = String(name).trim();
  let province = null;
  let rest = raw;
  for (const p of PROVINCES) {
    if (raw.startsWith(p)) { province = p; rest = raw.slice(p.length); }
    else if (raw.endsWith(p)) { province = p; rest = raw.slice(0, -p.length); }
  }
  const key = normPlace(rest);
  const candidates = [key];
  // 「苏州工业园区」「连云港灌云」这类：取前 2~3 字再试
  if (key.length >= 4) candidates.push(key.slice(0, 3), key.slice(0, 2));
  if (key.length === 3) candidates.push(key.slice(0, 2));
  for (const c of candidates) {
    if (CITY_COORDS[c]) return { query: raw, province, city: c, coord: CITY_COORDS[c] };
  }
  if (province && PROVINCE_CAPITAL[province]) {
    const c = PROVINCE_CAPITAL[province];
    return { query: raw, province, city: c, coord: CITY_COORDS[c], degraded: 'province-only' };
  }
  return null;
}

/**
 * 沿途经点链求和的大圆距离。
 * nodes: 城市名数组，如 ['苏州','南京','徐州','济宁','莱州'] 或含 [lon,lat] 的数组。
 * 返回 { straightKm, viaKm, legs:[{from,to,km}] }
 */
function chainDistance(nodes) {
  const pts = nodes.map((n) => (Array.isArray(n) ? { name: `${n[0]},${n[1]}`, coord: n } : resolvePlace(n)));
  const missing = pts.map((p, i) => (p ? null : nodes[i])).filter(Boolean);
  if (missing.length) {
    const e = new Error(`以下途经点无法识别坐标：${missing.join('、')}`);
    e.code = 'UNKNOWN_PLACE';
    throw e;
  }
  const legs = [];
  for (let i = 1; i < pts.length; i += 1) {
    legs.push({ from: pts[i - 1].name || pts[i - 1].query, to: pts[i].name || pts[i].query, km: haversine(pts[i - 1].coord, pts[i].coord) });
  }
  const viaKm = legs.reduce((s, l) => s + l.km, 0);
  const straightKm = pts.length >= 2
    ? haversine(pts[0].coord, pts[pts.length - 1].coord)
    : 0;
  return { straightKm, viaKm, legs, points: pts };
}

/* ------------------------------------------------------------------ *
 * 3. 线路里程求解
 *    route = {
 *      id, origin_city, dest_city, mode, basis,   // basis: 'via_points' | 'measured'
 *      via_points: ['苏州','南京',...],
 *      detour_factor: 1.0,   // 见文件头：已按 11 条实测线路标定
 *      measured_km: null,                         // basis='measured' 时必填
 *      distance_source: '',                       // 依据说明（路线/出处）
 *      ...
 *    }
 * ------------------------------------------------------------------ */
function routeDistance(route) {
  const basis = route.basis || (Number.isFinite(route.measured_km) ? 'measured' : 'via_points');
  if (basis === 'measured') {
    const km = Number(route.measured_km);
    if (!Number.isFinite(km) || km <= 0) {
      return { ok: false, reason: 'basis=measured 但 measured_km 缺失或非正数' };
    }
    return {
      ok: true,
      basis,
      km,
      straightKm: null,
      viaKm: null,
      legs: [],
      note: route.distance_source || '用户提供实测里程',
    };
  }
  if (basis === 'measured_legs') {
    // 已知终点的多条「起→终」实测里程，用于一个区域多点报价（主报点低端 / 备选点高端）
    const legs = (route.legs || []).map((l) => ({
      from: l.from, to: l.to || route.dest_city, km: Number(l.km),
      hours: Number.isFinite(Number(l.hours)) ? Number(l.hours) : null,
      source: l.source || '', url: l.url || '', road: l.road || '',
    })).filter((l) => Number.isFinite(l.km) && l.km > 0);
    if (!legs.length) return { ok: false, reason: 'basis=measured_legs 但 legs 为空或里程无效' };
    const sorted = legs.slice().sort((a, b) => a.km - b.km);
    const list = sorted.map((l) => `${l.from} ${l.km} km`);
    return {
      ok: true,
      basis,
      km: Math.round(sorted[0].km),
      km_high: Math.round(sorted[sorted.length - 1].km),
      km_low: Math.round(sorted[0].km),
      straightKm: null,
      viaKm: null,
      legs: sorted,
      range_note: route.distance_ref_note || list.join('；'),
      note: '已核验公路里程：' + list.join('；'),
      verified: true,
    };
  }
  const via = (route.via_points || []).slice();
  if (via.length < 2) return { ok: false, reason: 'basis=via_points 但 via_points 少于 2 个点' };
  // 途经链首尾应就是起终点；若用户没写，自动补
  const head = via[0];
  const tail = via[via.length - 1];
  if (normPlace(head) !== normPlace(route.origin_city)) via.unshift(route.origin_city);
  if (normPlace(tail) !== normPlace(route.dest_city)) via.push(route.dest_city);
  let ch;
  try { ch = chainDistance(via); } catch (e) {
    return { ok: false, reason: e.message, unknown_places: true };
  }
  const f = Number.isFinite(Number(route.detour_factor)) ? Number(route.detour_factor) : 1.0;
  const km = Math.round(ch.viaKm * f);
  return {
    ok: true,
    basis,
    km,
    straightKm: Math.round(ch.straightKm),
    viaKm: Math.round(ch.viaKm),
    detourFactor: f,
    legs: ch.legs.map((l) => ({ from: l.from, to: l.to, km: Math.round(l.km) })),
    chain: via,
    note: route.distance_source || `途经 ${via.join('→')} 的大圆距离和 ${Math.round(ch.viaKm)} km × 曲折系数 ${f}`,
  };
}

/* ------------------------------------------------------------------ *
 * 4. 运费与到厂成本
 *    参数（COST_PARAMS 结构，可在 HTML 面板实时改）：
 *      qty:            采购数量（计价单位）
 *      unit:           't' | 'kg'
 *      loadingUnit:    装卸费单价（元/单位）  null=未知
 *      unloadingUnit:  卸货费单价（元/单位）  null=未知
 *      inspectionUnit: 检测/取样费单价（元/单位） null=未知
 *      taxRate:        运费可抵扣税率（%）   仅当价格口径为含税时生效
 *      priceBasis:     'incl_tax' | 'excl_tax'
 *    线路（route 附加字段）：
 *      freight_unit:   元/吨（每单位）运价；null=未知
 *      freight_total:  元总运费；null=未知（与 freight_unit 二选一，total 优先）
 *      loading_total / unloading_total / inspection_total / other_total：整单费用，可空
 * ------------------------------------------------------------------ */
const DEFAULTS = {
  cost: {
    qty: 100,
    unit: 't',
    loadingUnit: null,
    unloadingUnit: null,
    inspectionUnit: null,
    taxRate: 9,
    priceBasis: 'incl_tax',
  },
  detourFactor: 1.0,
};

/**
 * 数值解析。null / undefined / '' / 非有限值 一律返回 null（表示"未知"），
 * 绝不把缺失值当作 0 —— 否则「未填运费」会被算成「运费为 0」，
 * 从而生成一个看似精确但错误的到厂成本排名。
 */
function num(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string' && v.trim() === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * 线路运费求解。
 * 返回 { freight, how, missing:[字段名] }
 *   how: 'manual_total' | 'unit_x_distance' | 'manual_unit_only' | 'none'
 */
function solveFreight(route, line, cost) {
  const src = line || route || {};
  const ft = num(src.freight_total);
  const fu = num(src.freight_unit);
  const dist = route && route.distance && route.distance.ok ? route.distance.km : null;
  const qty = num(cost.qty) || 0;

  if (ft !== null && ft >= 0) {
    return { freight: ft, how: 'manual_total', unitRate: qty > 0 ? ft / qty : null, missing: [] };
  }
  if (fu !== null && fu >= 0) {
    if (dist === null || dist <= 0) {
      return { freight: null, how: 'manual_unit_only', unitRate: fu, missing: ['距离（无法计算总运费）'] };
    }
    return { freight: fu * dist, how: 'unit_x_distance', unitRate: fu, missing: [] };
  }
  return { freight: null, how: 'none', unitRate: null, missing: ['运费（每吨运价或总运费）'] };
}

/**
 * 主计算：对每个线路计算价格端、物流端、到厂成本与因素分解。
 * regions: [{ id, name, price:{value,unit,spec,basis,date,source}, route: RefToRoute }]
 * opts: { cost: COST_PARAMS, benchmarkRegionId }
 */
function calculate(input) {
  const cost = Object.assign({}, DEFAULTS.cost, (input && input.cost) || {});
  const routes = ((input && input.routes) || []).map((r) => {
    const d = routeDistance(r);
    return Object.assign({}, r, { distance: d });
  });
  const routeById = {};
  routes.forEach((r) => { routeById[r.id] = r; });

  const regions = ((input && input.regions) || []).map((reg) => {
    const route = routeById[reg.route_id] || reg.route || null;
    const price = reg.price || {};
    const pv = num(price.value != null ? price.value : price.price);
    const unitMult = (price.unit || '元/吨') === '元/吨' ? 1 : (price.unit === '元/千克' ? 1000 : null);
    const pricePerTon = pv !== null && unitMult !== null ? pv * unitMult : null;

    let freightRows = null;
    // 运费字段允许三种写法：① 路线顶层 freight_unit/freight_total（本工具标准）
    // ② 路线内嵌 route.freight = { unit, total, lines }（兼容外部数据）
    // ③ 多段 freight_lines
    if (route && !route.freight_unit && !route.freight_total && route.freight) {
      if (route.freight.unit != null) route.freight_unit = route.freight.unit;
      if (route.freight.total != null) route.freight_total = route.freight.total;
      if (!route.freight_lines && Array.isArray(route.freight.lines)) route.freight_lines = route.freight.lines;
    }
    if (route) {
      if (Array.isArray(route.freight_lines) && route.freight_lines.length) {
        // 多段（如 汽运+内河、铁路+短驳）：每段需要自己的运价
        const seg = route.freight_lines.map((fl) => ({
          mode: fl.mode, km: num(fl.km), freight_unit: num(fl.freight_unit),
          freight_total: num(fl.freight_total),
        }));
        const solved = seg.map((s) => {
          if (s.freight_total !== null) return s.freight_total;
          if (s.freight_unit !== null && s.km) return s.freight_unit * s.km;
          return null;
        });
        freightRows = solved.every((v) => v !== null) ? solved.reduce((a, b) => a + b, 0) : null;
        if (freightRows !== null) route.freight_solved = { freight: freightRows, how: 'segments' };
        else route.freight_solved = { freight: null, how: 'none', missing: ['多段运费（每段运价）'] };
      } else {
        route.freight_solved = solveFreight(route, route, cost);
      }
    }

    const fo = route ? route.freight_solved : { freight: null, how: 'none', missing: ['线路'] };
    const freight = fo.freight;
    const freightPerTon = freight !== null && num(cost.qty) > 0 ? freight / cost.qty : null;

    const operating = { loading: 0, unloading: 0, inspection: 0, other: 0 };
    const opMissing = [];
    const opUnit = {
      loading: num(cost.loadingUnit),
      unloading: num(cost.unloadingUnit),
      inspection: num(cost.inspectionUnit),
    };
    // 每单位费用 × 数量；整单费用若显式给出则覆盖
    const line = Object.assign({}, route || {});
    const pick = (unitKey, totalKey) => {
      const total = num(line[totalKey]);
      if (total !== null) return { v: total, ok: true };
      if (opUnit[unitKey] !== null) return { v: opUnit[unitKey] * (num(cost.qty) || 0), ok: true };
      return { v: 0, ok: false };
    };
    const l1 = pick('loading', 'loading_total');
    if (l1.ok) operating.loading = l1.v; else if (operating.loading === 0) opMissing.push('装车费');
    const l2 = pick('unloading', 'unloading_total');
    if (l2.ok) operating.unloading = l2.v; else opMissing.push('卸车费');
    const l3 = pick('inspection', 'inspection_total');
    if (l3.ok) operating.inspection = l3.v; else opMissing.push('检测/取样费');
    const l4 = num(line.other_total);
    if (l4 !== null) operating.other = l4;
    const opTotal = operating.loading + operating.unloading + operating.inspection + operating.other;
    const opPerTon = num(cost.qty) > 0 ? opTotal / cost.qty : 0;

    const priceExTon = cost.priceBasis === 'incl_tax' && pricePerTon !== null
      ? pricePerTon / (1 + (num(cost.taxRate) || 0) / 100)
      : pricePerTon;

    const fullLanded = pricePerTon !== null && freight !== null;
    const landedPerTon = fullLanded ? pricePerTon + freightPerTon + opPerTon : null;
    const landedTotal = fullLanded ? (pricePerTon * (num(cost.qty) || 0)) + freight + opTotal : null;

    const gaps = [];
    if (pricePerTon === null) gaps.push('现货价格缺值');
    opMissing.forEach((m) => gaps.push(m));
    (fo.missing || []).forEach((m) => gaps.push(m));
    if (route && !route.distance.ok) gaps.push(`距离：${route.distance.reason}`);

    return {
      id: reg.id,
      name: reg.name,
      price: Object.assign({}, price, { per_ton: pricePerTon, ex_tax_per_ton: priceExTon }),
      route_id: reg.route_id || null,
      region_market: reg.region_market || null,
      distance: route ? route.distance : null,
      transport_mode: route ? route.transport_mode || route.mode : null,
      freight: {
        solved: freight,
        per_ton: freightPerTon,
        how: fo.how,
        unit_rate_basis: fo.unitRate,
      },
      operating: {
        detail: operating,
        total: opTotal,
        per_ton: opPerTon,
      },
      landed: {
        per_ton: landedPerTon,
        total: landedTotal,
        full: fullLanded,
      },
      gaps,
    };
  });

  /* —— 价差与因素分解（以基准地区为参照） —— */
  const refId = (input && input.benchmark_region_id) || null;
  const ref = regions.find((r) => r.id === refId) || null;
  const priced = regions.filter((r) => r.price.per_ton !== null);
  const cheap = priced.length ? priced.reduce((a, b) => (b.price.per_ton < a.price.per_ton ? b : a)) : null;
  const cheapFull = regions.filter((r) => r.landed.full).reduce((a, b) => (!a || b.landed.per_ton < a.landed.per_ton ? b : a), null);

  regions.forEach((r) => {
    r.vs_ref = {};
    if (ref && r.id !== ref.id && r.price.per_ton !== null && ref.price.per_ton !== null) {
      const d = r.price.per_ton - ref.price.per_ton;
      r.vs_ref.price_gap = d;
      r.vs_ref.price_gap_pct = d / ref.price.per_ton;
      const rk = r.freight.per_ton; const fk = ref.freight.per_ton;
      const ro = r.operating.per_ton; const fo = ref.operating.per_ton;
      r.vs_ref.factors = [
        { key: 'price', label: '市场裸价', value: d, known: true },
        { key: 'freight', label: '运输费用', value: (rk !== null && fk !== null) ? rk - fk : null, known: rk !== null && fk !== null },
        { key: 'operating', label: '装卸/其他', value: (ro !== null && fo !== null) ? ro - fo : null, known: ro !== null && fo !== null },
      ];
      r.vs_ref.landed_gap = r.landed.full && ref.landed.full ? r.landed.per_ton - ref.landed.per_ton : null;
    }
  });

  return {
    cost,
    routes,
    regions,
    summary: {
      reference_region_id: ref ? ref.id : null,
      lowest_price_region: cheap ? cheap.name : null,
      lowest_price_region_id: cheap ? cheap.id : null,
      lowest_landed_region: cheapFull ? cheapFull.name : null,
      lowest_landed_region_id: cheapFull ? cheapFull.id : null,
      all_landed_complete: regions.length > 0 && regions.every((r) => r.landed.full),
      priced_count: priced.length,
    },
  };
}

module.exports = {
  R_EARTH, CITY_COORDS, PROVINCES, PROVINCE_CAPITAL,
  haversine, normPlace, resolvePlace, chainDistance,
  routeDistance, solveFreight, calculate, DEFAULTS,
};
