/*
 * Классификация риска протоколов, сетей и активов.
 * Читают её и приложение (вкладка «Методика»), и сборщик collector/ — тиры правятся только здесь.
 *
 * Редактируйте JSON между маркерами JSON-START / JSON-END:
 * двойные кавычки, без висячих запятых и комментариев — сборщик читает его как JSON.
 *
 * protocols.aliases — slug-и DefiLlama и id DEX в GeckoTerminal (подчёркивания читаются как дефисы).
 *   Совпадение точное или по префиксу "alias-"; самый длинный alias побеждает (gmx-v1 отделяется от gmx).
 * protocols.rules   — переопределение тира по названию хранилища (regex по symbol + poolMeta).
 * protocols.fee_default — комиссия для DEX, у которых её нет в названии пула (Uniswap V2: 0.3%).
 * assets.extra_assets — монеты вне топ-30, которые тоже показывать (например, токенизированные акции),
 *   только в перечисленных сетях — так одноимённые подделки в других сетях не попадут в выборку.
 */
(typeof window !== "undefined" ? window : globalThis).TIERS =
/*JSON-START*/
{
  "version": "2026-10-07c",
  "protocols": [
    {
      "id": "aave-v3",
      "name": "Aave V3",
      "tier": 1,
      "cat": "lending",
      "since": "2022",
      "aliases": [
        "aave-v3"
      ],
      "url": "https://app.aave.com",
      "why": "Крупнейший лендинг (Aave работает с 2020), десятки аудитов, код V3 не взламывался. Урок 04.2026: после взлома моста Kelp атакующий занял WETH под необеспеченный rsETH, безнадёжный долг составил $124–230 млн, рынки WETH были заморожены почти две недели; дыру закрыла коалиция DeFi United. Риск — в принятых залогах, а не в коде."
    },
    {
      "id": "aave-v4",
      "name": "Aave V4",
      "tier": 2,
      "cat": "lending",
      "since": "2026",
      "aliases": [
        "aave-v4"
      ],
      "url": "https://pro.aave.com",
      "why": "Запущен 30.03.2026, новая архитектура Hub & Spoke и почти год проверки безопасности, но короткая история в работе и осторожные лимиты. Кандидат в T1 после 12–18 месяцев без инцидентов."
    },
    {
      "id": "aave-v2",
      "name": "Aave V2",
      "tier": 2,
      "cat": "lending",
      "since": "2020",
      "aliases": [
        "aave-v2"
      ],
      "url": "https://app.aave.com",
      "why": "Устаревшая версия, рынки сворачиваются и теряют ликвидность. Для новых депозитов используйте V3."
    },
    {
      "id": "compound-v3",
      "name": "Compound V3",
      "tier": 1,
      "cat": "lending",
      "since": "2022",
      "aliases": [
        "compound-v3"
      ],
      "url": "https://app.compound.finance",
      "why": "Comet: в каждом рынке один заимствуемый актив, залог не выдаётся в долг. Долгая история без взломов кода; в 04.2026 быстро остановил займы под rsETH."
    },
    {
      "id": "compound-v2",
      "name": "Compound V2",
      "tier": 2,
      "cat": "lending",
      "since": "2019",
      "aliases": [
        "compound-v2",
        "compound"
      ],
      "url": "https://app.compound.finance",
      "why": "Устаревшая версия с низкой ликвидностью. Для новых депозитов используйте V3."
    },
    {
      "id": "morpho",
      "name": "Morpho",
      "tier": 2,
      "cat": "lending",
      "since": "2024",
      "aliases": [
        "morpho-v1",
        "morpho-blue",
        "morpho"
      ],
      "url": "https://app.morpho.org",
      "flags": [
        "curator"
      ],
      "rules": [
        {
          "match": "steakhouse|^steak|gauntlet|^gt[a-z]",
          "tier": 1,
          "note": "Хранилище известного куратора (Steakhouse или Gauntlet) — поднято до T1. Всё равно проверьте список залогов в интерфейсе Morpho."
        }
      ],
      "why": "Ядро Morpho Blue неизменяемое, рынки изолированы: при взломе Kelp в 04.2026 пострадали лишь два рынка (~$1 млн), остальное не задето. Риск хранилища задаёт куратор: в 11.2025 хранилища MEV Capital получили потери 3,5–12% из-за обвала xUSD и deUSD. По умолчанию T2.",
      "exit": {
        "type": "pool",
        "text": "Вывод из хранилища ограничен свободной ликвидностью его рынков; куратор может перераспределять её между рынками."
      }
    },
    {
      "id": "sparklend",
      "name": "SparkLend",
      "tier": 1,
      "cat": "lending",
      "since": "2023",
      "aliases": [
        "sparklend",
        "spark-lend"
      ],
      "url": "https://app.spark.fi",
      "why": "Форк Aave V3 в экосистеме Sky с глубокой ликвидностью USDS и DAI. Заморозил rsETH в первые часы после взлома Kelp."
    },
    {
      "id": "spark-savings",
      "name": "Spark Savings",
      "tier": 1,
      "cat": "savings",
      "since": "2024",
      "aliases": [
        "spark-savings"
      ],
      "url": "https://app.spark.fi",
      "why": "Обёртки сбережений Sky (sUSDS, sUSDC) через интерфейс Spark: доход — ставка Sky Savings Rate.",
      "exit": {
        "type": "instant",
        "text": "Вывод из сбережений Spark мгновенный."
      }
    },
    {
      "id": "sky",
      "name": "Sky (sUSDS, sDAI)",
      "tier": 1,
      "cat": "savings",
      "since": "2017",
      "aliases": [
        "sky-lending",
        "sky",
        "makerdao",
        "maker"
      ],
      "url": "https://sky.money",
      "why": "Maker/Sky с 2017 года. Ставку сбережений (SSR/DSR) задаёт управление; обеспечение — крипта и реальные активы (казначейские облигации США). У вкладчика нет ликвидационного риска.",
      "exit": {
        "type": "instant",
        "text": "Вывод из сбережений Sky (sUSDS, sDAI) мгновенный."
      }
    },
    {
      "id": "uniswap-v3",
      "name": "Uniswap V3",
      "tier": 1,
      "cat": "dex",
      "since": "2021",
      "aliases": [
        "uniswap-v3"
      ],
      "url": "https://app.uniswap.org",
      "flags": [
        "il",
        "range"
      ],
      "why": "Неизменяемые контракты, глубочайшая ликвидность, ни одного взлома ядра. Риск LP — непостоянные потери и выход цены за диапазон, а не код."
    },
    {
      "id": "uniswap-v4",
      "name": "Uniswap V4",
      "tier": 1,
      "cat": "dex",
      "since": "2025",
      "aliases": [
        "uniswap-v4"
      ],
      "url": "https://app.uniswap.org",
      "flags": [
        "il",
        "range",
        "hooks"
      ],
      "why": "Неизменяемое ядро-синглтон, множество аудитов и крупный баг-баунти. Хуки — произвольный код автора пула, их риск оценивайте отдельно."
    },
    {
      "id": "uniswap-v2",
      "name": "Uniswap V2",
      "tier": 1,
      "cat": "dex",
      "since": "2020",
      "aliases": [
        "uniswap-v2",
        "uniswap"
      ],
      "url": "https://app.uniswap.org",
      "flags": [
        "il"
      ],
      "why": "Простейший AMM с 2020 года, код не менялся и не взламывался. Ликвидность распределена по всей кривой — доход на капитал ниже, чем в V3.",
      "fee_default": 0.003
    },
    {
      "id": "curve",
      "name": "Curve",
      "tier": 1,
      "cat": "dex",
      "since": "2020",
      "aliases": [
        "curve-dex",
        "curve"
      ],
      "url": "https://curve.fi",
      "why": "Эталон стейбл-свопов с 2020 года. В 07.2023 баг компилятора Vyper задел несколько пулов; основные стейбл-пулы не пострадали."
    },
    {
      "id": "curve-llamalend",
      "name": "Curve LlamaLend",
      "tier": 2,
      "cat": "lending",
      "since": "2024",
      "aliases": [
        "curve-llamalend",
        "llamalend"
      ],
      "url": "https://curve.fi",
      "why": "Изолированные рынки на механике мягких ликвидаций crvUSD. Моложе основной Curve, ликвидность ниже."
    },
    {
      "id": "gmx-v2",
      "name": "GMX V2",
      "tier": 2,
      "cat": "perp",
      "since": "2023",
      "aliases": [
        "gmx-v2-perps",
        "gmx-v2",
        "gmx"
      ],
      "url": "https://app.gmx.io",
      "flags": [
        "counterparty"
      ],
      "why": "GM-пулы изолированы под каждую пару, GLV распределяет ликвидность между ними. В 07.2025 взломали старый GLP (V1, $42 млн, реентерабельность) — V2 не задет, пострадавшим всё компенсировали. LP-пулы — контрагент трейдеров и держат ~50% в ETH/BTC.",
      "exit": {
        "type": "instant",
        "text": "Вывод из GM-пула — ордер исполняется за минуты; при перекосе пула возможна повышенная комиссия."
      }
    },
    {
      "id": "gmx-v1",
      "name": "GMX V1 (GLP)",
      "tier": 3,
      "cat": "perp",
      "since": "2021",
      "aliases": [
        "gmx-v1",
        "gmx-v1-perps"
      ],
      "url": "https://app.gmx.io",
      "why": "В 07.2025 GLP взломан на $42 млн, версия свёрнута. Не размещайте средства."
    },
    {
      "id": "hyperliquid-hlp",
      "name": "Hyperliquid HLP",
      "tier": 2,
      "cat": "vault",
      "since": "2023",
      "aliases": [
        "hyperliquid-hlp",
        "hyperliquid"
      ],
      "url": "https://app.hyperliquid.xyz/vaults/0xdfc24b077bc1425ad1dea75bcb6f8158e10df303",
      "flags": [
        "counterparty",
        "lockup"
      ],
      "why": "HLP — хранилище маркет-мейкинга и ликвидаций на собственной L1 Hyperliquid (небольшой набор валидаторов, USDC заходит через мост на Arbitrum). Регулярно становится целью манипуляций: JELLY (03.2025), POPCAT (11.2025), FARTCOIN (04.2026, около −$1,5 млн). Доходность сильно скачет.",
      "exit": {
        "type": "lock",
        "days": 4,
        "text": "Каждый депозит в HLP заблокирован на 4 дня, потом вывод сразу."
      }
    },
    {
      "id": "fluid-lending",
      "name": "Fluid",
      "tier": 2,
      "cat": "lending",
      "since": "2024",
      "aliases": [
        "fluid-lending",
        "fluid-lite",
        "fluid"
      ],
      "url": "https://fluid.io",
      "why": "Команда Instadapp (с 2019), общий слой ликвидности для лендинга и DEX. Эффективен, но сложнее и моложе Aave."
    },
    {
      "id": "fluid-dex",
      "name": "Fluid DEX",
      "tier": 2,
      "cat": "dex",
      "since": "2024",
      "aliases": [
        "fluid-dex"
      ],
      "url": "https://fluid.io",
      "flags": [
        "il"
      ],
      "why": "DEX поверх слоя ликвидности Fluid: LP-позиция одновременно работает как залог. Сложная архитектура, недолгая история."
    },
    {
      "id": "euler",
      "name": "Euler V2",
      "tier": 2,
      "cat": "lending",
      "since": "2024",
      "aliases": [
        "euler-v2",
        "euler"
      ],
      "url": "https://app.euler.finance",
      "flags": [
        "curator"
      ],
      "why": "V1 взломали в 2023 ($197 млн, средства вернули). V2 с 2024 года — модульные хранилища с кураторами; в 11.2025 часть хранилищ потеряла средства из-за xUSD и deUSD.",
      "exit": {
        "type": "pool",
        "text": "Вывод из хранилища ограничен свободной ликвидностью его рынков."
      }
    },
    {
      "id": "pendle",
      "name": "Pendle",
      "tier": 2,
      "cat": "yield",
      "since": "2021",
      "aliases": [
        "pendle"
      ],
      "url": "https://app.pendle.finance",
      "why": "Токенизация доходности: PT даёт фиксированную ставку при удержании до погашения. Риск = риск базового актива + ценовой риск PT при досрочном выходе.",
      "exit": {
        "type": "market",
        "text": "PT до даты погашения продаётся по рыночной цене — возможен дисконт; в дату погашения выкуп 1:1."
      }
    },
    {
      "id": "aerodrome",
      "name": "Aerodrome",
      "tier": 2,
      "cat": "dex",
      "since": "2023",
      "aliases": [
        "aerodrome-slipstream",
        "aerodrome-v1",
        "aerodrome"
      ],
      "url": "https://aerodrome.finance",
      "flags": [
        "il",
        "emissions"
      ],
      "why": "Главный DEX сети Base (форк Velodrome). Основная часть APY — эмиссия AERO, её цена плавает."
    },
    {
      "id": "velodrome",
      "name": "Velodrome",
      "tier": 2,
      "cat": "dex",
      "since": "2022",
      "aliases": [
        "velodrome-v2",
        "velodrome-v3",
        "velodrome-slipstream",
        "velodrome"
      ],
      "url": "https://velodrome.finance",
      "flags": [
        "il",
        "emissions"
      ],
      "why": "Главный DEX Optimism. Основная часть APY — эмиссия VELO."
    },
    {
      "id": "pancakeswap",
      "name": "PancakeSwap",
      "tier": 2,
      "cat": "dex",
      "since": "2020",
      "aliases": [
        "pancakeswap-amm-v3",
        "pancakeswap-amm-v4",
        "pancakeswap-amm",
        "pancakeswap-v3",
        "pancakeswap-v2",
        "pancakeswap-infinity",
        "pancakeswap"
      ],
      "url": "https://pancakeswap.finance",
      "flags": [
        "il"
      ],
      "why": "Крупнейший DEX BNB Chain, V3 — форк Uniswap V3. Долгая история, но более централизованное управление."
    },
    {
      "id": "sushiswap",
      "name": "SushiSwap",
      "tier": 2,
      "cat": "dex",
      "since": "2020",
      "aliases": [
        "sushiswap-v3",
        "sushiswap",
        "sushi"
      ],
      "url": "https://www.sushi.com",
      "flags": [
        "il"
      ],
      "why": "Ветеран DeFi; в 2023 взломан RouteProcessor2 (средства пользователей с открытыми разрешениями). Ликвидность сокращается.",
      "fee_default": 0.003
    },
    {
      "id": "balancer-v3",
      "name": "Balancer V3",
      "tier": 2,
      "cat": "dex",
      "since": "2024",
      "aliases": [
        "balancer-v3"
      ],
      "url": "https://balancer.fi",
      "flags": [
        "il"
      ],
      "why": "Новая кодовая база, не затронутая взломом V2, но с короткой историей."
    },
    {
      "id": "balancer-v2",
      "name": "Balancer V2",
      "tier": 3,
      "cat": "dex",
      "since": "2021",
      "aliases": [
        "balancer-v2",
        "balancer"
      ],
      "url": "https://balancer.fi",
      "flags": [
        "il"
      ],
      "why": "В 11.2025 composable stable pools взломаны примерно на $128 млн из-за ошибки округления."
    },
    {
      "id": "convex",
      "name": "Convex",
      "tier": 2,
      "cat": "vault",
      "since": "2021",
      "aliases": [
        "convex-finance",
        "convex"
      ],
      "url": "https://www.convexfinance.com",
      "flags": [
        "emissions"
      ],
      "why": "Надстройка над Curve: риск Curve плюс собственные контракты. Часть дохода — токены CRV и CVX."
    },
    {
      "id": "yearn",
      "name": "Yearn",
      "tier": 2,
      "cat": "vault",
      "since": "2020",
      "aliases": [
        "yearn-finance",
        "yearn"
      ],
      "url": "https://yearn.fi",
      "why": "Агрегатор с 2020: риск стратегии плюс риски базовых протоколов. В конце 2025 взломан отдельный продукт yETH (~$9 млн), основные хранилища не задеты."
    },
    {
      "id": "beefy",
      "name": "Beefy",
      "tier": 2,
      "cat": "vault",
      "since": "2020",
      "aliases": [
        "beefy"
      ],
      "url": "https://app.beefy.com",
      "why": "Автокомпаундер: риск Beefy плюс риски всех протоколов внутри стратегии."
    },
    {
      "id": "ethena",
      "name": "Ethena (sUSDe)",
      "tier": 2,
      "cat": "savings",
      "since": "2024",
      "aliases": [
        "ethena-usde",
        "ethena"
      ],
      "url": "https://app.ethena.fi",
      "flags": [
        "basis"
      ],
      "why": "sUSDe зарабатывает на базисной торговле: фандинг перпетуалов плюс стейкинг ETH. Обеспечение частично хранится у кастодианов бирж; при отрицательном фандинге доход падает.",
      "exit": {
        "type": "cooldown",
        "days": 7,
        "text": "Вывод sUSDe в USDe — после кулдауна до 7 дней. Быстрее — только продажа sUSDe на DEX, возможен дисконт."
      }
    },
    {
      "id": "maple",
      "name": "Maple (syrupUSDC)",
      "tier": 2,
      "cat": "lending",
      "since": "2021",
      "aliases": [
        "maple"
      ],
      "url": "https://app.maple.finance",
      "flags": [
        "credit"
      ],
      "why": "Займы институционалам с неполным обеспечением: основной риск кредитный, а не смарт-контрактный.",
      "exit": {
        "type": "queue",
        "text": "Вывод через очередь: обычно быстро, но в стресс может занять дни — займы институционалам не отзываются мгновенно."
      }
    },
    {
      "id": "liquity-v2",
      "name": "Liquity V2",
      "tier": 2,
      "cat": "vault",
      "since": "2025",
      "aliases": [
        "liquity-v2"
      ],
      "url": "https://www.liquity.org",
      "why": "Неизменяемые контракты, стабилизационный пул BOLD. Вторая версия моложе и сложнее первой.",
      "exit": {
        "type": "instant",
        "text": "Вывод из стабилизационного пула в любой момент."
      }
    },
    {
      "id": "kamino",
      "name": "Kamino",
      "tier": 2,
      "cat": "lending",
      "since": "2022",
      "aliases": [
        "kamino-lend",
        "kamino-liquidity",
        "kamino"
      ],
      "url": "https://app.kamino.finance",
      "why": "Крупнейший лендинг Solana, много аудитов, без крупных взломов."
    },
    {
      "id": "jupiter",
      "name": "Jupiter",
      "tier": 2,
      "cat": "perp",
      "since": "2023",
      "aliases": [
        "jupiter-perps",
        "jupiter-lend",
        "jupiter"
      ],
      "url": "https://jup.ag",
      "flags": [
        "counterparty"
      ],
      "why": "JLP — мультиактивный пул перпетуалов Solana: доход от комиссий, контрагент трейдеров, экспозиция к SOL/ETH/BTC."
    },
    {
      "id": "orca",
      "name": "Orca",
      "tier": 2,
      "cat": "dex",
      "since": "2021",
      "aliases": [
        "orca-dex",
        "orca"
      ],
      "url": "https://www.orca.so",
      "flags": [
        "il",
        "range"
      ],
      "why": "DEX с концентрированной ликвидностью на Solana, долгая история."
    },
    {
      "id": "raydium",
      "name": "Raydium",
      "tier": 2,
      "cat": "dex",
      "since": "2021",
      "aliases": [
        "raydium-amm",
        "raydium"
      ],
      "url": "https://raydium.io",
      "flags": [
        "il"
      ],
      "why": "Крупный DEX Solana; в 2022 взлом из-за утечки ключа администратора пулов, компенсирован."
    },
    {
      "id": "venus",
      "name": "Venus",
      "tier": 3,
      "cat": "lending",
      "since": "2020",
      "aliases": [
        "venus-core-pool",
        "venus-isolated-pools",
        "venus"
      ],
      "url": "https://app.venus.io",
      "why": "Крупнейший лендинг BNB Chain, но серия инцидентов; последний — 03.2026 (~$3,7 млн, обход лимита предложения)."
    },
    {
      "id": "silo",
      "name": "Silo",
      "tier": 3,
      "cat": "lending",
      "since": "2022",
      "aliases": [
        "silo-v2",
        "silo-v1",
        "silo-finance",
        "silo"
      ],
      "url": "https://app.silo.finance",
      "why": "Изолированные рынки, но инциденты с неверной настройкой оракула; последний — 04.2026 (~$0,4 млн)."
    },
    {
      "id": "drift",
      "name": "Drift",
      "tier": 3,
      "cat": "perp",
      "since": "2021",
      "aliases": [
        "drift"
      ],
      "url": "https://www.drift.trade",
      "why": "В 04.2026 потерял около $285 млн через компрометацию административных ключей."
    },
    {
      "id": "radiant",
      "name": "Radiant",
      "tier": 3,
      "cat": "lending",
      "since": "2022",
      "aliases": [
        "radiant-v2",
        "radiant"
      ],
      "url": "https://app.radiant.capital",
      "why": "В 10.2024 потерял около $50 млн после взлома мультиподписи."
    },
    {
      "id": "resolv",
      "name": "Resolv",
      "tier": 3,
      "cat": "savings",
      "since": "2024",
      "aliases": [
        "resolv"
      ],
      "url": "https://resolv.xyz",
      "why": "В 2026 эксплойт минта: выпущено около 80 млн необеспеченных USR."
    }
  ],
  "chains": {
    "Ethereum": 1,
    "Arbitrum": 1,
    "Base": 1,
    "Optimism": 1,
    "OP Mainnet": 1,
    "Solana": 2,
    "BSC": 2,
    "Polygon": 2,
    "Avalanche": 2,
    "Gnosis": 2,
    "xDai": 2,
    "Linea": 2,
    "Scroll": 2,
    "Unichain": 2,
    "Sonic": 2,
    "Mantle": 2,
    "zkSync Era": 2,
    "Hyperliquid L1": 2,
    "Hyperliquid": 2,
    "Plasma": 2,
    "Katana": 2,
    "Berachain": 2,
    "Sui": 2,
    "Aptos": 2,
    "Tron": 2,
    "Celo": 2,
    "Robinhood": 2,
    "Robinhood Chain": 2
  },
  "assets": {
    "stable": {
      "USDC": 1,
      "USDT": 1,
      "DAI": 1,
      "USDS": 1,
      "SUSDS": 1,
      "SDAI": 1,
      "USDT0": 2,
      "USDC.E": 2,
      "USDCE": 2,
      "USDT.E": 2,
      "USDBC": 2,
      "PYUSD": 2,
      "USDE": 2,
      "SUSDE": 2,
      "GHO": 2,
      "SGHO": 2,
      "CRVUSD": 2,
      "SCRVUSD": 2,
      "FRAX": 2,
      "FRXUSD": 2,
      "SFRXUSD": 2,
      "LUSD": 2,
      "BOLD": 2,
      "SBOLD": 2,
      "RLUSD": 2,
      "USD1": 2,
      "FDUSD": 2,
      "DOLA": 2,
      "USDTB": 2,
      "USDG": 2,
      "USR": 3,
      "XUSD": 3,
      "DEUSD": 3,
      "SDEUSD": 3,
      "TUSD": 3,
      "USDX": 3
    },
    "families": {
      "WETH": "ETH",
      "STETH": "ETH",
      "WSTETH": "ETH",
      "WEETH": "ETH",
      "RETH": "ETH",
      "CBETH": "ETH",
      "EZETH": "ETH",
      "RSETH": "ETH",
      "WBETH": "ETH",
      "WBTC": "BTC",
      "CBBTC": "BTC",
      "TBTC": "BTC",
      "LBTC": "BTC",
      "BTCB": "BTC",
      "SOLVBTC": "BTC",
      "WBNB": "BNB",
      "WSOL": "SOL",
      "WAVAX": "AVAX",
      "WPOL": "POL",
      "WMATIC": "POL",
      "MATIC": "POL",
      "WHYPE": "HYPE",
      "WTRX": "TRX",
      "WXRP": "XRP",
      "WSUI": "SUI"
    },
    "volatile_tiers": {
      "ETH": 1,
      "WETH": 1,
      "STETH": 1,
      "WSTETH": 1,
      "RETH": 2,
      "CBETH": 2,
      "WEETH": 2,
      "WBETH": 2,
      "EZETH": 3,
      "RSETH": 3,
      "BTC": 1,
      "WBTC": 1,
      "CBBTC": 1,
      "TBTC": 2,
      "LBTC": 2,
      "BTCB": 2,
      "SOLVBTC": 3,
      "LINK": 1,
      "UNI": 1,
      "AAVE": 1
    },
    "alt_default_tier": 2,
    "extra_assets": [
      {
        "symbol": "NVDA",
        "name": "NVIDIA (токенизированная акция)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      },
      {
        "symbol": "SPCX",
        "name": "SpaceX (токенизированная акция)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      },
      {
        "symbol": "SPY",
        "name": "S&P 500 ETF (токен)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      },
      {
        "symbol": "AAPL",
        "name": "Apple (токенизированная акция)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      },
      {
        "symbol": "TSLA",
        "name": "Tesla (токенизированная акция)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      },
      {
        "symbol": "COIN",
        "name": "Coinbase (токенизированная акция)",
        "chains": [
          "Robinhood"
        ],
        "tier": 2
      }
    ],
    "exclude_symbols": [
      "XAUT",
      "PAXG",
      "BUIDL",
      "USYC",
      "USTB",
      "OUSG",
      "FIGR_HELOC",
      "BSC-USD"
    ],
    "fallback_top": [
      "BTC",
      "ETH",
      "XRP",
      "BNB",
      "SOL",
      "TRX",
      "DOGE",
      "ADA",
      "HYPE",
      "LINK",
      "BCH",
      "XLM",
      "ZEC",
      "SUI",
      "AVAX",
      "LTC",
      "HBAR",
      "TON",
      "XMR",
      "SHIB",
      "DOT",
      "UNI",
      "AAVE",
      "NEAR",
      "PEPE",
      "ENA",
      "ONDO",
      "APT",
      "ETC",
      "POL"
    ]
  },
  "flags": {
    "il": {
      "level": 2,
      "text": "Непостоянные потери: при сильном движении ETH/BTC позиция LP отстаёт от простого холда. APY этого не учитывает."
    },
    "range": {
      "level": 2,
      "text": "Концентрированная ликвидность: APY пула — среднее, ваш доход зависит от выбранного диапазона и частоты ребалансировки."
    },
    "hooks": {
      "level": 2,
      "text": "Пул может использовать хук — внешний код, который не проходил аудит Uniswap."
    },
    "counterparty": {
      "level": 2,
      "text": "Вы — контрагент трейдеров: их прибыль оплачивается из пула, в шторм возможен минус."
    },
    "lockup": {
      "level": 1,
      "text": "Вывод с задержкой: депозит в HLP заблокирован на 4 дня."
    },
    "emissions": {
      "level": 2,
      "text": "Значительная часть дохода — токены эмиссии, их цена может упасть."
    },
    "basis": {
      "level": 2,
      "text": "Доход зависит от фандинга перпетуалов: при отрицательном фандинге падает; часть обеспечения у кастодианов бирж."
    },
    "credit": {
      "level": 2,
      "text": "Кредитный риск: займы институционалам с неполным обеспечением."
    },
    "curator": {
      "level": 2,
      "text": "Риск хранилища задаёт куратор: проверьте список залогов, лимиты и долю экзотических стейблкоинов."
    },
    "rewards": {
      "level": 2,
      "text": "Больше половины APY — награды и эмиссия. Они временные и обычно дешевеют."
    },
    "spike": {
      "level": 2,
      "text": "Текущий APY более чем вдвое выше среднего за 30 дней — вероятен кратковременный всплеск."
    },
    "smalltvl": {
      "level": 2,
      "text": "Маленький TVL: твой депозит заметно разбавит пул, а выход может сдвинуть цену."
    },
    "negative": {
      "level": 3,
      "text": "Доходность за последний период отрицательная: хранилище теряло деньги."
    },
    "young": {
      "level": 2,
      "text": "Пулу меньше 30 дней: история объёма короткая, доходность может быстро измениться."
    },
    "vol24": {
      "level": 2,
      "text": "Объём за 30 дней недоступен — расчёт по последним 24 часам, он менее надёжен."
    },
    "vol7": {
      "level": 1,
      "text": "Объём за 30 дней недоступен — расчёт по среднему дневному объёму за 7 дней (данные DefiLlama)."
    },
    "volspike": {
      "level": 2,
      "text": "Объём последних суток намного выше среднего за 30 дней — вероятен разовый всплеск."
    },
    "rewardtoken": {
      "level": 2,
      "text": "Награды платятся токенами проекта. Доход в $ посчитан по текущей цене токена, она может упасть."
    },
    "stock": {
      "level": 2,
      "text": "Токенизированная акция: отдельный риск эмитента и торговля вне часов биржи с широким спредом."
    },
    "unverified": {
      "level": 3,
      "text": "Токен в пуле не сопоставлен с CoinGecko — сверьте адрес контракта, это может быть подделка."
    }
  },
  "exit_defaults": {
    "lending": "pool",
    "dex": "instant",
    "perp": "instant",
    "savings": "instant",
    "vault": "instant",
    "yield": "market"
  },
  "exit_texts": {
    "instant": "Вывод в любой момент, без ожидания.",
    "pool": "Вывод сразу, пока на рынке есть свободная ликвидность. Если почти всё занято заёмщиками (загрузка 95–100%), вывод встаёт до погашения займов — так было на Aave в апреле 2026.",
    "cooldown": "Вывод через период ожидания.",
    "lock": "Депозит заблокирован на срок после внесения.",
    "queue": "Вывод через очередь заявок.",
    "market": "Досрочный выход — продажей по рыночной цене, возможен дисконт.",
    "unknown": "Условия вывода не проверены — уточните на сайте протокола."
  }
}
/*JSON-END*/
;
