const byId = (id) => document.getElementById(id);
const symbols = ["MSFT", "LSEG", "AZR", "CONTOSO", "FABRIKAM", "NORTHWIND"];

const state = {
  rumors: [],
  selectedRumor: null,
  holdings: [
    {symbol: "MSFT", allocation: 50},
    {symbol: "LSEG", allocation: 30},
    {symbol: "CONTOSO", allocation: 20},
  ],
  activeAnalysis: null,
  history: [],
};

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderHoldings() {
  const container = byId("holdings");
  container.replaceChildren();

  state.holdings.forEach((holding, index) => {
    const row = createElement("div", "holding-row");
    const select = document.createElement("select");
    symbols.forEach((symbol) => {
      const option = document.createElement("option");
      option.value = symbol;
      option.textContent = symbol;
      option.selected = symbol === holding.symbol;
      select.append(option);
    });
    select.addEventListener("change", (event) => {
      state.holdings[index].symbol = event.target.value;
    });

    const allocation = document.createElement("input");
    allocation.type = "number";
    allocation.min = "1";
    allocation.max = "100";
    allocation.value = holding.allocation;
    allocation.setAttribute("aria-label", `${holding.symbol} allocation`);
    allocation.addEventListener("input", (event) => {
      state.holdings[index].allocation = Number(event.target.value);
      updateAllocationTotal();
    });

    const suffix = createElement("span", "percent-suffix", "%");
    const remove = createElement("button", "icon-button", "×");
    remove.type = "button";
    remove.title = "Remove position";
    remove.disabled = state.holdings.length <= 2;
    remove.addEventListener("click", () => {
      state.holdings.splice(index, 1);
      renderHoldings();
    });

    row.append(select, allocation, suffix, remove);
    container.append(row);
  });
  byId("add-holding").disabled = state.holdings.length >= 6;
  updateAllocationTotal();
}

function updateAllocationTotal() {
  const total = state.holdings.reduce(
    (sum, holding) => sum + (Number(holding.allocation) || 0),
    0,
  );
  const indicator = byId("allocation-total");
  indicator.textContent = `${total}%`;
  indicator.classList.toggle("invalid", total !== 100);
  updateAnalyzeButton();
}

function renderRumors() {
  const feed = byId("rumor-feed");
  feed.replaceChildren();
  state.rumors.forEach((rumor) => {
    const card = createElement("button", "rumor-card");
    card.type = "button";
    card.classList.toggle(
      "selected",
      state.selectedRumor?.id === rumor.id,
    );
    card.classList.toggle("fresh", rumor.fresh === true);

    const meta = createElement("div", "rumor-meta");
    meta.append(
      createElement("span", `severity ${rumor.severity}`, rumor.severity),
      createElement(
        "span",
        `verification ${rumor.status}`,
        rumor.status,
      ),
    );
    card.append(
      meta,
      createElement("strong", "", rumor.headline),
      createElement("small", "", rumor.source),
    );
    card.addEventListener("click", () => selectRumor(rumor));
    feed.append(card);
  });
}

function selectRumor(rumor) {
  state.selectedRumor = rumor;
  renderRumors();
  renderSelectedRumor();
}

function currentRumor() {
  return state.selectedRumor;
}

function renderSelectedRumor() {
  const rumor = currentRumor();
  byId("selected-rumor-title").textContent = rumor
    ? rumor.headline
    : "Choose a rumor to investigate";
  byId("selected-rumor-details").textContent = rumor
    ? rumor.details || "Your specialist desks will investigate this signal."
    : "Your specialist team will map the signal to your portfolio.";
  updateAnalyzeButton();
}

function updateAnalyzeButton() {
  const total = state.holdings.reduce(
    (sum, holding) => sum + (Number(holding.allocation) || 0),
    0,
  );
  byId("analyze").disabled =
    !currentRumor() || total !== 100 || state.activeAnalysis?.status === "running";
}

