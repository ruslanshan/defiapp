#!/usr/bin/env python3
"""Сборщик данных для Mini App Yield Ladder (репозиторий defiapp).

Источники:
  CoinGecko        — топ-30 монет по капитализации (без стейблкоинов и обёрток);
  GeckoTerminal    — DEX-пулы: уровень комиссии, TVL, объём за 24 ч и дневной объём за 30 дней;
  DefiLlama Yields — лендинги, сбережения, хранилища, перп-LP и пулы с наградами токенами;
  DefiLlama Coins  — символы токенов наград;
  Hyperliquid      — хранилище HLP.

Запуск:  python collector/collect.py --out webapp/data.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import scoring as S

HERE = Path(__file__).resolve().parent
log = logging.getLogger("collector")

LLAMA_POOLS = "https://yields.llama.fi/pools"
LLAMA_COINS = "https://coins.llama.fi/prices/current/"
CG_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
GT_API = "https://api.geckoterminal.com/api/v2"
HL_INFO = "https://api.hyperliquid.xyz/info"
HLP_ADDR = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
CAPITAL_DEFAULT = 6000

# Название сети в DefiLlama Yields → префикс в API coins.llama.fi
LLAMA_CHAIN_KEYS = {
    "Ethereum": "ethereum", "Arbitrum": "arbitrum", "Base": "base", "Optimism": "optimism",
    "Polygon": "polygon", "BSC": "bsc", "Avalanche": "avax", "Solana": "solana", "Gnosis": "xdai",
    "zkSync Era": "era", "Hyperliquid L1": "hyperliquid", "Unichain": "unichain", "Sonic": "sonic",
    "Linea": "linea", "Scroll": "scroll", "Mantle": "mantle", "Berachain": "berachain", "Plasma": "plasma",
}
ADDRESS_RE = re.compile(r"^(0x[0-9a-fA-F]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})$")


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def pretty(slug: str) -> str:
    words = re.split(r"[-_\s]+", str(slug or "?"))
    return " ".join(w.upper() if re.fullmatch(r"v\d", w, re.I) else w[:1].upper() + w[1:] for w in words if w)


class Http:
    def __init__(self, gt_rpm: int):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "defiapp-collector/2.0"
        self.gt_gap = 60.0 / max(1, gt_rpm)
        self._last_gt = 0.0
        self.calls = 0
        self.rate_limited = 0

    def get(self, url, params=None, headers=None, timeout=60, retries=4, backoff=20):
        for attempt in range(retries):
            self.calls += 1
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                log.warning("%s: %s", url, e)
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                self.rate_limited += r.status_code == 429
                wait = _retry_after(r) or backoff * (attempt + 1)
                log.warning("%s → %s, пауза %s с", url, r.status_code, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"{url}: нет ответа после {retries} попыток")

    def post(self, url, payload, timeout=30):
        self.calls += 1
        r = self.s.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def gt(self, path, params=None):
        """GeckoTerminal: бесплатный лимит 30 запросов в минуту — держим паузу между вызовами.
        На серверах GitHub лимит делят с чужими проектами, поэтому после отказа (429) замедляемся."""
        wait = self._last_gt + self.gt_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last_gt = time.time()
        before = self.rate_limited
        try:
            return self.get(GT_API + path, params=params, headers={"Accept": "application/json;version=20230302"},
                            retries=3, backoff=15)
        finally:
            if self.rate_limited > before:
                self.gt_gap = min(self.gt_gap * 1.5, 12.0)


def _retry_after(r):
    try:
        return min(120, int(r.headers.get("Retry-After", "")))
    except ValueError:
        return None


# ---------------------------------------------------------------- топ-30

def build_universe(http: Http, size: int):
    key = os.environ.get("COINGECKO_API_KEY")
    headers = {"x-cg-demo-api-key": key} if key else None
    try:
        rows = http.get(CG_MARKETS, params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 150, "page": 1},
                        headers=headers, retries=2)
        out, seen = [], set()
        for r in rows or []:
            sym, name = str(r.get("symbol") or "").upper(), str(r.get("name") or "")
            if not sym or sym in seen or S.is_excluded_coin(sym, name):
                continue
            seen.add(sym)
            out.append({"id": r.get("id"), "symbol": sym, "name": name, "rank": r.get("market_cap_rank"),
                        "mcap": num(r.get("market_cap"))})
            if len(out) >= size:
                break
        if len(out) < size // 2:
            raise RuntimeError("в ответе слишком мало монет")
        return out, {"status": "ok", "count": len(out)}
    except Exception as e:  # noqa: BLE001 — любой сбой источника не должен ронять сборку
        log.warning("CoinGecko недоступен (%s), беру резервный список из tiers.js", e)
        fb = S.tiers()["assets"]["fallback_top"][:size]
        return ([{"id": None, "symbol": s, "name": s, "rank": i + 1, "mcap": None} for i, s in enumerate(fb)],
                {"status": "fallback", "count": len(fb), "note": str(e)[:200]})


# ---------------------------------------------------------------- общие поля

def finish(rec: dict, pr) -> dict:
    """Флаги, которые не зависят от капитала пользователя."""
    flags = list(rec.pop("_flags", []))
    for f in (pr or {}).get("flags", []):
        if not (rec["kind"] == "stable" and f == "il"):
            flags.append(f)
    if rec["kind"] == "pair" and rec["cat"] == "dex":
        flags.append("il")
    rew = rec.get("rew") or 0
    if rew > 0:
        flags.append("rewardtoken")
        if rec["apy"] and rew / rec["apy"] > 0.5 and "emissions" not in flags:
            flags.append("rewards")
    m30 = rec.get("m30")
    if rec["src"] == "llama" and m30 and rec["apy"] > 2 * m30 and rec["apy"] - m30 > 2:
        flags.append("spike")
    if rec["src"] == "gt":
        if rec.get("v30") is None:
            flags.append("vol24")
        elif rec["vdays"] < 30:
            flags.append("young")
        if rec.get("v24") and rec.get("v1d") and rec["v24"] > 3 * rec["v1d"] and rec["v24"] - rec["v1d"] > 1e5:
            flags.append("volspike")
    if rec["tvl"] < 1e6:
        flags.append("smalltvl")
    rec["flags"] = list(dict.fromkeys(flags))
    rec["tier"] = max(rec["pt"], rec["at"], rec["ct"])
    return rec


def dedupe_key(rec: dict) -> str:
    fee = round(rec["fee"] * 1e6) if rec.get("fee") else "?"
    return f'{rec["chain"]}|{rec["proto"]}|{"-".join(sorted(rec["keytoks"]))}|{fee}'


# ---------------------------------------------------------------- DefiLlama

def collect_llama(http: Http, clf: S.Classifier, cfg: dict) -> list[dict]:
    data = http.get(LLAMA_POOLS, timeout=180).get("data") or []
    floor, out = cfg["min_tvl_llama"], []
    for p in data:
        tvl, apy = num(p.get("tvlUsd")), num(p.get("apy"))
        if not p.get("pool") or tvl is None or tvl < floor or apy is None or apy <= 0:
            continue
        chain = str(p.get("chain") or "")
        raw = S.split_symbol(p.get("symbol"))
        if not raw or len(raw) > 2:
            continue
        toks = [clf.token(t, chain) for t in raw]
        if any(t is None for t in toks):
            if p.get("stablecoin") is not True:
                continue
            toks = [t or {"t": "stable", "sym": r, "tier": 3} for t, r in zip(toks, raw)]
        info = S.Classifier.combine(toks)
        rew = num(p.get("apyReward")) or 0.0
        if not info or (info["kind"] == "single" and rew <= 0):
            continue  # одиночный волатильный актив интересен только ради наград
        meta = str(p.get("poolMeta") or "")
        prot = S.protocol_info(p.get("project", ""), p.get("symbol", ""), meta)
        pr = prot["pr"]
        rec = {
            "id": p["pool"], "src": "llama", "kind": info["kind"], "quote": info["quote"], "assets": info["assets"],
            "chain": chain, "proto": pr["id"] if pr else p.get("project"),
            "pn": pr["name"] if pr else pretty(p.get("project")), "sym": str(p.get("symbol") or ""), "meta": meta,
            "keytoks": [t.get("base", t["sym"]) for t in toks],
            "fee": S.parse_fee(meta), "tvl": tvl, "apy": apy, "base": num(p.get("apyBase")), "rew": rew or None,
            "m30": num(p.get("apyMean30d")), "v24": num(p.get("volumeUsd1d")), "v1d": None, "v30": None,
            "vdays": None, "vh": None, "age": None,
            "rtRaw": [t for t in (p.get("rewardTokens") or []) if isinstance(t, str)], "rt": [],
            "pt": prot["pt"], "at": info["at"], "ct": S.chain_tier(chain),
            "cat": pr["cat"] if pr else ("dex" if p.get("exposure") == "multi" else "vault"),
            "outlier": bool(p.get("outlier")), "url": f"https://defillama.com/yields/pool/{p['pool']}",
            "purl": pr.get("url") if pr else None, "_flags": info["flags"],
        }
        out.append(finish(rec, pr))
    return out


def resolve_reward_symbols(http: Http, recs: list[dict]) -> dict:
    keys = set()
    for r in recs:
        prefix = LLAMA_CHAIN_KEYS.get(r["chain"], r["chain"].lower().replace(" ", ""))
        for t in r["rtRaw"]:
            if ADDRESS_RE.match(t):
                keys.add(f"{prefix}:{t}")
    found = {}
    keys = sorted(keys)
    for i in range(0, len(keys), 40):
        try:
            j = http.get(LLAMA_COINS + ",".join(keys[i:i + 40]), timeout=60)
        except Exception as e:  # noqa: BLE001
            log.warning("coins.llama.fi: %s", e)
            continue
        for k, v in (j.get("coins") or {}).items():
            if v.get("symbol"):
                found[k.lower()] = str(v["symbol"])
    resolved = 0
    for r in recs:
        prefix = LLAMA_CHAIN_KEYS.get(r["chain"], r["chain"].lower().replace(" ", ""))
        syms = []
        for t in r.pop("rtRaw"):
            if ADDRESS_RE.match(t):
                s = found.get(f"{prefix}:{t}".lower())
            else:
                s = t if len(t) <= 12 else None
            if s and s not in syms:
                syms.append(s)
        r["rt"] = syms
        resolved += bool(syms)
    return {"status": "ok", "count": resolved}


def fetch_hlp(http: Http) -> dict | None:
    d = http.post(HL_INFO, {"type": "vaultDetails", "vaultAddress": HLP_ADDR})
    apr = num(d.get("apr"))
    tvl = None
    for row in d.get("portfolio") or []:
        if row and row[0] == "day":
            hist = (row[1] or {}).get("accountValueHistory") or []
            if hist:
                tvl = num(hist[-1][1])
    if apr is None or not tvl:
        return None
    pct = apr * 100 if abs(apr) <= 3 else apr
    prot = S.protocol_info("hyperliquid-hlp")
    pr = prot["pr"]
    rec = {
        "id": "hyperliquid-hlp", "src": "hl", "kind": "stable", "quote": None, "assets": [], "chain": "Hyperliquid L1",
        "proto": pr["id"], "pn": pr["name"], "sym": "USDC", "meta": "HLP", "keytoks": ["USDC"], "fee": None,
        "tvl": tvl, "apy": pct, "base": pct, "rew": None, "m30": None, "v24": None, "v1d": None, "v30": None,
        "vdays": None, "vh": None, "age": None, "rt": [], "pt": prot["pt"], "at": 1, "ct": S.chain_tier("Hyperliquid L1"),
        "cat": pr["cat"], "outlier": False, "url": pr["url"], "purl": pr["url"],
        "_flags": ["negative"] if pct < 0 else [],
    }
    return finish(rec, pr)


# ---------------------------------------------------------------- GeckoTerminal

def resolve_networks(http: Http, cfg: dict) -> list[tuple[str, str]]:
    known = {}
    try:
        for page in range(1, 8):
            rows = http.gt("/networks", {"page": page}).get("data") or []
            if not rows:
                break
            for r in rows:
                known[r.get("id")] = str((r.get("attributes") or {}).get("name") or "")
    except Exception as e:  # noqa: BLE001
        log.warning("Список сетей GeckoTerminal не получен (%s), беру id из config.json", e)
    out = []
    for n in cfg["networks"]:
        gid = n.get("gt")
        if known and gid not in known:
            m = (n.get("match") or n["chain"]).lower()
            cands = [k for k, name in known.items() if k and (k.lower() == m or m in name.lower())]
            gid = cands[0] if cands else None
        if gid:
            out.append((n["chain"], gid))
        else:
            log.warning("Сеть %s не найдена в GeckoTerminal — пропускаю", n["chain"])
    return out


def gt_record(d: dict, inc: dict, chain: str, net: str, clf: S.Classifier, cfg: dict) -> dict | None:
    a, rel = d.get("attributes") or {}, d.get("relationships") or {}
    tvl, v24 = num(a.get("reserve_in_usd")), num((a.get("volume_usd") or {}).get("h24"))
    if tvl is None or tvl < cfg["min_tvl_dex"] or v24 is None:
        return None

    def tok(key):
        tid = ((rel.get(key) or {}).get("data") or {}).get("id")
        return (inc.get(tid) or {}).get("attributes") or {}

    bt, qt = tok("base_token"), tok("quote_token")
    toks = [clf.token(t.get("symbol"), chain, t.get("coingecko_coin_id"), t.get("address"), check_cg=True) for t in (bt, qt)]
    if any(t is None for t in toks):
        return None
    info = S.Classifier.combine(toks)
    if not info or info["kind"] not in ("pair", "stable"):
        return None
    dex_id = ((rel.get("dex") or {}).get("data") or {}).get("id") or ""
    name = str(a.get("name") or "")
    prot = S.protocol_info(dex_id, name)
    pr = prot["pr"]
    fee = S.parse_fee(name) or (pr or {}).get("fee_default")
    if not fee:
        return None  # без уровня комиссии доход по формуле таблицы не посчитать
    addr = a.get("address") or str(d.get("id", "")).split("_", 1)[-1]
    age = None
    try:
        created = datetime.fromisoformat(str(a.get("pool_created_at")).replace("Z", "+00:00"))
        age = max(0, (datetime.now(timezone.utc) - created).days)
    except ValueError:
        pass
    return {
        "id": f"gt:{net}:{addr}", "src": "gt", "net": net, "addr": addr, "kind": info["kind"], "quote": info["quote"],
        "assets": info["assets"], "chain": chain, "proto": pr["id"] if pr else dex_id,
        "pn": pr["name"] if pr else pretty(dex_id), "sym": f'{toks[0]["sym"]}-{toks[1]["sym"]}', "meta": "",
        "keytoks": [t.get("base", t["sym"]) for t in toks], "fee": fee, "tvl": tvl, "apy": None, "base": None,
        "rew": None, "m30": None, "v24": v24, "v1d": None, "v30": None, "vdays": None, "vh": None, "age": age, "rt": [],
        "pt": prot["pt"], "at": info["at"], "ct": S.chain_tier(chain), "cat": "dex", "outlier": False,
        "url": f"https://www.geckoterminal.com/{net}/pools/{addr}", "purl": pr.get("url") if pr else None,
        "_flags": info["flags"], "_pr": pr,
    }


def gt_daily_volumes(http: Http, net: str, addr: str) -> list[float]:
    j = http.gt(f"/networks/{net}/pools/{addr}/ohlcv/day", {"aggregate": 1, "limit": 31, "currency": "usd"})
    rows = ((j.get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    today = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    full = sorted((r for r in rows if r and len(r) >= 6 and int(r[0]) < today), key=lambda r: r[0])[-30:]
    return [num(r[5]) or 0.0 for r in full]


def collect_gt(http: Http, clf: S.Classifier, cfg: dict, deadline: float) -> tuple[list[dict], dict]:
    nets = resolve_networks(http, cfg)
    by_id: dict[str, dict] = {}
    stopped = False
    for chain, net in nets:
        for page in range(1, cfg["gt_pages_per_network"] + 1):
            if time.time() > deadline:
                stopped = True
                break
            try:
                j = http.gt(f"/networks/{net}/pools",
                            {"page": page, "sort": "h24_volume_usd_desc", "include": "base_token,quote_token,dex"})
            except Exception as e:  # noqa: BLE001
                log.warning("GeckoTerminal %s, стр. %s: %s", net, page, e)
                break
            rows = j.get("data") or []
            if not rows:
                break
            inc = {i.get("id"): i for i in (j.get("included") or [])}
            for d in rows:
                rec = gt_record(d, inc, chain, net, clf, cfg)
                if rec:
                    by_id[rec["id"]] = rec
    recs = list(by_id.values())
    log.info("GeckoTerminal: %d подходящих пулов в %d сетях, отказов по лимиту: %d", len(recs), len(nets), http.rate_limited)

    # Дневной объём за 30 дней — отдельный запрос на пул, поэтому только для самых интересных
    n = cfg["ohlcv_pools"]
    top_vol = sorted(recs, key=lambda r: r["v24"], reverse=True)[: n // 2]
    top_apr = sorted(recs, key=lambda r: r["v24"] * r["fee"] / r["tvl"], reverse=True)
    pick = list({r["id"]: r for r in top_vol + top_apr}.values())[:n]
    done = 0
    for i, r in enumerate(pick, 1):
        if time.time() > deadline:
            log.warning("Бюджет времени исчерпан: объём за 30 дней собран для %d из %d пулов, у остальных — за 24 часа",
                        done, len(pick))
            stopped = True
            break
        if i % 25 == 0:
            log.info("Объём за 30 дней: %d из %d пулов (отказов по лимиту: %d)", i, len(pick), http.rate_limited)
        try:
            vols = gt_daily_volumes(http, r["net"], r["addr"])
        except Exception as e:  # noqa: BLE001
            log.warning("OHLCV %s: %s", r["id"], e)
            continue
        if vols:
            r["vh"] = [round(v) for v in vols]
            r["vdays"] = len(vols)
            r["v30"] = sum(vols)
            done += 1

    out = []
    for r in recs:
        r["v1d"] = r["v30"] / r["vdays"] if r.get("v30") is not None and r["vdays"] else r["v24"]
        r["apy"] = r["v1d"] * r["fee"] * 365 / r["tvl"] * 100  # доходность пула при нулевом взносе
        r["base"] = r["apy"]
        r["outlier"] = r["apy"] > 1000 or r["v1d"] / r["tvl"] > 100
        pr = r.pop("_pr")
        out.append(finish(r, pr))
    return out, {"status": "ok" if out else "empty", "count": len(out), "with30d": done,
                 "networks": [c for c, _ in nets], "partial": stopped, "rateLimited": http.rate_limited}


# ---------------------------------------------------------------- сборка

ROUND = {"tvl": 0, "v24": 0, "v1d": 0, "v30": 0, "apy": 4, "base": 4, "rew": 4, "m30": 4}


def compact(rec: dict) -> dict:
    out = {}
    for k, v in rec.items():
        if k.startswith("_") or k in ("keytoks", "addr") or v is None or v == [] or v == "" or v is False:
            continue
        if k in ROUND and isinstance(v, float):
            v = round(v, ROUND[k]) if ROUND[k] else round(v)
        out[k] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Собирает webapp/data.json для Mini App")
    ap.add_argument("--out", default=str(HERE.parent / "webapp" / "data.json"))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--skip-gt", action="store_true", help="без GeckoTerminal (быстрая проверка)")
    ap.add_argument("--ohlcv", type=int, help="сколько пулов дополнить объёмом за 30 дней")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.ohlcv is not None:
        cfg["ohlcv_pools"] = args.ohlcv
    started = time.time()
    http = Http(cfg["gt_requests_per_minute"])
    sources: dict[str, dict] = {}

    universe, sources["coingecko"] = build_universe(http, cfg["universe_size"])
    clf = S.Classifier(universe)
    log.info("Топ-%d: %s", len(universe), ", ".join(u["symbol"] for u in universe))

    pools: list[dict] = []
    try:
        llama = collect_llama(http, clf, cfg)
        sources["defillama"] = {"status": "ok", "count": len(llama)}
        sources["rewards"] = resolve_reward_symbols(http, [r for r in llama if r.get("rew")])
        for r in llama:
            r.pop("rtRaw", None)
        pools += llama
    except Exception as e:  # noqa: BLE001
        log.error("DefiLlama: %s", e)
        sources["defillama"] = {"status": "error", "note": str(e)[:200]}

    try:
        hlp = fetch_hlp(http)
        if hlp and not any(p["proto"] == "hyperliquid-hlp" for p in pools):
            pools.append(hlp)
        sources["hyperliquid"] = {"status": "ok" if hlp else "empty"}
    except Exception as e:  # noqa: BLE001
        sources["hyperliquid"] = {"status": "error", "note": str(e)[:200]}

    if not args.skip_gt:
        try:
            budget = cfg.get("budget_minutes", 20) * 60
            gt, sources["geckoterminal"] = collect_gt(http, clf, cfg, started + budget)
            keys = {dedupe_key(r) for r in gt}
            for r in pools:  # тот же пул из DefiLlama прячем в «Парах», но оставляем в «Наградах»
                if r["src"] == "llama" and r["cat"] == "dex" and dedupe_key(r) in keys:
                    r["dup"] = True
            pools += gt
        except Exception as e:  # noqa: BLE001
            log.error("GeckoTerminal: %s", e)
            sources["geckoterminal"] = {"status": "error", "note": str(e)[:200]}

    if not pools:
        log.error("Ни один источник не дал данных — data.json не перезаписан")
        return 2
    pools.sort(key=lambda r: r["tvl"], reverse=True)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tiersVersion": S.tiers()["version"], "capitalDefault": CAPITAL_DEFAULT,
        "sources": sources, "universe": universe, "pools": [compact(p) for p in pools],
    }
    out = Path(args.out)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(out)
    log.info("Готово: %d пулов, %d запросов, %.0f с, %s (%.0f КБ)", len(pools), http.calls,
             time.time() - started, out, out.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
