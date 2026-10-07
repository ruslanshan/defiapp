"""Классификация пулов и риск-тиры для сборщика.

Читает webapp/tiers.js (JSON между маркерами JSON-START / JSON-END) — тиры правятся в одном месте.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIERS_PATH = ROOT / "webapp" / "tiers.js"
ZERO_ADDR = "0x0000000000000000000000000000000000000000"
WRAPPERS = {"GLV", "GM", "LP"}
FEE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@lru_cache(maxsize=1)
def tiers() -> dict:
    text = TIERS_PATH.read_text(encoding="utf-8")
    m = re.search(r"/\*JSON-START\*/(.*?)/\*JSON-END\*/", text, re.S)
    if not m:
        raise RuntimeError(f"В {TIERS_PATH} нет маркеров JSON-START/JSON-END")
    return json.loads(m.group(1))


def split_symbol(sym: str) -> list[str]:
    parts = re.split(r"[-/\s]+", str(sym or "").upper())
    return [p for p in (s.strip() for s in parts) if p and p not in WRAPPERS and not FEE_RE.fullmatch(p)]


def parse_fee(text: str | None) -> float | None:
    """'WETH / USDC 0.05%' → 0.0005"""
    found = FEE_RE.findall(str(text or ""))
    if not found:
        return None
    pct = float(found[-1])
    return pct / 100 if 0 < pct <= 10 else None


@lru_cache(maxsize=4096)
def _proto_idx(slug: str):
    best, best_len = None, -1
    for i, pr in enumerate(tiers()["protocols"]):
        for a in pr["aliases"]:
            if slug == a:
                return i
            if slug.startswith(a + "-") and len(a) > best_len:
                best, best_len = i, len(a)
    return best


def find_protocol(slug: str):
    """slug DefiLlama ('uniswap-v3') или id DEX GeckoTerminal ('uniswap_v3_arbitrum')."""
    i = _proto_idx(str(slug or "").lower().replace("_", "-"))
    return None if i is None else tiers()["protocols"][i]


def is_excluded_coin(sym: str, name: str) -> bool:
    a = tiers()["assets"]
    if sym in a["stable"] or sym in a["families"] or sym in a["exclude_symbols"]:
        return True
    if sym.endswith("USD") or re.search(r"\b(usd|dollar|treasur|gold)", name, re.I):
        return True
    return bool(re.match(r"(wrapped|staked|bridged) ", name, re.I))


class Classifier:
    """Определяет, что за токен: стейблкоин, актив из топ-30 (или его обёртка), токенизированная акция."""

    def __init__(self, universe: list[dict]):
        a = tiers()["assets"]
        self.stable = a["stable"]
        self.stable_keys = sorted(self.stable, key=len, reverse=True)
        self.families = a["families"]
        self.vtiers = a["volatile_tiers"]
        self.alt_tier = a["alt_default_tier"]
        self.extras = {e["symbol"]: e for e in a.get("extra_assets", [])}
        self.universe = {u["symbol"] for u in universe}
        self.names = {u["symbol"]: u.get("name", "") for u in universe}
        self.cg_ids = {u["id"] for u in universe if u.get("id")}

    def stable_tier(self, tok: str):
        if tok in self.stable:
            return self.stable[tok]
        # обёртки хранилищ: STEAKUSDC, GTUSDC, SYRUPUSDC — стейбл в конце символа
        for k in self.stable_keys:
            if len(k) >= 3 and tok.endswith(k):
                return self.stable[k]
        return None

    def _cg_matches(self, cg_id: str, sym: str, base: str) -> bool:
        cg = cg_id.lower()
        if cg in self.cg_ids:
            return True
        name = self.names.get(base, "").lower().replace(" ", "-")
        return any(x and x in cg for x in (sym.lower(), base.lower(), name))

    def token(self, sym: str, chain: str, cg_id: str | None = None, address: str | None = None,
              check_cg: bool = False) -> dict | None:
        s = str(sym or "").upper().strip()
        if not s:
            return None
        if s in self.stable:
            return {"t": "stable", "sym": s, "tier": self.stable[s]}
        plain = re.sub(r"\.E$", "", s)
        base = self.families.get(plain, plain)
        if base in self.universe:
            tier = self.vtiers.get(plain) or self.vtiers.get(base) or self.alt_tier
            verified = True
            if check_cg:
                if cg_id:
                    if not self._cg_matches(cg_id, plain, base):
                        return None  # одноимённый, но другой токен
                elif (address or "").lower() != ZERO_ADDR:
                    verified = False
            return {"t": "asset", "sym": plain, "base": base, "tier": tier if verified else max(tier, 3),
                    "verified": verified}
        extra = self.extras.get(base)
        if extra and chain in extra.get("chains", []):
            return {"t": "asset", "sym": plain, "base": base, "tier": extra.get("tier", 2), "verified": True, "stock": True}
        st = self.stable_tier(s)
        if st is not None:
            return {"t": "stable", "sym": s, "tier": st}
        return None

    @staticmethod
    def combine(toks: list[dict]) -> dict | None:
        """Тип пула по классифицированным токенам."""
        flags = []
        if any(not t.get("verified", True) for t in toks):
            flags.append("unverified")
        if any(t.get("stock") for t in toks):
            flags.append("stock")
        tier = max(t["tier"] for t in toks)
        if len(toks) == 1:
            t = toks[0]
            if t["t"] == "stable":
                return {"kind": "stable", "quote": None, "assets": [], "at": tier, "flags": flags}
            return {"kind": "single", "quote": None, "assets": [t["base"]], "at": tier, "flags": flags}
        if len(toks) != 2:
            return None
        a, b = toks
        if a["t"] == "stable" and b["t"] == "stable":
            return {"kind": "stable", "quote": None, "assets": [], "at": tier, "flags": flags}
        if a["t"] == "stable" or b["t"] == "stable":
            asset = b if a["t"] == "stable" else a
            return {"kind": "pair", "quote": "stable", "assets": [asset["base"]], "at": tier, "flags": flags}
        if a["base"] == b["base"]:
            return None  # ETH-stETH и подобное — не то, что ищем
        quote = "major" if {a["base"], b["base"]} & {"ETH", "BTC"} else "alt"
        return {"kind": "pair", "quote": quote, "assets": [a["base"], b["base"]], "at": tier, "flags": flags}


def protocol_info(slug: str, symbol: str = "", meta: str = "") -> dict:
    pr = find_protocol(slug)
    pt = pr["tier"] if pr else 3
    if pr and pr.get("rules"):
        hay = f"{symbol} {meta}".lower()
        for r in pr["rules"]:
            if re.search(r["match"], hay, re.I):
                pt = r["tier"]
                break
    return {"pr": pr, "pt": pt}


def chain_tier(chain: str) -> int:
    return tiers()["chains"].get(chain, 3)
