"""Бот Yield Ladder (@yieldladder_bot) для Mini App из репозитория defiapp.

Переменные окружения:
  BOT_TOKEN   — токен от @BotFather
  WEBAPP_URL  — HTTPS-адрес опубликованной папки webapp/ (например, https://ВАШ-ЛОГИН.github.io/defiapp/)
  DATA_PATH   — необязательно: локальный путь к data.json, если сборщик работает на этом же сервере

Команды: /start, /pairs [МОНЕТА], /stables, /rewards, /capital СУММА, /tiers.
Расчёт тот же, что в приложении и в таблице: доля в пуле, доход в сутки, доход в месяц, APR.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import math
import os
import time
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
                           MenuButtonWebApp, Message, WebAppInfo)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/") + "/"
DATA_PATH = os.environ.get("DATA_PATH")
STATE_PATH = Path(os.environ.get("BOT_STATE", Path(__file__).with_name("bot_state.json")))
CACHE_TTL = 10 * 60
CAPITAL_DEFAULT = 6000
MIN_TVL = 1e5
RISK_MULT = {1: 1.0, 2: 0.75, 3: 0.5}
APY_CAP = {"stable": 80, "pair": 300, "rewards": 300}

log = logging.getLogger("yield-ladder-bot")
dp = Dispatcher()
_cache: dict = {"ts": 0.0, "data": None}
_lock = asyncio.Lock()


# ---------------------------------------------------------------- данные и расчёт

async def get_data() -> dict:
    async with _lock:
        if _cache["data"] and time.time() - _cache["ts"] < CACHE_TTL:
            return _cache["data"]
        if DATA_PATH:
            data = json.loads(Path(DATA_PATH).read_text(encoding="utf-8"))
        else:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
                async with s.get(WEBAPP_URL + "data.json", params={"t": int(time.time() // 300)}) as r:
                    r.raise_for_status()
                    data = await r.json(content_type=None)
        _cache.update(ts=time.time(), data=data)
        return data


def personal(p: dict, capital: float) -> dict:
    """Те же формулы, что в таблице и в webapp/core.js."""
    share = capital / (p["tvl"] + capital)
    if p.get("fee") is not None and p.get("v1d") is not None:
        day = p["v1d"] * p["fee"] * share
        apr = day * 365 / capital * 100
    else:
        apr = p.get("apy") or 0.0
        day = capital * apr / 100 / 365
    return {"share": share * 100, "day": day, "month": day * 30, "apr": apr,
            "month_rew": capital * (p.get("rew") or 0) / 100 / 365 * 30}


def risk_adjusted(p: dict, m: dict) -> float:
    if p.get("fee") is not None and p.get("v1d") is not None:
        y = m["apr"]
    else:
        y = p["base"] + 0.5 * (p.get("rew") or 0) if p.get("base") is not None else (p.get("apy") or 0) * 0.75
        if p.get("m30") and p["m30"] > 0:
            y = min(y, p["m30"] * 1.5 + 0.5)
    liq = min(1.0, max(0.6, 0.7 + 0.1 * math.log10(max(p["tvl"], 1) / 1e6)))
    return y * RISK_MULT[p["tier"]] * liq


def select(data: dict, view: str, asset: str | None, capital: float) -> dict[int, list[tuple[dict, dict]]]:
    rows = []
    for p in data["pools"]:
        if p["tvl"] < MIN_TVL or p.get("outlier"):
            continue
        if view == "pairs" and (p["kind"] != "pair" or p.get("dup") or (p.get("apy") or 0) > APY_CAP["pair"]):
            continue
        if view == "stables" and (p["kind"] != "stable" or p.get("dup") or (p.get("apy") or 0) > APY_CAP["stable"]):
            continue
        if view == "rewards" and not (p.get("rew") or 0) > 0:
            continue
        if asset and asset not in (p.get("assets") or []):
            continue
        m = personal(p, capital)
        rows.append((risk_adjusted(p, m), p, m))
    best: dict[int, list] = {1: [], 2: [], 3: []}
    for _, p, m in sorted(rows, key=lambda r: r[0], reverse=True):
        if len(best[p["tier"]]) < 3:
            best[p["tier"]].append((p, m))
    return best


# ---------------------------------------------------------------- состояние пользователей

def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_state = _load_state()


def get_capital(uid: int) -> float:
    return float(_state.get(str(uid), {}).get("capital", CAPITAL_DEFAULT))


def set_capital(uid: int, value: float) -> None:
    _state.setdefault(str(uid), {})["capital"] = value
    try:
        STATE_PATH.write_text(json.dumps(_state), encoding="utf-8")
    except OSError as e:
        log.warning("Не удалось сохранить капитал: %s", e)


# ---------------------------------------------------------------- форматирование

def money(v: float) -> str:
    return "$" + (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}").replace(",", " ").replace(".", ",")


def pct(v: float) -> str:
    return (f"{v:.2f}" if abs(v) < 1000 else f"{v:.0f}").replace(".", ",") + "%"


def share_txt(v: float) -> str:
    return "<0,01%" if 0 < v < 0.01 else pct(v)


def usd_short(v: float) -> str:
    if v >= 1e9:
        return "$" + f"{v / 1e9:.1f}".replace(".", ",") + " млрд"
    if v >= 1e6:
        return "$" + f"{v / 1e6:.1f}".replace(".", ",") + " млн"
    return "$" + f"{v / 1e3:.0f}" + " тыс"


def app_keyboard(text: str = "Открыть приложение") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=WEBAPP_URL))]])


def summary(data: dict, view: str, asset: str | None, capital: float) -> str:
    titles = {"pairs": "Пулы" + (f" с {asset}" if asset else " топ-30 монет"), "stables": "Стейблкоины",
              "rewards": "Награды токенами за депозит" + (f" ({asset})" if asset else "")}
    names = {1: "T1 — низкий риск", 2: "T2 — средний риск", 3: "T3 — высокий риск"}
    best = select(data, view, asset, capital)
    lines = [f"<b>{titles[view]}: лучшее на каждом уровне риска</b>",
             f"Капитал {money(capital)}, TVL от $100 тыс, сортировка с поправкой на риск.", ""]
    for t in (1, 2, 3):
        lines.append(f"<b>{names[t]}</b>")
        if not best[t]:
            lines.append("нет подходящих пулов")
        for p, m in best[t]:
            fee = f", {p['fee'] * 100:g}%".replace(".", ",") if p.get("fee") is not None else ""
            lines.append(f"{html.escape(p['pn'])} {html.escape(p['sym'])}{fee}, {html.escape(p['chain'])}, TVL {usd_short(p['tvl'])}")
            lines.append(f"   доля {share_txt(m['share'])} · {money(m['day'])}/сут · <b>{money(m['month'])}/мес</b> · APR <b>{pct(m['apr'])}</b>")
            if view == "rewards" and p.get("rew"):
                toks = ", ".join(p.get("rt") or []) or "токены проекта"
                lines.append(f"   награды {html.escape(toks)}: {pct(p['rew'])}, {money(m['month_rew'])}/мес")
        lines.append("")
    if view != "stables":
        lines.append("APR не учитывает непостоянные потери при движении цены.")
    lines.append("Не инвестиционная рекомендация.")
    return "\n".join(lines)


# ---------------------------------------------------------------- команды

@dp.message(CommandStart())
async def cmd_start(m: Message) -> None:
    await m.answer(
        "<b>Yield Ladder</b> — доходности DeFi с оценкой риска T1–T3: пулы топ-30 монет, стейблкоины и депозиты с наградами токенами. "
        "Для каждого пула — доля, доход в сутки и в месяц и APR на ваш капитал.\n\n"
        f"Сейчас капитал {money(get_capital(m.from_user.id))}. Изменить: /capital 10000\n"
        "Сводки: /pairs, /pairs SOL, /stables, /rewards",
        reply_markup=app_keyboard(),
    )


@dp.message(Command("capital"))
async def cmd_capital(m: Message, command: CommandObject) -> None:
    raw = (command.args or "").replace(" ", "").replace(",", ".").lstrip("$")
    try:
        value = float(raw)
        if not 10 <= value <= 1e9:
            raise ValueError
    except ValueError:
        await m.answer(f"Капитал сейчас {money(get_capital(m.from_user.id))}. Чтобы изменить, пришлите, например: /capital 6000")
        return
    set_capital(m.from_user.id, value)
    await m.answer(f"Капитал {money(value)} сохранён — сводки будут считаться на эту сумму. "
                   "В приложении сумма задаётся отдельно, в поле «Капитал».")


async def send_summary(m: Message, view: str, args: str | None) -> None:
    asset = (args or "").strip().upper() or None
    try:
        data = await get_data()
    except Exception as e:  # noqa: BLE001 — сеть, формат
        log.exception("Ошибка загрузки data.json")
        await m.answer(f"Не удалось получить данные: {html.escape(str(e))}. Попробуйте через минуту.")
        return
    if asset and view != "stables":
        known = {a for p in data["pools"] for a in (p.get("assets") or [])}
        if asset not in known:
            sample = ", ".join(u["symbol"] for u in data.get("universe", [])[:12])
            await m.answer(f"Пулов с {html.escape(asset)} нет в выгрузке. Попробуйте одну из монет топ-30: {sample}…")
            return
    await m.answer(summary(data, view, asset, get_capital(m.from_user.id)), reply_markup=app_keyboard("Все пулы и фильтры"))


@dp.message(Command("pairs"))
async def cmd_pairs(m: Message, command: CommandObject) -> None:
    await send_summary(m, "pairs", command.args)


@dp.message(Command("stables"))
async def cmd_stables(m: Message) -> None:
    await send_summary(m, "stables", None)


@dp.message(Command("rewards"))
async def cmd_rewards(m: Message, command: CommandObject) -> None:
    await send_summary(m, "rewards", command.args)


@dp.message(Command("tiers"))
async def cmd_tiers(m: Message) -> None:
    await m.answer(
        "<b>Как оценивается риск</b>\n"
        "Итоговый тир пула — худший из трёх: протокол, активы в пуле, сеть.\n\n"
        "<b>T1</b> — 2+ года без потерь из-за кода, крупный TVL, несколько аудитов (Aave V3, Compound V3, Uniswap, Curve, Sky).\n"
        "<b>T2</b> — меньше истории, кураторы или внешние стратегии, молодые сети (Morpho, Euler, GMX V2, HLP, Robinhood Chain).\n"
        "<b>T3</b> — недавние взломы, непроверенные токены и всё неоценённое.\n\n"
        "Формулы и полный список — во вкладке «Методика».",
        reply_markup=app_keyboard("Открыть методику"),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Открыть", web_app=WebAppInfo(url=WEBAPP_URL)))
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть приложение"),
        BotCommand(command="pairs", description="Пулы топ-30 монет, например /pairs ETH"),
        BotCommand(command="stables", description="Куда положить стейблкоины"),
        BotCommand(command="rewards", description="Где платят токенами за депозит"),
        BotCommand(command="capital", description="Капитал для расчёта, например /capital 6000"),
        BotCommand(command="tiers", description="Как оценивается риск"),
    ])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
