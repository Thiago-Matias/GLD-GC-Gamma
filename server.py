from flask import Flask, jsonify, send_from_directory, request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import urllib.request
import yfinance as yf
import pandas as pd
import math
import time

from scipy.stats import norm
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


app = Flask(__name__, static_folder=".")


# ============================================================
# CONFIGURAÇÃO
# ============================================================

GLD_SYMBOL = "GLD"
GC_SYMBOL = "GC=F"

MARKET_TZ = ZoneInfo("America/New_York")

GAMMA_CACHE_SECONDS = 60

ZERO_DTE_CUTOFF_HOUR = 16
ZERO_DTE_CUTOFF_MINUTE = 0


# ============================================================
# CACHE
# ============================================================

gamma_cache = {
    0: {
        "timestamp": 0,
        "data": None
    },

    1: {
        "timestamp": 0,
        "data": None
    }
}


last_valid_0dte = None


# ============================================================
# BLACK-SCHOLES GAMMA
# ============================================================

def bs_gamma(S, K, T, sigma):

    if S <= 0:
        return 0.0

    if K <= 0:
        return 0.0

    if T <= 0:
        return 0.0

    if sigma <= 0:
        return 0.0

    try:

        sqrt_T = math.sqrt(T)

        d1 = (
            math.log(S / K)
            + (sigma ** 2 / 2.0) * T
        ) / (
            sigma * sqrt_T
        )

        pdf_d1 = norm.pdf(d1)

        gamma = (
            pdf_d1
            /
            (
                S
                * sigma
                * sqrt_T
            )
        )

        return gamma

    except Exception as e:

        print(
            "ERRO BS GAMMA:",
            e
        )

        return 0.0



# ============================================================
# PREÇO ATUAL DO GLD
# ============================================================

def get_gld_price():

    ticker = yf.Ticker(GLD_SYMBOL)

    # --------------------------------------------------------
    # fast_info
    # --------------------------------------------------------

    try:

        price = ticker.fast_info.get(
            "last_price"
        )

        if price is not None:

            price = float(price)

            if price > 0:

                return price

    except Exception as e:

        print(
            "fast_info GLD falhou:",
            e
        )

    # --------------------------------------------------------
    # fallback histórico
    # --------------------------------------------------------

    try:

        history = ticker.history(
            period="1d",
            interval="1m",
            prepost=True,
            auto_adjust=False
        )

        if not history.empty:

            close = history[
                "Close"
            ].dropna()

            if not close.empty:

                price = float(
                    close.iloc[-1]
                )

                if price > 0:

                    return price

    except Exception as e:

        print(
            "history GLD falhou:",
            e
        )

    raise RuntimeError(
        "Não foi possível obter o preço atual do GLD."
    )


# ============================================================
# EXPIRAÇÕES
# ============================================================

def get_expirations():

    ticker = yf.Ticker(
        GLD_SYMBOL
    )

    try:

        expirations = list(
            ticker.options
        )

    except Exception as e:

        raise RuntimeError(
            "Não foi possível obter as expirações do GLD: "
            + str(e)
        )

    if not expirations:

        raise RuntimeError(
            "O Yahoo Finance não retornou nenhuma expiração para GLD."
        )

    return expirations


# ============================================================
# ESCOLHER EXPIRAÇÃO
# ============================================================

def get_expiration_for_dte(dte):

    expirations = get_expirations()

    today = (
        datetime.now(
            MARKET_TZ
        )
        .date()
        .isoformat()
    )

    future_or_today = [
        x
        for x in expirations
        if x >= today
    ]

    if not future_or_today:

        raise RuntimeError(
            "Não existe expiração disponível para o GLD."
        )

    # --------------------------------------------------------
    # 0DTE
    # --------------------------------------------------------

    if dte == 0:

        if today in expirations:

            return today

        # Se o Yahoo não disponibilizar a expiração de hoje,
        # usamos a próxima disponível.
        return future_or_today[0]

    # --------------------------------------------------------
    # 1DTE
    # --------------------------------------------------------

    if dte == 1:

        tomorrow = (
            datetime.now(
                MARKET_TZ
            ).date()
            + timedelta(days=1)
        ).isoformat()

        future = [
            x
            for x in expirations
            if x >= tomorrow
        ]

        if future:

            return future[0]

        # fallback:
        # segunda expiração disponível
        if len(future_or_today) >= 2:

            return future_or_today[1]

        raise RuntimeError(
            "Não existe expiração disponível para 1DTE."
        )

    raise RuntimeError(
        "DTE inválido. Use 0 ou 1."
    )


