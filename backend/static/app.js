const api = (path, options) => fetch(`/api/v1${path}`, {
  headers: { "Content-Type": "application/json" },
  ...options
}).then((response) => {
  if (!response.ok) throw new Error(`API failed: ${response.status}`);
  return response.json();
});

const money = (value) => Number(value).toLocaleString();
let activeView = "reconciliation";
let activeMobile = "home";

async function renderReconciliation() {
  const [rows, requests] = await Promise.all([
    api("/float/reconciliation"),
    api("/float/requests")
  ]);
  document.querySelector("#desktop-view").innerHTML = `
    <div class="title-card">Reconciliation</div>
    <div class="layout-2">
      <div class="data-card">
        <table class="table">
          <thead>
            <tr>
              <th>Agent Name</th><th>Field Agent</th><th>Cash in Amt</th><th>Cash out Amt</th>
              <th>Cash received</th><th>Cash returned</th><th>Float received</th><th>Balance owed</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${row.agent_name}</td><td>${row.field_agent}</td><td>${money(row.cash_in_amount)}</td>
                <td>${money(row.cash_out_amount)}</td><td>${money(row.cash_received)}</td>
                <td>${money(row.cash_returned)}</td><td>${money(row.float_received)}</td>
                <td class="owed">${money(row.balance_owed)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <aside>
        <div class="title-card">Review Requests</div>
        <div class="request-list">
          ${requests.map((request) => `
            <div class="request-row">
              <span class="pill ${request.status}">${request.status}</span>
              <span>${money(request.amount)} ${request.request_type}<br><b>${request.agent_name}</b></span>
              <span>
                <button class="action" onclick="approveRequest('${request.id}')">Approve</button>
                <button class="action danger" onclick="rejectRequest('${request.id}')">Reject</button>
              </span>
            </div>
          `).join("")}
        </div>
      </aside>
    </div>
  `;
}

async function renderReports() {
  const report = await api("/reports/agent-network");
  document.querySelector("#desktop-view").innerHTML = `
    <div class="title-card">Agent Network Dashboard</div>
    <div class="toolbar"><span>Time Period: Month</span><span>Benchmark: Previous period</span><span>Selected dates: Dec 2023</span></div>
    <div class="metrics">
      ${report.metrics.slice(0, 6).map((metric) => `
        <article class="metric-card">
          <span>${metric.label}</span>
          <b>${metric.label.includes("Rate") || metric.label.includes("Utilization") ? metric.value + "%" : money(metric.value)}</b>
          <small>${metric.benchmark_delta}% vs benchmark</small>
          <div class="spark">${metric.trend.map((point) => `<i style="height:${Math.max(point, 8)}px"></i>`).join("")}</div>
        </article>
      `).join("")}
    </div>
  `;
}

async function renderCustomers() {
  const customers = await api("/customers");
  const customer = customers[0];
  document.querySelector("#desktop-view").innerHTML = `
    <div class="title-card">Customer: ${customer.full_name}</div>
    <div class="toolbar"><b class="green">Overview</b><button class="action" onclick="reviewKyc('${customer.id}')">Review KYC</button></div>
    <div class="profile-grid">
      <div class="profile-card">
        <div class="avatar"></div>
        <b>UUID</b><p>${customer.id}</p>
        <b>Contacts</b><p>${customer.phone}</p>
      </div>
      <div class="profile-card">
        ${[
          ["Customer name from KYC", customer.name],
          ["Customer surname from KYC", customer.surname],
          ["ID Number from KYC", customer.national_id],
          ["Customer birthday from KYC", customer.birthday],
          ["Compliance status", customer.compliance_status],
          ["KYC collected by", customer.kyc_collected_by],
          ["Verified at", customer.verified_at || "--"],
          ["Address", customer.address]
        ].map(([label, value]) => `<div class="field-row"><span>${label}</span><b>${value}</b></div>`).join("")}
      </div>
    </div>
  `;
}

async function renderMap() {
  const data = await api("/maps/field-team");
  document.querySelector("#desktop-view").innerHTML = `
    <div class="title-card">Field Team Map</div>
    <div class="map">
      <div class="map-controls">
        <p><input type="checkbox" checked> Show Activity</p>
        <p><input type="checkbox" checked> Show Field Agents</p>
        <p><input type="checkbox" checked> Show Agents</p>
      </div>
      ${data.agents.map((agent) => {
        const left = 45 + (agent.longitude + 16.65) * 400;
        const top = 300 - (agent.latitude - 13.42) * 900;
        return `<span class="pin" title="${agent.name}" style="left:${Math.max(4, Math.min(94, left))}%;top:${Math.max(8, Math.min(88, top))}%"></span>`;
      }).join("")}
    </div>
  `;
}

