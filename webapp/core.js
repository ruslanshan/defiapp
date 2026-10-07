/*
 * Клиентская логика без DOM. Классификацию и тиры готовит сборщик (collector/), здесь —
 * только то, что зависит от капитала пользователя и фильтров.
 *
 * Показатели как в таблице:
 *   Объём за 1 день     = объём за 30 дней / 30 (если истории меньше — среднее по имеющимся дням)
 *   Объём / TVL         = объём за 1 день / TVL
 *   Комиссии в сутки    = объём за 1 день × уровень комиссии
 *   Твоя доля в пуле    = взнос / (TVL + взнос)   — в таблице было взнос / TVL, разница описана во вкладке «Тиры»
 *   Твой доход в сутки  = комиссии в сутки × доля
 *   Доход в месяц       = доход в сутки × 30
 *   APR                 = доход в сутки × 365 / взнос
 * Для лендинга и хранилищ без комиссий доход в сутки = взнос × APY / 365.
 */
(function (root) {
  "use strict";

  const RISK_MULT = { 1: 1, 2: 0.75, 3: 0.5 };
  const APY_CAP = { stables: 80, pairs: 300, rewards: 300 };
  const DILUTION_WARN = 5; // %, доля в пуле, после которой предупреждаем

  const CAT_LABEL = {
    lending: "Лендинг", savings: "Сбережения", dex: "DEX LP",
    perp: "Перп-LP", vault: "Хранилище", yield: "PT / LP доходности"
  };
  const STABLE_KIND = { lending: "lending", savings: "savings", dex: "lp", perp: "strategy", vault: "strategy", yield: "strategy" };
  const TIER_NAME = { 1: "низкий", 2: "средний", 3: "высокий" };

  const hasFees = (p) => p.fee != null && p.v1d != null;

  function personal(p, capital) {
    const C = Math.max(1, capital);
    const share = C / (p.tvl + C);
    let day, apr, feesDay = null, volTvl = null;
    if (hasFees(p)) {
      feesDay = p.v1d * p.fee;
      volTvl = p.v1d / p.tvl;
      day = feesDay * share;
      apr = day * 365 / C * 100;
    } else {
      apr = p.apy || 0;
      day = C * apr / 100 / 365;
    }
    const dayRew = C * (p.rew || 0) / 100 / 365;
    return { share: share * 100, day, month: day * 30, apr, feesDay, volTvl, dayRew, monthRew: dayRew * 30 };
  }

  /** Доходность для ранжирования: награды вполовину, всплески APY режем средним за 30 дней */
  function effApy(p, m) {
    if (hasFees(p)) return m.apr;
    let y = p.base != null ? p.base + 0.5 * (p.rew || 0) : (p.apy || 0) * 0.75;
    if (p.m30 != null && p.m30 > 0) y = Math.min(y, p.m30 * 1.5 + 0.5);
    return y;
  }

  function liqMult(tvl) {
    return Math.min(1, Math.max(0.6, 0.7 + 0.1 * Math.log10(Math.max(tvl, 1) / 1e6)));
  }

  /** Добавляет к каждому пулу p.m (личные показатели) и p.ra (доходность с поправкой на риск) */
  function applyCapital(pools, capital) {
    for (const p of pools) {
      p.m = personal(p, capital);
      p.ex = exitInfo(p, capital);
      p.ra = effApy(p, p.m) * RISK_MULT[p.tier] * liqMult(p.tvl);
    }
    return pools;
  }

  /*
   * Можно ли забрать деньги в любой момент.
   * instant — сразу; pool (лендинг) — сразу, если свободной ликвидности хватает с большим запасом
   * (в 20 раз больше капитала и не меньше $1 млн) и рынок не перегружен заёмщиками (загрузка < 95%).
   */
  const UTIL_WARN = 0.9, UTIL_BLOCK = 0.95, FREE_MULT = 20, FREE_MIN = 1e6;
  function exitInfo(p, capital) {
    const t = p.exit || "unknown";
    if (t === "instant") return { ok: true, label: "Вывод сразу" };
    if (t === "pool") {
      const free = p.free != null ? p.free : p.tvl;
      const need = Math.max(FREE_MULT * capital, FREE_MIN);
      if (p.util != null && p.util >= UTIL_BLOCK) return { ok: false, label: "Рынок перегружен", warn: true, free };
      if (free < need) return { ok: false, label: "Мало свободной ликвидности", warn: true, free };
      return { ok: true, label: "Вывод сразу", warn: p.util != null && p.util >= UTIL_WARN, free };
    }
    if (t === "cooldown") return { ok: false, label: `Вывод через ${p.exitDays || "?"} дн.` };
    if (t === "lock") return { ok: false, label: `Блокировка ${p.exitDays || "?"} дн.` };
    if (t === "queue") return { ok: false, label: "Вывод через очередь" };
    if (t === "market") return { ok: false, label: "Выход по рынку" };
    return { ok: false, label: "Условия вывода неизвестны" };
  }

  function stableKind(cat) { return STABLE_KIND[cat] || "strategy"; }

  function filterPools(pools, s) {
    const cap = APY_CAP[s.tab];
    return pools.filter(p => {
      if (p.tvl < s.minTvl) return false;
      if (s.chain !== "all" && p.chain !== s.chain) return false;
      if (!s.showOutliers && (p.outlier || (p.apy || 0) > cap)) return false;
      if (s.exitNow && !(p.ex && p.ex.ok)) return false;
      const assets = p.assets || [];
      if (s.tab === "stables") {
        return p.kind === "stable" && !p.dup && (s.stableKind === "all" || stableKind(p.cat) === s.stableKind);
      }
      if (s.tab === "pairs") {
        if (p.kind !== "pair" || p.dup) return false;
        if (s.asset !== "all" && !assets.includes(s.asset)) return false;
        if (s.quote !== "all" && p.quote !== s.quote) return false;
        return s.pairKind === "all" || (s.pairKind === "dex" ? p.cat === "dex" : p.cat === "perp");
      }
      if (s.tab === "rewards") {
        if (!(p.rew > 0)) return false;
        if (s.asset !== "all" && !assets.includes(s.asset)) return false;
        return s.rewardKind === "all" || p.kind === s.rewardKind;
      }
      return false;
    });
  }

  function ladder(list) {
    const best = { 1: null, 2: null, 3: null };
    for (const p of list) if (!best[p.tier] || p.ra > best[p.tier].ra) best[p.tier] = p;
    return best;
  }

  const SORTS = {
    ra: (a, b) => b.ra - a.ra,
    apr: (a, b) => b.m.apr - a.m.apr,
    month: (a, b) => b.m.month - a.m.month,
    voltvl: (a, b) => (b.m.volTvl ?? -1) - (a.m.volTvl ?? -1),
    tvl: (a, b) => b.tvl - a.tvl,
    tier: (a, b) => a.tier - b.tier || b.ra - a.ra,
    rew: (a, b) => (b.rew || 0) - (a.rew || 0),
    free: (a, b) => ((b.ex && b.ex.free) ?? -1) - ((a.ex && a.ex.free) ?? -1)
  };
  function sortPools(list, key) { return list.slice().sort(SORTS[key] || SORTS.ra); }

  function chainList(pools) {
    const sum = new Map();
    for (const p of pools) sum.set(p.chain, (sum.get(p.chain) || 0) + p.tvl);
    return [...sum.entries()].sort((a, b) => b[1] - a[1]).map(e => e[0]);
  }

  root.DYCore = {
    personal, applyCapital, exitInfo, filterPools, ladder, sortPools, chainList, liqMult, stableKind, hasFees,
    catLabel: c => CAT_LABEL[c] || "Прочее",
    tierName: t => TIER_NAME[t] || "?",
    RISK_MULT, APY_CAP, DILUTION_WARN
  };
})(typeof window !== "undefined" ? window : globalThis);