function buildPortfolio() {
  return {
    customer_id: `LAB-${Date.now()}`,
    customer_name: byId("portfolio-name").value.trim() || "My Portfolio",
    risk_profile: byId("risk-profile").value,
    holdings: state.holdings.map((holding) => ({
      symbol: holding.symbol,
      allocation: Number(holding.allocation) / 100,
    })),
  };
}

async function startAnalysis() {
  const rumor = currentRumor();
  if (!rumor) return;

  byId("analyze").disabled = true;
  byId("analysis-workspace").classList.remove("hidden");
  byId("report").classList.add("hidden");
  byId("report-placeholder").classList.remove("hidden");
  byId("analysis-workspace").scrollIntoView({behavior: "smooth", block: "start"});

  const response = await fetch("/api/analyses", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({portfolio: buildPortfolio(), rumor}),
  });
  if (!response.ok) {
    showAnalysisError("The investigation could not be started.");
    return;
  }
  state.activeAnalysis = await response.json();
  renderAnalysis(state.activeAnalysis);
  await pollAnalysis(state.activeAnalysis.id);
}

async function pollAnalysis(analysisId) {
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 350));
    const response = await fetch(`/api/analyses/${analysisId}`);
    if (!response.ok) {
      showAnalysisError("The investigation could not be refreshed.");
      return;
    }
    const analysis = await response.json();
    state.activeAnalysis = analysis;
    renderAnalysis(analysis);
    if (analysis.status === "completed" || analysis.status === "failed") {
      await refreshHistory();
      updateAnalyzeButton();
      return;
    }
  }
}

function renderAnalysis(analysis) {
  const status = byId("analysis-state");
  status.textContent = analysis.status;
  status.className = `status-pill ${analysis.status}`;

  const stages = byId("analysis-stages");
  stages.replaceChildren();
  analysis.stages.forEach((stage) => {
    const card = createElement("div", `stage ${stage.status}`);
    const marker = createElement("span", "stage-marker");
    marker.textContent =
      stage.status === "completed"
        ? "✓"
        : stage.status === "running"
          ? "●"
          : stage.status === "failed"
            ? "!"
            : "○";
    const content = createElement("div");
    content.append(
      createElement("strong", "", stage.specialist),
      createElement("span", "", stage.title),
    );
    if (stage.summary) {
      content.append(createElement("p", "", stage.summary));
    }
    card.append(marker, content);
    stages.append(card);
  });

  if (analysis.status === "completed" && analysis.report) {
    renderReport(analysis);
  } else if (analysis.status === "failed") {
    showAnalysisError(analysis.error || "The investigation failed.");
  }
}

function renderReport(analysis) {
  const report = analysis.report;
  byId("report-placeholder").classList.add("hidden");
  byId("report").classList.remove("hidden");
  byId("report-headline").textContent = analysis.rumor.headline;
  byId("executive-summary").textContent = report.executive_summary;
  byId("risk-score").textContent = report.risk_score;
  byId("diversification-score").textContent = report.diversification_score;
  byId("confidence-score").textContent = report.confidence;
  byId("exposure-score").textContent =
    `${Math.round(report.affected_allocation * 100)}%`;
  byId("recommendation").textContent = report.recommendation;

  const impacts = byId("holding-impacts");
  impacts.replaceChildren();
  report.holding_impacts.forEach((impact) => {
    const row = createElement("div", "impact-row");
    const heading = createElement("div", "impact-heading");
    heading.append(
      createElement("strong", "", impact.symbol),
      createElement("span", `direction ${impact.direction}`, impact.direction),
    );
    const track = createElement("div", "impact-track");
    const fill = createElement("div", `impact-fill ${impact.direction}`);
    fill.style.width = `${Math.max(4, impact.impact_score)}%`;
    track.append(fill);
    row.append(
      heading,
      track,
      createElement("p", "", impact.rationale),
    );
    impacts.append(row);
  });

  const scenarios = byId("scenarios");
  scenarios.replaceChildren();
  report.scenarios.forEach((scenario) => {
    const card = createElement("article", `scenario ${scenario.name.toLowerCase()}`);
    card.append(
      createElement("span", "", `${scenario.name} · ${scenario.probability}%`),
      createElement("strong", "", scenario.portfolio_effect),
      createElement("p", "", scenario.narrative),
    );
    scenarios.append(card);
  });
}

