import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AreaChart, Area, BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { Banknote, CheckCircle, FileText, Map, ShieldCheck, Smartphone, XCircle } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type Session = { token: string; user: { full_name: string; role: string; agent_id?: string | null } };
type Metric = { label: string; value: number; benchmark_delta: number; trend: number[] };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {})
    }
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const session = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      }).then((response) => {
        if (!response.ok) throw new Error("Invalid login");
        return response.json();
      });
      onLogin({ token: session.access_token, user: session.user });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main className="login">
      <form onSubmit={submit}>
        <h1>Agent Network Platform</h1>
        <label>Email<input value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error && <p className="error">{error}</p>}
        <button>Sign in</button>
        <small>Demo users: admin@example.com, reviewer@example.com, field@example.com, agent@example.com. Password: password.</small>
      </form>
    </main>
  );
}

function Dashboard({ session }: { session: Session }) {
  const [view, setView] = useState("float");
  const nav = [
    ["float", "Float", Banknote],
    ["reports", "Reports", FileText],
    ["customers", "KYC", ShieldCheck],
    ["map", "Map", Map],
    ["mobile", "Agent App", Smartphone],
    ["events", "Events", CheckCircle]
  ] as const;
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="mark" />
        <h2>{session.user.full_name}</h2>
        <p>{session.user.role}</p>
        {nav.map(([id, label, Icon]) => (
          <button className={view === id ? "active" : ""} key={id} onClick={() => setView(id)}>
            <Icon size={18} /> {label}
          </button>
        ))}
      </aside>
      <section className="workspace">
        {view === "float" && <FloatView session={session} />}
        {view === "reports" && <ReportsView session={session} />}
        {view === "customers" && <CustomersView session={session} />}
        {view === "map" && <MapView session={session} />}
        {view === "mobile" && <MobileView session={session} />}
        {view === "events" && <EventsView session={session} />}
      </section>
    </main>
  );
}

function FloatView({ session }: { session: Session }) {
  const client = useQueryClient();
  const reconciliation = useQuery({ queryKey: ["reconciliation"], queryFn: () => api<any[]>("/api/v1/float/reconciliation", session.token) });
  const requests = useQuery({ queryKey: ["requests"], queryFn: () => api<any[]>("/api/v1/float/requests", session.token) });
  const approve = useMutation({
    mutationFn: (id: string) => api(`/api/v1/float/requests/${id}/approve`, session.token, { method: "POST", body: JSON.stringify({ reviewer: session.user.full_name }) }),
    onSuccess: () => client.invalidateQueries()
  });
  const reject = useMutation({
    mutationFn: (id: string) => api(`/api/v1/float/requests/${id}/reject`, session.token, { method: "POST", body: JSON.stringify({ reviewer: session.user.full_name }) }),
    onSuccess: () => client.invalidateQueries()
  });
  return (
    <>
      <h1>Float Control & Reconciliation</h1>
      <div className="grid two">
        <table>
          <thead><tr><th>Agent</th><th>Field Agent</th><th>Cash In</th><th>Cash Out</th><th>Float Received</th><th>Balance Owed</th></tr></thead>
          <tbody>{reconciliation.data?.map((row) => <tr key={row.agent_id}><td>{row.agent_name}</td><td>{row.field_agent}</td><td>{row.cash_in_amount.toLocaleString()}</td><td>{row.cash_out_amount.toLocaleString()}</td><td>{row.float_received.toLocaleString()}</td><td className="owed">{row.balance_owed.toLocaleString()}</td></tr>)}</tbody>
        </table>
        <div className="panel">
          <h2>Review Requests</h2>
          {requests.data?.map((request) => <div className="request" key={request.id}><span className={request.status}>{request.status}</span><b>{request.amount.toLocaleString()} {request.request_type}</b><small>{request.agent_name}</small><button onClick={() => approve.mutate(request.id)}><CheckCircle size={16}/>Approve</button><button className="danger" onClick={() => reject.mutate(request.id)}><XCircle size={16}/>Reject</button></div>)}
        </div>
      </div>
    </>
  );
}

