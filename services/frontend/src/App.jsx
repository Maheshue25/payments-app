import { useState, useEffect } from "react";

const API_BASE = "/api";
const CURRENT_USER_ID = "ACC-904812"; // Matches your Receive Money account ID

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [apiStatus, setApiStatus] = useState("Checking backend...");
  const [totalTransactions, setTotalTransactions] = useState(0);

  // Form states for Send Money
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  // Function to fetch status and transaction count
  const fetchOverview = async () => {
    try {
      const res = await fetch(`${API_BASE}/`);
      if (!res.ok) throw new Error("API not responding");
      const data = await res.json();
      setApiStatus(data.message || "Connected to Backend");
      if (data.total_transactions_in_db !== undefined) {
        setTotalTransactions(data.total_transactions_in_db);
      }
    } catch {
      setApiStatus("Failed to connect to FastAPI");
    }
  };

  // Poll FastAPI on mount and every 4 seconds to observe real-time PostgreSQL updates
  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 4000);
    return () => clearInterval(interval);
  }, []);

  // Handle Send Money
  const handleSendMoney = async (e) => {
    e.preventDefault();
    setStatusMessage("Processing...");

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: parseFloat(amount),
          type: "transfer",
          sender_id: CURRENT_USER_ID,
          recipient_id: recipient.trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          typeof errorData.detail === "string"
            ? errorData.detail
            : "Transaction failed validation"
        );
      }

      const result = await response.json();
      setStatusMessage(`Success! Transferred $${result.amount} to ${result.recipient_id}.`);
      setRecipient("");
      setAmount("");
      fetchOverview();
    } catch (err) {
      setStatusMessage(`Error: ${err.message}`);
    }
  };

  return (
    <div style={styles.container}>
      {/* Top Navigation */}
      <header style={styles.header}>
        <h2>Finance Dashboard</h2>
        <nav style={styles.nav}>
          <button
            style={activeTab === "dashboard" ? styles.activeTab : styles.tab}
            onClick={() => setActiveTab("dashboard")}
          >
            Overview
          </button>
          <button
            style={activeTab === "send" ? styles.activeTab : styles.tab}
            onClick={() => setActiveTab("send")}
          >
            Send Money
          </button>
          <button
            style={activeTab === "receive" ? styles.activeTab : styles.tab}
            onClick={() => setActiveTab("receive")}
          >
            Receive Money
          </button>
        </nav>
      </header>

      {/* Main Body */}
      <main style={styles.main}>
        {activeTab === "dashboard" && (
          <section style={styles.card}>
            <h3>Account Overview</h3>
            <p><strong>API Status:</strong> {apiStatus}</p>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Total Transactions in DB</span>
              <span style={styles.statValue}>{totalTransactions}</span>
            </div>
          </section>
        )}

        {activeTab === "send" && (
          <section style={styles.card}>
            <h3>Transfer Funds</h3>
            <form onSubmit={handleSendMoney} style={styles.form}>
              <label style={styles.label}>Recipient Name or ID</label>
              <input
                type="text"

                required
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                style={styles.input}
                placeholder="e.g. usr_1a2b3c4d"
              />

              <label style={styles.label}>Amount ($)</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                style={styles.input}
                placeholder="0.00"
              />

              <button type="submit" style={styles.primaryButton}>
                Confirm Transfer
              </button>
            </form>
            {statusMessage && <p style={styles.status}>{statusMessage}</p>}
          </section>
        )}

        {activeTab === "receive" && (
          <section style={styles.card}>
            <h3>Receive Money</h3>
            <p>Share your payment endpoint or account details to receive funds.</p>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Your Account ID</span>
              <span style={styles.statValue}>{CURRENT_USER_ID}</span>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

const styles = {
  container: { fontFamily: "sans-serif", maxWidth: "700px", margin: "40px auto", padding: "0 20px" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #ddd", paddingBottom: "15px" },
  nav: { display: "flex", gap: "10px" },
  tab: { padding: "8px 14px", border: "1px solid #ccc", background: "#f8f8f8", cursor: "pointer", borderRadius: "4px" },
  activeTab: { padding: "8px 14px", border: "1px solid #0056b3", background: "#007bff", color: "#fff", cursor: "pointer", borderRadius: "4px" },
  main: { marginTop: "25px" },
  card: { background: "#fff", border: "1px solid #e0e0e0", borderRadius: "8px", padding: "20px", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" },
  statBox: { marginTop: "15px", padding: "15px", background: "#f4f6f8", borderRadius: "6px" },
  statLabel: { display: "block", color: "#666", fontSize: "14px" },
  statValue: { display: "block", fontSize: "24px", fontWeight: "bold", marginTop: "5px" },
  form: { display: "flex", flexDirection: "column", gap: "12px", marginTop: "15px" },
  label: { fontSize: "14px", fontWeight: "600" },
  input: { padding: "10px", fontSize: "14px", border: "1px solid #ccc", borderRadius: "4px" },
  primaryButton: { padding: "12px", background: "#28a745", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "15px", fontWeight: "bold" },
  status: { marginTop: "12px", fontWeight: "bold" },
};