async function renderEvents() {
  const events = await api("/events");
  document.querySelector("#desktop-view").innerHTML = `
    <div class="title-card">Kafka-style Event Log</div>
    <div class="event-log">
      ${events.slice().reverse().map((event) => `<code>${event.created_at} ${event.name} ${JSON.stringify(event.payload)}</code>`).join("")}
    </div>
  `;
}

async function renderMobileHome() {
  const report = await api("/reports/agent/agent_neema");
  document.querySelector("#phone-title").textContent = "Neema Diallo";
  document.querySelector("#phone-view").innerHTML = `
    <section class="agent-summary">
      <h2>${report.agent.name}</h2>
      <p>Float Balance <b class="green">${money(report.float_balance)}</b></p>
      <p>Commission Earned <b class="orange">${money(report.commission_earned)}</b></p>
    </section>
    <div class="tiles">
      ${["Cash Deposit", "Cash Withdraw", "Customer Registration", "Sell Airtime", "Float Transfer", "Float request"].map((label) => `<button class="tile" onclick="quickTransaction('${label}')">${label}</button>`).join("")}
    </div>
  `;
}

async function renderMobileTransactions() {
  const transactions = await api("/transactions");
  document.querySelector("#phone-title").textContent = "Transactions";
  document.querySelector("#phone-view").innerHTML = transactions
    .filter((tx) => tx.agent_id === "agent_neema")
    .map((tx) => `<div class="tx-row"><span><b>${tx.customer_phone}</b><br><small>${new Date(tx.created_at).toLocaleString()}</small></span><span><b>${money(tx.amount)}</b><br><small class="orange">+ ${money(tx.commission)}</small></span></div>`)
    .join("");
}

async function renderMobileReport() {
  const report = await api("/reports/agent/agent_neema");
  document.querySelector("#phone-title").textContent = "Reports";
  document.querySelector("#phone-view").innerHTML = `
    <h3>Commission Payments</h3>
    ${report.transactions.map((tx) => `<div class="commission-row"><span><b>Commission Amount</b><br><span class="orange">${money(tx.commission)}</span><br><small>${tx.transaction_type}</small></span><span>${new Date(tx.created_at).toLocaleDateString()}<br><span class="pill approved">Paid</span></span></div>`).join("")}
  `;
}

async function renderMobileProfile() {
  const customers = await api("/customers");
  document.querySelector("#phone-title").textContent = "Customer Profile Picture";
  document.querySelector("#phone-view").innerHTML = `
    <p>First, please take a photo of the customer. Please make sure their whole face is visible.</p>
    <div class="avatar"></div>
    <button class="action" style="width:100%;font-size:24px">Save Photo</button>
    <h3>Guidelines</h3>
    <p>Customer should be facing camera. No hats or sunglasses. Facial features should be clear.</p>
    <p><b>KYC customer:</b> ${customers[0].full_name}</p>
  `;
}

async function approveRequest(id) {
  await api(`/float/requests/${id}/approve`, { method: "POST", body: JSON.stringify({ reviewer: "operations-admin" }) });
  await renderAll();
}

async function rejectRequest(id) {
  await api(`/float/requests/${id}/reject`, { method: "POST", body: JSON.stringify({ reviewer: "operations-admin" }) });
  await renderAll();
}

async function reviewKyc(id) {
  await api("/kyc/reviews", { method: "POST", body: JSON.stringify({ customer_id: id, status: "approved", reviewer: "Neema Diallo", comments: "Photo and ID verified" }) });
  await renderAll();
}

async function quickTransaction(label) {
  const type = label.includes("Withdraw") ? "withdrawal" : label.includes("Airtime") ? "airtime" : label.includes("Registration") ? "registration" : "deposit";
  await api("/transactions", { method: "POST", body: JSON.stringify({ agent_id: "agent_neema", customer_phone: "782645673", transaction_type: type, amount: 3400 }) });
  activeMobile = "transactions";
  await renderAll();
}

async function renderDesktop() {
  if (activeView === "reconciliation") return renderReconciliation();
  if (activeView === "reports") return renderReports();
  if (activeView === "customers") return renderCustomers();
  if (activeView === "map") return renderMap();
  return renderEvents();
}

async function renderMobile() {
  if (activeMobile === "transactions") return renderMobileTransactions();
  if (activeMobile === "report") return renderMobileReport();
  if (activeMobile === "profile") return renderMobileProfile();
  return renderMobileHome();
}

async function renderAll() {
  await Promise.all([renderDesktop(), renderMobile()]);
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === activeView));
  document.querySelectorAll("[data-mobile]").forEach((button) => button.classList.toggle("active", button.dataset.mobile === activeMobile));
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    activeView = button.dataset.view;
    renderAll();
  });
});

document.querySelectorAll("[data-mobile]").forEach((button) => {
  button.addEventListener("click", () => {
    activeMobile = button.dataset.mobile;
    renderAll();
  });
});

renderAll();

