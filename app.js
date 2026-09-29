// ==========================================================
// GLD → GC GAMMA
// 0DTE / 1DTE
// ==========================================================

let gammaData = [];

let marketData = null;

let anchorData = null;

let mostrarTodosOsNiveis = false;

const MAX_NIVEIS_PADRAO = 19;


// ==========================================================
// DTE SELECIONADO
// ==========================================================

let selectedDTE = 0;


// ==========================================================
// ELEMENTOS
// ==========================================================

const gldAnchorInput =
    document.getElementById("gldAnchor");

const gcAnchorInput =
    document.getElementById("gcAnchor");

const anchorTimeInput =
    document.getElementById("anchorTime");

const gammaTable =
    document.getElementById("gammaTable");

const statusElement =
    document.getElementById("status");

const calculateButton =
    document.getElementById("calculateButton");

const manualButton =
    document.getElementById("manualButton");


// ==========================================================
// FORMATAÇÃO
// ==========================================================

function formatNumber(
    value,
    decimals = 2
) {

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "-";
    }

    return number.toLocaleString(
        "pt-BR",
        {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }
    );
}


// ==========================================================
// GEX
// ==========================================================
//
// Não reduz a escala.
//
// Mostra menos casas decimais quando necessário.
// ==========================================================
function formatGEX(value) {

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "-";
    }

    const formatted =
        Math.abs(number).toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        );

    return (
        number > 0
            ? "+" + formatted
            : number < 0
                ? "-" + formatted
                : formatted
    );
}


// ==========================================================
// GAMMA FLIP
// ==========================================================

function formatFlip(value) {

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "-";
    }

    return number.toFixed(2);
}


// ==========================================================
// DISTÂNCIA DO FLIP
// ==========================================================

function getFlipStatus(
    spot,
    flip
) {

    const current =
        Number(spot);

    const level =
        Number(flip);

    if (
        !Number.isFinite(current)
        ||
        !Number.isFinite(level)
    ) {

        return {
            text: "-",
            className: ""
        };

    }

    if (current > level) {

        return {
            text: "ACIMA DO FLIP",
            className: "above"
        };

    }

    if (current < level) {

        return {
            text: "ABAIXO DO FLIP",
            className: "below"
        };

    }

    return {
        text: "NO FLIP",
        className: "at-flip"
    };

}


// ==========================================================
// RENDER GAMMA FLIP
// ==========================================================

function renderGammaFlip() {

    if (!marketData) {
        return;
    }

    const gammaFlip =
        marketData.gamma_flip;

    if (!gammaFlip) {
        return;
    }


    const spot =
        Number(
            marketData.gld_price
        );


    // ------------------------------------------------------
    // NOSSO
    // ------------------------------------------------------

    const ourFlip =
        Number(
            gammaFlip.our
        );


    const ourElement =
        document.getElementById(
            "ourGammaFlip"
        );


    if (ourElement) {

        ourElement.textContent =
            Number.isFinite(
                ourFlip
            )
                ? formatFlip(
                    ourFlip
                )
                : "-";

    }


    const ourStatus =
        getFlipStatus(
            spot,
            ourFlip
        );


    const ourStatusElement =
        document.getElementById(
            "ourGammaStatus"
        );


    if (ourStatusElement) {

        ourStatusElement.textContent =
            ourStatus.text;

        ourStatusElement.className =
            "flip-status " +
            ourStatus.className;

    }


    // ------------------------------------------------------
    // ALGOX
    // ------------------------------------------------------

    const algoxFlip =
        Number(
            gammaFlip.algox
        );


    const algoxElement =
        document.getElementById(
            "algoxGammaFlip"
        );


    if (algoxElement) {

        algoxElement.textContent =
            Number.isFinite(
                algoxFlip
            )
                ? formatFlip(
                    algoxFlip
                )
                : "-";

    }


    const algoxStatus =
        getFlipStatus(
            spot,
            algoxFlip
        );


    const algoxStatusElement =
        document.getElementById(
            "algoxGammaStatus"
        );


    if (algoxStatusElement) {

        algoxStatusElement.textContent =
            algoxStatus.text;

        algoxStatusElement.className =
            "flip-status " +
            algoxStatus.className;

    }


    // ------------------------------------------------------
    // REGIME
    // ------------------------------------------------------

    const regimeElement =
        document.getElementById(
            "gammaRegime"
        );


    if (regimeElement) {

        if (
            Number.isFinite(
                algoxFlip
            )
        ) {

            if (spot > algoxFlip) {

                regimeElement.textContent =
                    "GAMMA POSITIVO";

                regimeElement.className =
                    "gamma-regime positive";

            }

            else if (
                spot < algoxFlip
            ) {

                regimeElement.textContent =
                    "GAMMA NEGATIVO";

                regimeElement.className =
                    "gamma-regime negative";

            }

            else {

                regimeElement.textContent =
                    "NO GAMMA FLIP";

                regimeElement.className =
                    "gamma-regime neutral";

            }

        }

        else {

            regimeElement.textContent =
                "-";

            regimeElement.className =
                "gamma-regime";

        }

    }


    // ------------------------------------------------------
    // IDADE DO ALGOX
    // ------------------------------------------------------

    const ageElement =
        document.getElementById(
            "algoxGammaAge"
        );


    if (ageElement) {

        const age =
            Number(
                gammaFlip.algox_age_seconds
            );


        if (
            Number.isFinite(age)
        ) {

            if (age < 60) {

                ageElement.textContent =
                    `${Math.round(age)}s`;

            }

            else {

                ageElement.textContent =
                    `${Math.round(
                        age / 60
                    )} min`;

            }

        }

        else {

            ageElement.textContent =
                "-";

        }

    }

}



