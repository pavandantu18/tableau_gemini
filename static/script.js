// static/script.js – Reads Tableau worksheet data and talks to backend

let dashboard = null;

function logDebug(msg) {
  const dbg = document.getElementById("debug");
  dbg.textContent += msg + "\n";
  if (dbg.textContent.length > 2000) {
    dbg.textContent = dbg.textContent.substring(dbg.textContent.length - 1000);
  }
}

async function initializeTableau() {
  try {
    if (typeof tableau === 'undefined' || typeof tableau.extensions === 'undefined') {
        logDebug("Tableau API object not found. Ensure the script tag loads correctly.");
        return;
    }
    
    await tableau.extensions.initializeAsync();
    dashboard = tableau.extensions.dashboardContent.dashboard;
    logDebug("Extensions initialized. Dashboard: " + dashboard.name);

    const worksheetSelect = document.getElementById("worksheetSelect");
    worksheetSelect.innerHTML = "";

    dashboard.worksheets.forEach((ws) => {
      const opt = document.createElement("option");
      opt.value = ws.name;
      opt.textContent = ws.name;
      worksheetSelect.appendChild(opt);
    });

    if (dashboard.worksheets.length === 0) {
      logDebug("No worksheets found in dashboard. Please add data sheets.");
    }
  } catch (err) {
    console.error("Error initializing Tableau extensions:", err);
    logDebug("Error initializing Tableau extensions: " + err.toString());
  }
}

async function getWorksheetData(worksheetName) {
  const ws = dashboard.worksheets.find(w => w.name === worksheetName);

  if (!ws) {
    logDebug(`Worksheet '${worksheetName}' not found.`);
    return null;
  }

  logDebug("Reading full summary data from worksheet: " + ws.name);

  // Fetch underlying data, limited to 1000 rows to prevent massive payloads
  const summary = await ws.getSummaryDataAsync({
    ignoreSelection: false, 
    maxRows: 1000,          
  });

  const columns = summary.columns.map(col => col.fieldName);
  
  // Use formattedValue to send clean string data to Python
  const rows = summary.data.map(row =>
    row.map(cell => cell.formattedValue ?? cell.value)
  );

  logDebug(`Got ${rows.length} rows and ${columns.length} columns from ${ws.name}`);

  return {
    sheetName: ws.name,
    columns,
    rows,
  };
}

async function sendQuestion() {
  const messageBox = document.getElementById("message");
  const responseBox = document.getElementById("response");
  const sendBtn = document.getElementById("sendBtn");
  const worksheetSelect = document.getElementById("worksheetSelect");

  const question = messageBox.value.trim();
  if (!question) {
    responseBox.textContent = "Please type a question first.";
    return;
  }
  
  sendBtn.disabled = true;
  responseBox.textContent = "Thinking with Gemini… (Sending raw data for analysis)";

  try {
    const worksheetName = worksheetSelect.value;
    const tableauData = await getWorksheetData(worksheetName);

    const payload = {
      message: question,
      tableau: tableauData,
    };

    const res = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errDetail = await res.json().catch(() => res.text());
      console.error("Backend error:", errDetail);
      responseBox.textContent = `Error from backend (Status ${res.status}): ${JSON.stringify(errDetail)}`;
      return;
    }

    const data = await res.json();
    responseBox.textContent = data.response || "(No response received)";
  } catch (err) {
    console.error("Error sending question:", err);
    responseBox.textContent = "Error communicating with backend: " + err.toString();
  } finally {
    sendBtn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initializeTableau();

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.addEventListener("click", sendQuestion);
  
  const messageBox = document.getElementById("message");
  messageBox.addEventListener("keypress", (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); 
        sendQuestion();
    }
  });
});