function showAnalysisError(message) {
  byId("report-placeholder").classList.remove("hidden");
  byId("report-placeholder").replaceChildren(
    createElement("h2", "", "Investigation unavailable"),
    createElement("p", "", message),
  );
  state.activeAnalysis = null;
  updateAnalyzeButton();
}

async function refreshHistory() {
  const response = await fetch("/api/analyses");
  if (!response.ok) return;
  state.history = await response.json();
  const history = byId("history");
  history.replaceChildren();

  if (state.history.length === 0) {
    history.append(
      createElement("p", "muted", "Completed investigations will appear here."),
    );
    return;
  }

  state.history.slice(0, 6).forEach((analysis) => {
    const item = createElement("button", "history-item");
    item.type = "button";
    const details = createElement("div");
    details.append(
      createElement("strong", "", analysis.rumor.headline),
      createElement(
        "span",
        "",
        `${analysis.portfolio.customer_name} · ${analysis.status}`,
      ),
    );
    const score = createElement(
      "span",
      "history-score",
      analysis.report ? `Risk ${analysis.report.risk_score}` : "In progress",
    );
    item.append(details, score);
    item.addEventListener("click", () => {
      state.activeAnalysis = analysis;
      byId("analysis-workspace").classList.remove("hidden");
      renderAnalysis(analysis);
      byId("analysis-workspace").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
    history.append(item);
  });
}

function connectRumorFeed() {
  const feedStatus = byId("feed-status");
  const events = new EventSource("/api/rumors/stream");

  events.onopen = () => {
    feedStatus.classList.remove("disconnected");
    feedStatus.lastChild.textContent = " Live";
  };

  events.addEventListener("rumor", (event) => {
    const update = JSON.parse(event.data);
    const rumor = {...update.rumor, fresh: true};
    const existingIndex = state.rumors.findIndex(
      (candidate) => candidate.id === rumor.id,
    );

    if (existingIndex >= 0) {
      state.rumors.splice(existingIndex, 1);
    }
    state.rumors.unshift(rumor);
    state.rumors = state.rumors.slice(0, 12);

    if (state.selectedRumor?.id === rumor.id) {
      state.selectedRumor = rumor;
      renderSelectedRumor();
    }
    renderRumors();
    window.setTimeout(() => {
      const current = state.rumors.find(
        (candidate) => candidate.id === rumor.id,
      );
      if (current) current.fresh = false;
      renderRumors();
    }, 1800);
  });

  events.onerror = () => {
    feedStatus.classList.add("disconnected");
    feedStatus.lastChild.textContent = " Reconnecting";
  };
}

async function initialize() {
  renderHoldings();
  const [rumorResponse] = await Promise.all([
    fetch("/api/rumors"),
    refreshHistory(),
  ]);
  if (rumorResponse.ok) {
    state.rumors = await rumorResponse.json();
    state.selectedRumor = state.rumors[0] || null;
    renderRumors();
    renderSelectedRumor();
  }
  connectRumorFeed();

  const marketResponse = await fetch("/api/market");
  if (marketResponse.ok) {
    const market = await marketResponse.json();
    byId("market-status").textContent = market.status;
  }
}

byId("add-holding").addEventListener("click", () => {
  const unused = symbols.find(
    (symbol) => !state.holdings.some((holding) => holding.symbol === symbol),
  );
  state.holdings.push({symbol: unused || symbols[0], allocation: 0});
  renderHoldings();
});

byId("analyze").addEventListener("click", startAnalysis);

initialize();