# ============================================================
# HORÁRIO DE FECHAMENTO DO 0DTE
# ============================================================

def zero_dte_ja_fechou():

    now = datetime.now(
        MARKET_TZ
    )

    cutoff = now.replace(
        hour=ZERO_DTE_CUTOFF_HOUR,
        minute=ZERO_DTE_CUTOFF_MINUTE,
        second=0,
        microsecond=0
    )

    return now >= cutoff

# ============================================================
# GAMMA FLIP ALGОX FLOW
# ============================================================

def get_algox_gamma():

    url = (
        "https://algoxflow.com/v1/gamma/GLD"
        "?strikes=0"
    )

    try:

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    "GLD-GC-Gamma/1.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:

            raw = response.read()

        data = json.loads(
            raw.decode("utf-8")
        )

        gamma = data.get(
            "gamma",
            {}
        )

        flip = gamma.get(
            "zero_gamma_flip"
        )

        spot = data.get(
            "spot"
        )

        regime = gamma.get(
            "regime"
        )

        age_seconds = data.get(
            "age_seconds"
        )

        as_of = data.get(
            "as_of"
        )

        return {

            "flip":
                float(flip)
                if flip is not None
                else None,

            "spot":
                float(spot)
                if spot is not None
                else None,

            "regime":
                regime,

            "age_seconds":
                float(age_seconds)
                if age_seconds is not None
                else None,

            "as_of":
                as_of

        }

    except Exception as e:

        print(
            "ERRO ALGОX FLOW:",
            e
        )

        return {

            "flip":
                None,

            "spot":
                None,

            "regime":
                None,

            "age_seconds":
                None,

            "as_of":
                None,

            "error":
                str(e)

        }


# ============================================================
# NOSSO GAMMA FLIP
# ============================================================

def calculate_our_gamma_flip(grouped, spot):

    if grouped.empty:

        return None

    data = (
        grouped[
            ["strike", "gex"]
        ]
        .dropna()
        .sort_values(
            "strike"
        )
        .copy()
    )

    if data.empty:

        return None

    # --------------------------------------------------------
    # GEX ACUMULADO
    # --------------------------------------------------------

    data["cumulative_gex"] = (
        data["gex"].cumsum()
    )

    # --------------------------------------------------------
    # PROCURAR CRUZAMENTOS
    # --------------------------------------------------------

    crossings = []

    rows = data.reset_index(
        drop=True
    )

    for i in range(
        1,
        len(rows)
    ):

        previous = rows.iloc[i - 1]
        current = rows.iloc[i]

        previous_value = float(
            previous["cumulative_gex"]
        )

        current_value = float(
            current["cumulative_gex"]
        )

        previous_strike = float(
            previous["strike"]
        )

        current_strike = float(
            current["strike"]
        )

        # ----------------------------------------------------
        # EXATAMENTE ZERO
        # ----------------------------------------------------

        if current_value == 0:

            crossings.append(
                current_strike
            )

            continue

        # ----------------------------------------------------
        # CRUZAMENTO
        # ----------------------------------------------------

        if (
            previous_value < 0
            and
            current_value > 0
        ) or (
            previous_value > 0
            and
            current_value < 0
        ):

            denominator = (
                current_value
                -
                previous_value
            )

            if denominator == 0:

                continue

            fraction = (
                -previous_value
                /
                denominator
            )

            flip = (
                previous_strike
                +
                (
                    current_strike
                    -
                    previous_strike
                )
                *
                fraction
            )

            crossings.append(
                flip
            )

    if not crossings:

        return None

    # --------------------------------------------------------
    # SE HOUVER MAIS DE UM CROSSING,
    # PEGAMOS O MAIS PRÓXIMO DO SPOT
    # --------------------------------------------------------

    closest = min(
        crossings,
        key=lambda x:
            abs(x - spot)
    )

    return float(
        closest
    )