function ReportsView({ session }: { session: Session }) {
  const report = useQuery({ queryKey: ["report"], queryFn: () => api<{ metrics: Metric[] }>("/api/v1/reports/agent-network", session.token) });
  return (
    <>
      <h1>Agent Network Dashboard</h1>
      <div className="metrics">{report.data?.metrics.map((metric) => <article key={metric.label}><span>{metric.label}</span><b>{metric.label.includes("Rate") || metric.label.includes("Utilization") ? `${metric.value}%` : metric.value.toLocaleString()}</b><ResponsiveContainer height={90}><AreaChart data={metric.trend.map((value, index) => ({ index, value }))}><Area dataKey="value" stroke="#20c997" fill="#b9efe0" /></AreaChart></ResponsiveContainer></article>)}</div>
    </>
  );
}

function CustomersView({ session }: { session: Session }) {
  const client = useQueryClient();
  const customers = useQuery({ queryKey: ["customers"], queryFn: () => api<any[]>("/api/v1/customers", session.token) });
  const review = useMutation({
    mutationFn: (id: string) => api("/api/v1/kyc/reviews", session.token, { method: "POST", body: JSON.stringify({ customer_id: id, status: "approved", reviewer: session.user.full_name, comments: "Verified in operations console" }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["customers"] })
  });
  const customer = customers.data?.[0];
  if (!customer) return <p>No customers found.</p>;
  return <><h1>Customer: {customer.full_name}</h1><section className="profile"><div className="avatar" /><div><p><b>ID:</b> {customer.national_id}</p><p><b>Status:</b> {customer.compliance_status}</p><p><b>Birthday:</b> {customer.birthday}</p><p><b>Address:</b> {customer.address}</p><button onClick={() => review.mutate(customer.id)}>Review KYC</button></div></section></>;
}

function MapView({ session }: { session: Session }) {
  const map = useQuery({ queryKey: ["map"], queryFn: () => api<any>("/api/v1/maps/field-team", session.token) });
  return <><h1>Field Team Map</h1><div className="map">{map.data?.agents.map((agent: any, index: number) => <span key={agent.id} style={{ left: `${18 + (index * 11) % 70}%`, top: `${20 + (index * 17) % 58}%` }} title={agent.name} />)}</div></>;
}

function MobileView({ session }: { session: Session }) {
  const client = useQueryClient();
  const agentId = session.user.agent_id || "agent_neema";
  const report = useQuery({ queryKey: ["agent-report", agentId], queryFn: () => api<any>(`/api/v1/reports/agent/${agentId}`, session.token) });
  const tx = useMutation({
    mutationFn: () => api("/api/v1/transactions", session.token, { method: "POST", body: JSON.stringify({ agent_id: agentId, customer_phone: "782645673", transaction_type: "deposit", amount: 3400 }) }),
    onSuccess: () => client.invalidateQueries()
  });
  const chartData = useMemo(() => report.data?.transactions?.map((item: any, index: number) => ({ index, amount: item.amount })) || [], [report.data]);
  return <section className="phone"><h1>{report.data?.agent?.name || "Agent"}</h1><p>Float Balance <b>{report.data?.float_balance?.toLocaleString()}</b></p><p>Commission <b>{report.data?.commission_earned?.toLocaleString()}</b></p><button onClick={() => tx.mutate()}>Cash Deposit</button><ResponsiveContainer height={160}><BarChart data={chartData}><XAxis dataKey="index" /><YAxis /><Tooltip /><Bar dataKey="amount" fill="#20c997" /></BarChart></ResponsiveContainer></section>;
}

function EventsView({ session }: { session: Session }) {
  const events = useQuery({ queryKey: ["events"], queryFn: () => api<any[]>("/api/v1/events", session.token) });
  return <><h1>Event Audit Log</h1><div className="events">{events.data?.map((event) => <code key={event.id}>{event.topic} {event.name} {JSON.stringify(event.payload)}</code>)}</div></>;
}

function App() {
  const [session, setSession] = useState<Session | null>(() => {
    const stored = localStorage.getItem("session");
    return stored ? JSON.parse(stored) : null;
  });
  const login = (next: Session) => {
    localStorage.setItem("session", JSON.stringify(next));
    setSession(next);
  };
  return session ? <Dashboard session={session} /> : <Login onLogin={login} />;
}

createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>);