// ==========================================================
// STATUS
// ==========================================================

function setStatus(
    message,
    type = ""
) {

    if (!statusElement) {
        return;
    }

    statusElement.textContent =
        message;

    statusElement.className =
        "status " + type;
}


// ==========================================================
// DTE LABEL
// ==========================================================

function getDteLabel() {

    return selectedDTE === 0
        ? "0DTE"
        : "1DTE";
}


// ==========================================================
// CONVERSÃO GLD → GC
// ==========================================================

function converterGLDparaGC(
    gldPrice
) {

    if (!anchorData) {
        return null;
    }

    const gldAnchor =
        Number(
            anchorData.gld
        );

    const gcAnchor =
        Number(
            anchorData.gc
        );

    if (
        !Number.isFinite(
            gldAnchor
        )
        ||
        !Number.isFinite(
            gcAnchor
        )
        ||
        gldAnchor === 0
    ) {

        return null;
    }

    const factor =
        gcAnchor /
        gldAnchor;

    return (
        gcAnchor
        +
        (
            Number(gldPrice)
            -
            gldAnchor
        )
        *
        factor
    );
}


// ==========================================================
// CARREGAR ÂNCORA
// ==========================================================

async function carregarAnchor() {

    try {

        const response =
            await fetch(
                "/api/anchor?ts=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            );

        const result =
            await response.json();

        if (
            !response.ok
            ||
            !result.ok
        ) {

            throw new Error(
                result.error
                ||
                "Erro ao buscar âncora."
            );

        }

        anchorData =
            result.data;


        if (gldAnchorInput) {

            gldAnchorInput.value =
                Number(
                    anchorData.gld
                ).toFixed(2);

        }


        if (gcAnchorInput) {

            gcAnchorInput.value =
                Number(
                    anchorData.gc
                ).toFixed(2);

        }


        if (anchorTimeInput) {

            anchorTimeInput.value =
                anchorData.display_time;

        }


        const showGLD =
            document.getElementById(
                "showGLD"
            );

        const showGC =
            document.getElementById(
                "showGC"
            );

        const showFactor =
            document.getElementById(
                "showFactor"
            );

        const showTime =
            document.getElementById(
                "showTime"
            );


        if (showGLD) {

            showGLD.textContent =
                formatNumber(
                    anchorData.gld
                );

        }


        if (showGC) {

            showGC.textContent =
                formatNumber(
                    anchorData.gc
                );

        }


        if (showFactor) {

            showFactor.textContent =
                Number(
                    anchorData.factor
                ).toFixed(8);

        }


        if (showTime) {

            showTime.textContent =
                anchorData.display_time;

        }


        renderizar();

    }
    catch (error) {

        console.error(
            "ERRO ÂNCORA:",
            error
        );

        setStatus(
            "Erro na âncora: " +
            error.message,
            "error"
        );

    }

}


// ==========================================================
// CARREGAR GAMMA
// ==========================================================

async function carregarGamma() {

    try {

        const dte =
            selectedDTE;


        setStatus(
            `Carregando ${getDteLabel()} do GLD...`
        );


        console.log(
            "========== BUSCANDO GAMMA =========="
        );

        console.log(
            "DTE:",
            dte
        );


        const response =
            await fetch(
                `/api/gamma?dte=${dte}&ts=${Date.now()}`,
                {
                    cache: "no-store"
                }
            );


        console.log(
            "HTTP /api/gamma:",
            response.status
        );


        const result =
            await response.json();


        console.log(
            "JSON GAMMA:",
            result
        );


        if (
            !response.ok
            ||
            !result.ok
        ) {

            throw new Error(
                result.error
                ||
                "Erro ao carregar Gamma."
            );

        }


        if (
            !result.data
            ||
            !Array.isArray(
                result.data.rows
            )
        ) {

            throw new Error(
                "API retornou Gamma sem a lista de rows."
            );

        }


        marketData =
            result.data;

            renderGammaFlip();


        gammaData =
            marketData.rows

                .map(
                    row => ({

                        gld:
                            Number(
                                row.gld
                            ),

                        gex:
                            Number(
                                row.gex
                            ),

                        intensity:
                            Number(
                                row.intensity
                            )

                    })
                )

                .filter(
                    row =>
                        Number.isFinite(
                            row.gld
                        )
                        &&
                        Number.isFinite(
                            row.gex
                        )
                );


        console.log(
            "ROWS RECEBIDAS:",
            gammaData.length
        );
        
        console.log(
        "STRIKES GAMMA:",
        gammaData.map(item => ({
            gld: item.gld,
            gex: item.gex
        }))
        );



        if (
            gammaData.length === 0
        ) {

            throw new Error(
                "A API retornou 0 strikes."
            );

        }


        const frozen =
            result.frozen
            ||
            marketData.frozen;


        if (
            selectedDTE === 0
            &&
            frozen
        ) {

            setStatus(
                `0DTE encerrado às 16:00 ET · usando último cálculo válido · ${marketData.expiration}`,
                "success"
            );

        }

        else {

            setStatus(
                `${getDteLabel()} · GLD ${formatNumber(
                    marketData.gld_price
                )} · expiração ${
                    marketData.expiration
                } · ${
                    gammaData.length
                } strikes`,
                "success"
            );

        }


        atualizarIndicadorDTE();

        renderizar();
        renderGammaFlip();

    }
    catch (error) {

        console.error(
            "ERRO GAMMA:",
            error
        );


        setStatus(
            "Erro no Gamma: " +
            error.message,
            "error"
        );


        if (gammaTable) {

            gammaTable.innerHTML = `

                <div class="error-box">

                    Não foi possível carregar
                    o Gamma do GLD.

                    <br><br>

                    ${error.message}

                </div>

            `;

        }

    }

}


// ==========================================================
// INDICADOR DTE
// ==========================================================

function atualizarIndicadorDTE() {

    const dteElement =
        document.getElementById(
            "currentDTE"
        );

    if (dteElement) {

        dteElement.textContent =
            getDteLabel();

    }


    const expirationElement =
        document.getElementById(
            "currentExpiration"
        );

    if (
        expirationElement
        &&
        marketData
    ) {

        expirationElement.textContent =
            marketData.expiration
            ||
            "-";

    }


    const frozenElement =
        document.getElementById(
            "gammaFrozen"
        );

    if (frozenElement) {

        const frozen =
            marketData
            &&
            marketData.frozen;

        frozenElement.textContent =
            frozen
                ? "CONGELADO"
                : "";

        frozenElement.className =
            frozen
                ? "gamma-frozen"
                : "";

    }


    document
        .querySelectorAll(
            "[data-dte]"
        )
        .forEach(
            button => {

                const value =
                    Number(
                        button.dataset.dte
                    );

                button.classList.toggle(
                    "active",
                    value === selectedDTE
                );

            }
        );

}


// ==========================================================
// RENDERIZAR
// ==========================================================

function renderizar() {

    if (!anchorData) {
        return;
    }

    if (!gammaData.length) {
        return;
    }


    const showGLD =
        document.getElementById(
            "showGLD"
        );

    const showGC =
        document.getElementById(
            "showGC"
        );

    const showFactor =
        document.getElementById(
            "showFactor"
        );

    const showTime =
        document.getElementById(
            "showTime"
        );


    if (showGLD) {

        showGLD.textContent =
            formatNumber(
                anchorData.gld
            );

    }


    if (showGC) {

        showGC.textContent =
            formatNumber(
                anchorData.gc
            );

    }


    if (showFactor) {

        showFactor.textContent =
            Number(
                anchorData.factor
            ).toFixed(8);

    }


    if (showTime) {

        showTime.textContent =
            anchorData.display_time;

    }


    // ======================================================
    // MAIOR POSITIVO
    // ======================================================

    const positiveRows =
        gammaData.filter(
            item =>
                item.gex > 0
        );


    const positive =
        positiveRows.length

            ? positiveRows.reduce(
                (max, item) =>
                    item.gex > max.gex
                        ? item
                        : max
            )

            : null;


    // ======================================================
    // MAIOR NEGATIVO
    // ======================================================

    const negativeRows =
        gammaData.filter(
            item =>
                item.gex < 0
        );


    const negative =
        negativeRows.length

            ? negativeRows.reduce(
                (min, item) =>
                    item.gex < min.gex
                        ? item
                        : min
            )

            : null;


    const maxPositive =
        document.getElementById(
            "maxPositive"
        );


    if (maxPositive) {

        maxPositive.textContent =
            positive
                ? formatNumber(
                    positive.gld
                )
                : "-";

    }


    const maxNegative =
        document.getElementById(
            "maxNegative"
        );


    if (maxNegative) {

        maxNegative.textContent =
            negative
                ? formatNumber(
                    negative.gld
                )
                : "-";

    }


    const gammaLong =
        document.getElementById(
            "gammaLong"
        );


    if (gammaLong) {

        gammaLong.textContent =
            positive
                ? formatNumber(
                    converterGLDparaGC(
                        positive.gld
                    )
                )
                : "-";

    }


    const gammaShort =
        document.getElementById(
            "gammaShort"
        );


    if (gammaShort) {

        gammaShort.textContent =
            negative
                ? formatNumber(
                    converterGLDparaGC(
                        negative.gld
                    )
                )
                : "-";

    }


    // ======================================================
    // MAIOR ABSOLUTO
    // ======================================================

    const maxPositiveGEX =
        Math.max(
            0,
            ...gammaData
                .filter(item => item.gex > 0)
                .map(item => item.gex)
        );


    const maxNegativeGEX =
        Math.max(
            0,
            ...gammaData
                .filter(item => item.gex < 0)
                .map(item => Math.abs(item.gex))
        );
        

    if (!gammaTable) {

        console.error(
            "Elemento #gammaTable não encontrado."
        );

        return;

    }


    gammaTable.innerHTML = "";


    // ======================================================
    // ORDENAR
    // ======================================================

    const sortedData =
        [...gammaData].sort(
            (a, b) =>
                b.gld - a.gld
        );


    // ======================================================
    // LIMITAR
    // ======================================================

    const dadosParaMostrar =
        mostrarTodosOsNiveis
            ? sortedData
            : sortedData.slice(
                0,
                MAX_NIVEIS_PADRAO
            );


    // ======================================================
    // BOTÃO MAIS NÍVEIS
    // ======================================================

    const moreLevelsButton =
        document.getElementById(
            "moreLevelsButton"
        );


    if (moreLevelsButton) {

        moreLevelsButton.textContent =
            mostrarTodosOsNiveis
                ? "MOSTRAR MENOS NÍVEIS"
                : "MOSTRAR MAIS NÍVEIS";

    }


    // ======================================================
    // LINHAS
    // ======================================================

    dadosParaMostrar.forEach(
        item => {

            const gc =
                converterGLDparaGC(
                    item.gld
                );


            
            const maxSide =
            item.gex >= 0
                ? maxPositiveGEX
                : maxNegativeGEX;


            const intensity =
                    maxSide > 0
                        ? (
                            Math.abs(item.gex)
                            /
                            maxSide
                        ) * 100
                : 0;
       

            const isPositive =
                item.gex >= 0;


            const barClass =
                isPositive
                    ? "positive"
                    : "negative";


            const textClass =
                isPositive
                    ? "positive-text"
                    : "negative-text";


            let marker = "";


            // ------------------------------------------------
            // ÂNCORA
            // ------------------------------------------------

            if (
                anchorData
                &&
                Math.abs(
                    item.gld
                    -
                    Number(
                        anchorData.gld
                    )
                ) < 0.001
            ) {

                marker += `

                    <span class="marker call">
                        ÂNCORA
                    </span>

                `;

            }


            // ------------------------------------------------
            // MAX +
            // ------------------------------------------------

            if (
                marketData
                &&
                marketData.max_positive !== null
                &&
                Number(item.gld)
                ===
                Number(
                    marketData.max_positive
                )
            ) {

                marker += `

                    <span class="marker long">
                        MAX +
                    </span>

                `;

            }


            // ------------------------------------------------
            // MAX -
            // ------------------------------------------------

            if (
                marketData
                &&
                marketData.max_negative !== null
                &&
                Number(item.gld)
                ===
                Number(
                    marketData.max_negative
                )
            ) {

                marker += `

                    <span class="marker short">
                        MAX -
                    </span>

                `;

            }


            const row =
                document.createElement(
                    "div"
                );


            row.className =
                "row";


            row.innerHTML = `

                <div class="price">

                    ${formatNumber(
                        item.gld
                    )}

                    ${marker}

                </div>


                <div class="price gc-price">

                    ${
                        gc !== null
                            ? formatNumber(gc)
                            : "-"
                    }

                </div>


                <div class="bar-cell">

                    <div class="bar-container">

                        <div
                            class="bar ${barClass}"
                            style="width:${Math.min(
                                100,
                                Math.max(
                                    0,
                                    intensity
                                )
                            )}%"
                            title="GEX: ${formatGEX(
                                item.gex
                            )}"
                        ></div>

                    </div>

                </div>


                <div class="gex ${textClass}">

                    ${formatGEX(
                        item.gex
                    )}

                </div>

            `;


            gammaTable.appendChild(
                row
            );

        }
    );

}


// ==========================================================
// TESTE MANUAL
// ==========================================================

function calcularManual() {

    if (
        !gldAnchorInput
        ||
        !gcAnchorInput
    ) {
        return;
    }


    const gldAnchor =
        Number(
            gldAnchorInput.value
        );


    const gcAnchor =
        Number(
            gcAnchorInput.value
        );


    if (
        !Number.isFinite(
            gldAnchor
        )
        ||
        !Number.isFinite(
            gcAnchor
        )
        ||
        gldAnchor === 0
    ) {

        setStatus(
            "Digite primeiro o GLD e o GC da âncora.",
            "error"
        );

        return;

    }


    const factor =
        gcAnchor /
        gldAnchor;


    function converter(
        gldLevel
    ) {

        return (
            gcAnchor
            +
            (
                gldLevel
                -
                gldAnchor
            )
            *
            factor
        );

    }


    const levels = [

        {
            input:
                "manual393",

            gld:
                "manualGld393",

            gc:
                "manualGc393"
        },

        {
            input:
                "manual392",

            gld:
                "manualGld392",

            gc:
                "manualGc392"
        },

        {
            input:
                "manual391",

            gld:
                "manualGld391",

            gc:
                "manualGc391"
        },

        {
            input:
                "manual390",

            gld:
                "manualGld390",

            gc:
                "manualGc390"
        }

    ];


    levels.forEach(
        item => {

            const input =
                document.getElementById(
                    item.input
                );

            if (!input) {
                return;
            }


            const gldValue =
                Number(
                    input.value
                );


            const gldElement =
                document.getElementById(
                    item.gld
                );


            const gcElement =
                document.getElementById(
                    item.gc
                );


            if (gldElement) {

                gldElement.textContent =
                    Number.isFinite(
                        gldValue
                    )
                        ? gldValue.toFixed(2)
                        : "-";

            }


            if (gcElement) {

                gcElement.textContent =
                    Number.isFinite(
                        gldValue
                    )
                        ? converter(
                            gldValue
                        ).toFixed(2)
                        : "-";

            }

        }
    );


    const showFactor =
        document.getElementById(
            "showFactor"
        );


    if (showFactor) {

        showFactor.textContent =
            factor.toFixed(8);

    }


    setStatus(
        `Teste manual realizado · fator ${factor.toFixed(8)}`,
        "success"
    );

}


// ==========================================================
// BOTÃO ATUALIZAR
// ==========================================================

if (calculateButton) {

    calculateButton.addEventListener(
        "click",
        async function() {

            await carregarAnchor();

            await carregarGamma();

        }
    );

}


// ==========================================================
// BOTÃO MANUAL
// ==========================================================

if (manualButton) {

    manualButton.addEventListener(
        "click",
        calcularManual
    );

}


// ==========================================================
// BOTÕES 0DTE / 1DTE
// ==========================================================
//
// Você pode colocar no HTML:
//
// <button data-dte="0">0DTE</button>
// <button data-dte="1">1DTE</button>
//
// ==========================================================

document.addEventListener(
    "click",
    async function(event) {

        const button =
            event.target.closest(
                "[data-dte]"
            );


        if (!button) {
            return;
        }


        const dte =
            Number(
                button.dataset.dte
            );


        if (
            dte !== 0
            &&
            dte !== 1
        ) {
            return;
        }


        if (
            dte === selectedDTE
        ) {
            return;
        }


        selectedDTE =
            dte;


        console.log(
            "DTE selecionado:",
            selectedDTE
        );


        atualizarIndicadorDTE();


        await carregarGamma();

    }
);


// ==========================================================
// BOTÃO MAIS NÍVEIS
// ==========================================================

document.addEventListener(
    "click",
    function(event) {

        if (
            event.target
            &&
            event.target.id
            ===
            "moreLevelsButton"
        ) {

            mostrarTodosOsNiveis =
                !mostrarTodosOsNiveis;

            renderizar();

        }

    }
);


// ==========================================================
// VERIFICAR VIRADA DE HORA
// ==========================================================

let lastAnchorHour = null;


async function verificarVirada() {

    try {

        const response =
            await fetch(
                "/api/anchor?ts=" +
                Date.now(),
                {
                    cache: "no-store"
                }
            );


        const result =
            await response.json();


        if (
            !response.ok
            ||
            !result.ok
        ) {
            return;
        }


        const newAnchor =
            result.data;


        if (
            lastAnchorHour === null
        ) {

            lastAnchorHour =
                newAnchor.time;

            return;

        }


        if (
            newAnchor.time
            !==
            lastAnchorHour
        ) {

            console.log(
                "Nova hora-chave:",
                newAnchor.display_time
            );


            lastAnchorHour =
                newAnchor.time;


            await carregarAnchor();


            // ------------------------------------------------
            // IMPORTANTE:
            //
            // Se estiver no 0DTE, atualiza normalmente.
            //
            // Se estiver no 1DTE, também mantém o 1DTE.
            // ------------------------------------------------

            await carregarGamma();

        }

    }
    catch (error) {

        console.error(
            "Erro verificando virada:",
            error
        );

    }

}


// ==========================================================
// INICIALIZAÇÃO
// ==========================================================

async function iniciar() {

    console.log(
        "========== INICIANDO APP =========="
    );


    atualizarIndicadorDTE();


    await carregarAnchor();


    await carregarGamma();


    setInterval(
        verificarVirada,
        30000
    );

}





// ==========================================================
// INICIAR
// ==========================================================

iniciar();

// ==========================================================
// BOTÃO MINIMIZAR GAMMA FLIP
// ==========================================================

document.addEventListener(
    "click",
    function(event) {

        const button =
            event.target.closest(
                "#toggleGammaFlip"
            );

        if (!button) {
            return;
        }


        const panel =
            document.getElementById(
                "gammaFlipPanel"
            );


        const content =
            document.getElementById(
                "gammaFlipContent"
            );


        if (!panel || !content) {
            return;
        }


        const minimized =
            content.style.display === "none";


        if (minimized) {

            content.style.display = "";

            button.textContent = "−";

            button.title =
                "Minimizar Gamma Flip";

        }

        else {

            content.style.display = "none";

            button.textContent = "+";

            button.title =
                "Abrir Gamma Flip";

        }

    }
);