# ============================================================
# CALCULAR GAMMA
# ============================================================

def calculate_gamma(dte):

    global last_valid_0dte

    print()
    print(
        "========== CALCULANDO GAMMA =========="
    )

    print(
        "DTE solicitado:",
        dte
    )

    now = datetime.now(
        MARKET_TZ
    )

    print(
        "Hora ET:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # ========================================================
    # 0DTE APÓS 16:00
    # ========================================================

    if (
        dte == 0
        and
        zero_dte_ja_fechou()
    ):

        print(
            "0DTE já encerrou às 16:00 ET."
        )

        if last_valid_0dte is not None:

            print(
                "Usando último 0DTE válido."
            )

            return last_valid_0dte

        raise RuntimeError(
            "O 0DTE já encerrou às 16:00 ET "
            "e ainda não existe um cálculo válido armazenado."
        )

    # ========================================================
    # EXPIRAÇÃO
    # ========================================================

    expiration = get_expiration_for_dte(
        dte
    )

    print(
        "Expiração:",
        expiration
    )

    # ========================================================
    # PREÇO GLD
    # ========================================================

    S = get_gld_price()

    print(
        "GLD atual:",
        S
    )

    # ========================================================
    # OPTION CHAIN
    # ========================================================

    ticker = yf.Ticker(
        GLD_SYMBOL
    )

    try:

        chain = ticker.option_chain(
            expiration
        )

    except Exception as e:

        raise RuntimeError(
            "Erro carregando option chain do GLD: "
            + str(e)
        )

    calls = chain.calls.copy()
    puts = chain.puts.copy()

    print(
        "Calls recebidas:",
        len(calls)
    )

    print(
        "Puts recebidas:",
        len(puts)
    )

    if calls.empty and puts.empty:

        raise RuntimeError(
            "A cadeia de opções do GLD está vazia."
        )

    # ========================================================
    # TEMPO ATÉ EXPIRAÇÃO
    # ========================================================

    expiration_date = datetime.strptime(
        expiration,
        "%Y-%m-%d"
    ).date()

    expiration_dt = datetime(
        expiration_date.year,
        expiration_date.month,
        expiration_date.day,
        16,
        0,
        0,
        tzinfo=MARKET_TZ
    )

    seconds = (
        expiration_dt - now
    ).total_seconds()

    # --------------------------------------------------------
    # IMPORTANTE
    #
    # Para 0DTE durante o pregão usamos o tempo real.
    #
    # Para 1DTE também usamos o tempo real até a expiração.
    #
    # Não forçamos 60 segundos para um 0DTE já encerrado,
    # pois esse caso é tratado acima pelo último cálculo válido.
    # --------------------------------------------------------

    seconds = max(
        seconds,
        60
    )

    T = (
        seconds
        /
        (
            365.0
            * 24.0
            * 60.0
            * 60.0
        )
    )

    print(
        "Minutos até expiração:",
        round(
            seconds / 60.0,
            2
        )
    )

    # ========================================================
    # PROCESSAR OPÇÕES
    # ========================================================

    def process_options(
        dataframe,
        option_type
    ):

    
        
        result = []

        for _, row in dataframe.iterrows():

            try:

                strike = row.get(
                    "strike"
                )

                oi = row.get(
                    "openInterest"
                )

                iv = row.get(
                    "impliedVolatility"
                )

                if pd.isna(strike):
                    continue

                if pd.isna(oi):
                    continue

                if pd.isna(iv):
                    continue

                strike = float(
                    strike
                )

                oi = float(
                    oi
                )

                iv = float(
                    iv
                )

            except Exception:

                continue

            # ------------------------------------------------
            # VALIDAÇÃO
            # ------------------------------------------------

            if strike <= 0:
                continue

            if oi <= 0:
                continue

            if iv <= 0:
                continue

            if iv > 5:
                continue

            # ------------------------------------------------
            # GAMMA
            # ------------------------------------------------

            gamma = bs_gamma(
                S,
                strike,
                T,
                iv
            )

            if gamma <= 0:
                continue

                        # ------------------------------------------------
            # GEX ABSOLUTO
            # ------------------------------------------------

            absolute_gex = (
                gamma
                * oi
                * (S ** 2)
                / 100.0
            )

            # ------------------------------------------------
            # DEBUG: STRIKES 370 ATÉ 390
            # ------------------------------------------------

            if 370 <= strike <= 390:

                print(
                    f"{option_type.upper()} "
                    f"STRIKE={strike:.2f} "
                    f"OI={oi:.0f} "
                    f"IV={iv:.6f} "
                    f"GAMMA={gamma:.10f} "
                    f"GEX={absolute_gex:.6f}"
                )

            # ------------------------------------------------
            # GEX ASSINADO
            # ------------------------------------------------

            if option_type == "call":

                signed_gex = absolute_gex

            else:

                signed_gex = -absolute_gex


            result.append({

                "strike":
                    strike,

                "gamma":
                    gamma,

                "oi":
                    oi,

                "iv":
                    iv,

                "absolute_gex":
                    absolute_gex,

                "signed_gex":
                    signed_gex

            })

        return result

    

    # ========================================================
    # CALLS
    # ========================================================

    call_result = process_options(
        calls,
        "call"
    )

    # ========================================================
    # PUTS
    # ========================================================

    put_result = process_options(
        puts,
        "put"
    )

    print(
        "Calls válidas:",
        len(call_result)
    )

    print(
        "Puts válidas:",
        len(put_result)
    )

    if not call_result and not put_result:

        raise RuntimeError(
            "Nenhuma opção válida encontrada "
            "para calcular o GEX."
        )

    # ========================================================
    # DATAFRAMES
    # ========================================================

    calls_df = pd.DataFrame(
        call_result
    )

    puts_df = pd.DataFrame(
        put_result
    )

    # ========================================================
    # CALLS POR STRIKE
    # ========================================================

    if not calls_df.empty:

        calls_grouped = (
            calls_df
            .groupby("strike")[
                "absolute_gex"
            ]
            .sum()
            .reset_index()
        )

        calls_grouped = calls_grouped.rename(
            columns={
                "absolute_gex":
                    "call_gex"
            }
        )

    else:

        calls_grouped = pd.DataFrame(
            columns=[
                "strike",
                "call_gex"
            ]
        )

    # ========================================================
    # PUTS POR STRIKE
    # ========================================================

    if not puts_df.empty:

        puts_grouped = (
            puts_df
            .groupby("strike")[
                "absolute_gex"
            ]
            .sum()
            .reset_index()
        )

        puts_grouped = puts_grouped.rename(
            columns={
                "absolute_gex":
                    "put_gex"
            }
        )

    else:

        puts_grouped = pd.DataFrame(
            columns=[
                "strike",
                "put_gex"
            ]
        )

    # ========================================================
    # MERGE
    # ========================================================

    grouped = pd.merge(
        calls_grouped,
        puts_grouped,
        on="strike",
        how="outer"
    )

    grouped["call_gex"] = (
        grouped["call_gex"]
        .fillna(0.0)
    )

    grouped["put_gex"] = (
        grouped["put_gex"]
        .fillna(0.0)
    )

    # ========================================================
    # GEX LÍQUIDO
    # ========================================================

    grouped["gex"] = (
        grouped["call_gex"]
        -
        grouped["put_gex"]
    )
    
    # ========================================================
    # PREENCHER STRIKES AUSENTES
    #
    # Garante que os strikes inteiros apareçam em sequência.
    #
    # Exemplo:
    #
    # 375
    # 376
    # 377
    # 378
    # 379
    # 380
    # 381
    #
    # Mesmo que algum strike não tenha GEX válido,
    # ele será mostrado com CALL=0 / PUT=0 / NET=0.
    # ========================================================

    lower = S * 0.94
    upper = S * 1.06

    strike_min = math.floor(lower)
    strike_max = math.ceil(upper)

    all_strikes = pd.DataFrame({
        "strike": range(
            strike_min,
            strike_max + 1
        )
    })

    grouped = pd.merge(
        all_strikes,
        grouped,
        on="strike",
        how="left"
    )

    grouped["call_gex"] = (
        grouped["call_gex"]
        .fillna(0.0)
    )

    grouped["put_gex"] = (
        grouped["put_gex"]
        .fillna(0.0)
    )

    grouped["gex"] = (
        grouped["call_gex"]
        -
        grouped["put_gex"]
    )

    # ========================================================
    # FILTRO ±6%
    # ========================================================

    grouped = grouped[
        (grouped["strike"] >= lower)
        &
        (grouped["strike"] <= upper)
    ]

    if grouped.empty:

        raise RuntimeError(
            "Nenhum strike encontrado dentro "
            "de ±6% do GLD."
        )

    # ========================================================
    # NOSSO GAMMA FLIP
    # ========================================================

    our_gamma_flip = calculate_our_gamma_flip(
        grouped,
        S
    )

    

    print(
        "Nosso Gamma Flip:",
        our_gamma_flip
    )


    # ========================================================
    # GAMMA FLIP ALGОX
    # ========================================================

    algox_gamma = get_algox_gamma()

    algox_gamma_flip = (
        algox_gamma.get("flip")
    )

    algox_age_seconds = (
        algox_gamma.get("age_seconds")
    )

    algox_regime = (
        algox_gamma.get("regime")
    )

    print(
        "AlgoX Gamma Flip:",
        algox_gamma_flip
    )

    print(
        "AlgoX idade:",
        algox_age_seconds,
        "segundos"
    )

    print(
        "AlgoX regime:",
        algox_regime
    )
    
    # ========================================================
    # ORDENAR
    # ========================================================

    grouped = grouped.sort_values(
        "strike",
        ascending=False
    )

    # ========================================================
    # MAX ABS
    # ========================================================

    max_abs = float(
        grouped["gex"]
        .abs()
        .max()
    )

    # ========================================================
    # ROWS
    # ========================================================

    rows = []

    for _, row in grouped.iterrows():

        strike = float(
            row["strike"]
        )

        call_gex = float(
            row["call_gex"]
        )

        put_gex = float(
            row["put_gex"]
        )

        net_gex = float(
            row["gex"]
        )

        if max_abs > 0:

            intensity = (
                abs(net_gex)
                /
                max_abs
                *
                100.0
            )

        else:

            intensity = 0.0

        rows.append({

            "gld":
                strike,

            "call_gex":
                call_gex,

            "put_gex":
                -put_gex,

            "gex":
                net_gex,

            "intensity":
                intensity

        })

    # ========================================================
    # MAX POSITIVO
    # ========================================================

    positive = grouped[
        grouped["gex"] > 0
    ]

    max_positive = None

    if not positive.empty:

        max_positive = float(
            positive
            .sort_values(
                "gex",
                ascending=False
            )
            .iloc[0]["strike"]
        )

    # ========================================================
    # MAX NEGATIVO
    # ========================================================

    negative = grouped[
        grouped["gex"] < 0
    ]

    max_negative = None

    if not negative.empty:

        max_negative = float(
            negative
            .sort_values(
                "gex",
                ascending=True
            )
            .iloc[0]["strike"]
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    result = {

        "ticker":
            GLD_SYMBOL,

        "dte":
            dte,

        "expiration":
            expiration,

        "gld_price":
            S,

        "gamma_flip": {

            "our":
                our_gamma_flip,

            "algox":
                algox_gamma_flip,

            "algox_age_seconds":
                algox_age_seconds,

            "algox_regime":
                algox_regime,

            "algox_as_of":
                algox_gamma.get(
                    "as_of"
                )

        },
    

        "rows":
            rows,

        "max_positive":
            max_positive,

        "max_negative":
            max_negative,

        "updated":
            datetime.now(
                MARKET_TZ
            ).isoformat(),

        "frozen":
            False

    }

    # ========================================================
    # SALVAR ÚLTIMO 0DTE VÁLIDO
    # ========================================================

    if dte == 0:

        last_valid_0dte = result

        print(
            "Último 0DTE válido atualizado."
        )

    # ========================================================
    # DEBUG
    # ========================================================

    print()
    print(
        "----- GEX POR STRIKE -----"
    )

    for item in rows:

        print(
            f'{item["gld"]:.2f} '
            f'CALL={item["call_gex"]:.6f} '
            f'PUT={item["put_gex"]:.6f} '
            f'NET={item["gex"]:.6f}'
        )

    print(
        "MAX +:",
        max_positive
    )

    print(
        "MAX -:",
        max_negative
    )

    print(
        "=========================="
    )

    return result


# ============================================================
# API GAMMA
# ============================================================

@app.route("/api/gamma")
def api_gamma():

    global gamma_cache
    global last_valid_0dte

    # --------------------------------------------------------
    # DTE
    # --------------------------------------------------------

    try:

        dte = int(
            request.args.get(
                "dte",
                "0"
            )
        )

    except Exception:

        dte = 0

    if dte not in (0, 1):

        return jsonify({

            "ok": False,

            "error":
                "DTE inválido. Use dte=0 ou dte=1."

        }), 400

    # ========================================================
    # 0DTE ENCERRADO
    # ========================================================

    if (
        dte == 0
        and
        zero_dte_ja_fechou()
    ):

        if last_valid_0dte is not None:

            frozen_data = dict(
                last_valid_0dte
            )

            frozen_data["frozen"] = True

            return jsonify({

                "ok":
                    True,

                "data":
                    frozen_data,

                "cached":
                    True,

                "frozen":
                    True

            })

        return jsonify({

            "ok":
                False,

            "error":
                "O 0DTE já encerrou às 16:00 ET. "
                "Ainda não existe um cálculo válido armazenado."

        }), 400

    # ========================================================
    # CACHE NORMAL
    # ========================================================

    now = time.time()

    cache = gamma_cache[dte]

    if (
        cache["data"] is not None
        and
        (
            now
            -
            cache["timestamp"]
        )
        < GAMMA_CACHE_SECONDS
    ):

        return jsonify({

            "ok":
                True,

            "data":
                cache["data"],

            "cached":
                True,

            "frozen":
                False

        })

    # ========================================================
    # CALCULAR
    # ========================================================

    try:

        data = calculate_gamma(
            dte
        )

        gamma_cache[dte] = {

            "timestamp":
                now,

            "data":
                data

        }

        return jsonify({

            "ok":
                True,

            "data":
                data,

            "cached":
                False,

            "frozen":
                False

        })

    except Exception as e:

        print()
        print(
            "ERRO /api/gamma:"
        )
        print(
            str(e)
        )
        print()

        return jsonify({

            "ok":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# API ÂNCORA
# ============================================================

# Mantida com a mesma lógica do seu código atual.
# ============================================================

def get_last_hour_anchor():

    print()
    print(
        "========== BUSCANDO ÂNCORA =========="
    )

    now = datetime.now(
        MARKET_TZ
    )

    anchor_hour = now.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    print(
        "Hora atual ET:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print(
        "Hora-chave:",
        anchor_hour.strftime(
            "%Y-%m-%d %H:%M"
        )
    )

    market_open = anchor_hour.replace(
        hour=10,
        minute=30,
        second=0,
        microsecond=0
    )

    gld = yf.Ticker(
        GLD_SYMBOL
    ).history(
        period="5d",
        interval="1m",
        prepost=True,
        auto_adjust=False
    )

    gc = yf.Ticker(
        GC_SYMBOL
    ).history(
        period="5d",
        interval="1m",
        prepost=True,
        auto_adjust=False
    )

    if gld.empty:

        raise RuntimeError(
            "Histórico intraday do GLD vazio."
        )

    if gc.empty:

        raise RuntimeError(
            "Histórico intraday do GC vazio."
        )

    if gld.index.tz is None:

        gld.index = gld.index.tz_localize(
            MARKET_TZ
        )

    else:

        gld.index = gld.index.tz_convert(
            MARKET_TZ
        )

    if gc.index.tz is None:

        gc.index = gc.index.tz_localize(
            MARKET_TZ
        )

    else:

        gc.index = gc.index.tz_convert(
            MARKET_TZ
        )

        # ========================================================
        # GC - HORÁRIO DA VIRADA DA HORA
        # ========================================================

        gc_target = anchor_hour

        print(
            "GC alvo:",
            gc_target.strftime("%Y-%m-%d %H:%M")
        )

        gc_matches = gc[
            (
                gc.index.date
                ==
                gc_target.date()
            )
            &
            (
                gc.index.hour
                ==
                gc_target.hour
            )
            &
            (
                gc.index.minute
                ==
                0
            )
        ]

        gc_bar = None

        if not gc_matches.empty:

            gc_bar = gc_matches.iloc[0]

            print(
                "GC encontrado:",
                gc_target.strftime("%H:%M")
            )

        if gc_bar is None:

            gc_before = gc[
                gc.index <= gc_target
            ]

            if not gc_before.empty:

                gc_bar = gc_before.iloc[-1]

                print(
                    "GC fallback:",
                    gc_before.index[-1].strftime(
                        "%Y-%m-%d %H:%M"
                    )
                )

        if gc_bar is None:

            raise RuntimeError(
                f"GC não possui dados próximos de "
                f"{gc_target:%H:%M}."
            )

    # ========================================================
    # GLD
    # ========================================================

    if anchor_hour < market_open:

        previous_day = (
            anchor_hour.date()
            -
            timedelta(days=1)
        )

        previous_gld = gld[
            gld.index.date
            ==
            previous_day
        ]

        if previous_gld.empty:

            previous_gld = gld[
                gld.index < anchor_hour
            ]

        if previous_gld.empty:

            raise RuntimeError(
                "Não foi possível encontrar "
                "o fechamento anterior do GLD."
            )

        gld_bar = previous_gld.iloc[-1]

        gld_price = float(
            gld_bar["Close"]
        )

    else:

        gld_matches = gld[
            (
                gld.index.date
                ==
                anchor_hour.date()
            )
            &
            (
                gld.index.hour
                ==
                anchor_hour.hour
            )
            &
            (
                gld.index.minute
                ==
                0
            )
        ]

        gld_bar = None

        if not gld_matches.empty:

            gld_bar = gld_matches.iloc[0]

        if gld_bar is None:

            gld_hour = gld[
                (
                    gld.index.date
                    ==
                    anchor_hour.date()
                )
                &
                (
                    gld.index.hour
                    ==
                    anchor_hour.hour
                )
            ]

            if not gld_hour.empty:

                gld_bar = gld_hour.iloc[0]

        if gld_bar is None:

            raise RuntimeError(
                f"GLD não possui dados para "
                f"{anchor_hour:%H:%M}."
            )

        gld_price = float(
            gld_bar["Open"]
        )

    # ========================================================
    # GC
    # ========================================================

    gc_price = float(
        gc_bar["Open"]
    )

    if gld_price <= 0:

        raise RuntimeError(
            "Preço da âncora GLD inválido."
        )

    if gc_price <= 0:

        raise RuntimeError(
            "Preço da âncora GC inválido."
        )

    factor = (
        gc_price
        /
        gld_price
    )

    print()
    print(
        "----- ÂNCORA -----"
    )

    print(
        "GLD:",
        gld_price
    )

    print(
        "GC:",
        gc_price
    )

    print(
        "Fator:",
        factor
    )

    print(
        "=================="
    )

    return {

        "time":
            anchor_hour.isoformat(),

        "display_time":
            anchor_hour.strftime(
                "%H:%M"
            ),

        "gld":
            gld_price,

        "gc":
            gc_price,

        "factor":
            factor

    }


@app.route("/api/anchor")
def api_anchor():

    try:

        anchor = (
            get_last_hour_anchor()
        )

        return jsonify({

            "ok":
                True,

            "data":
                anchor

        })

    except Exception as e:

        print(
            "ERRO /api/anchor:",
            e
        )

        return jsonify({

            "ok":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def index():

    return send_from_directory(
        ".",
        "index.html"
    )


@app.route("/style.css")
def css():

    return send_from_directory(
        ".",
        "style.css"
    )


@app.route("/app.js")
def javascript():

    return send_from_directory(
        ".",
        "app.js"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "======================================"
    )
    print(
        " GLD → GC GAMMA"
    )
    print(
        " 0DTE / 1DTE"
    )
    print(
        " http://127.0.0.1:5000"
    )
    print(
        "======================================"
    )
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
