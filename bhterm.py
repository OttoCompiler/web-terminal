#!/usr/bin/env python3


import subprocess
import shlex
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime

app = Flask(__name__)


HISTORY = []
HISTORY_INDEX = -1


BLACKLIST = [
    "sudo", "rm -rf", "rm -r /", "shutdown", "poweroff",
    "reboot", "mkfs", "mount", "umount", "dd", "chown /",
    "chmod 777 /", "passwd", "useradd", "usermod",
]


WHITELIST = [
    "ls", "cat", "echo", "pwd", "whoami", "df", "du",
    "ps", "date", "uptime", "head", "tail", "grep",
    "uname", "top -l 1", "ifconfig", "ipconfig",
]


def safe_command(cmd: str):
    lower = cmd.lower().strip()
    for bad in BLACKLIST:
        if bad in lower:
            return False, f"Command blocked: contains forbidden pattern '{bad}'"

    allowed = False
    for good in WHITELIST:
        if lower.startswith(good):
            allowed = True
            break

    if not allowed:
        return False, "Command not in whitelist. Allowed: " + ", ".join(WHITELIST)

    return True, None


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OttoCompiler's Sandboxed WebTerminal</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
:root {
    --bg: #0d0f14;
    --panel: #1a1c22;
    --accent: #f25f4c;
    --accent2: #ffd166;
    --text: #eaf0f7;
    --muted: #8f9bb3;
    --radius: 18px;
    font-family: "JetBrains Mono", monospace;
}

body {
    margin: 0;
    background:
       radial-gradient(900px 400px at 10% 20%, rgba(242,95,76,0.06), transparent 50%),
       radial-gradient(800px 400px at 80% 80%, rgba(255,209,102,0.05), transparent 50%),
       var(--bg);
    color: var(--text);
    padding: 32px;
}

h1 {
    margin: 0;
    font-size: 28px;
}

header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 22px;
    align-items: center;
}

.logo {
    width: 54px;
    height: 54px;
    border-radius: 14px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #111;
    transform: rotate(-6deg);
    box-shadow: 0 7px 20px rgba(0,0,0,0.45);
}

.panel {
    background: var(--panel);
    padding: 18px;
    border-radius: var(--radius);
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
}

#terminal {
    height: 480px;
    overflow-y: auto;
    white-space: pre-wrap;
    font-size: 18px;   /* LARGER FONT */
    line-height: 1.45;
}

.input-row {
    display: flex;
    gap: 10px;
    margin-top: 16px;
}

input {
    flex: 1;
    padding: 10px;
    border-radius: 10px;
    background: #00000040;
    border: 1px solid rgba(255,255,255,0.1);
    color: var(--text);
    font-size: 16px;
    outline: none;
}

.btn {
    padding: 10px 18px;
    border-radius: 12px;
    background: var(--accent);
    color: #111;
    border: none;
    cursor: pointer;
    font-weight: 800;
    transition: 0.15s ease;
}

.btn:hover {
    transform: translateY(-2px);
}

.history {
    margin-top: 20px;
    color: var(--muted);
}
</style>

<script>
let historyIndex = -1;
let historyData = [];

// Load history initially
async function loadHistory() {
    let h = await fetch("/history").then(r => r.json());
    historyData = h;
    document.getElementById("history").textContent = h.join("\\n");
}

// Handle UP / DOWN arrow navigation
document.addEventListener("keydown", (e) => {
    let input = document.getElementById("cmd");

    if (e.key === "ArrowUp") {
        e.preventDefault();
        if (historyData.length === 0) return;
        if (historyIndex < historyData.length - 1) historyIndex++;
        input.value = historyData[historyData.length - 1 - historyIndex].split("  ").slice(1).join(" ");
    }

    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (historyIndex > 0) {
            historyIndex--;
            input.value = historyData[historyData.length - 1 - historyIndex].split("  ").slice(1).join(" ");
        } else {
            historyIndex = -1;
            input.value = "";
        }
    }
});


// Run command
async function runCmd() {
    let cmd = document.getElementById("cmd").value;
    if (!cmd.trim()) return;

    let res = await fetch("/run", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({cmd})
    });

    let data = await res.json();

    let t = document.getElementById("terminal");

    // Use innerHTML so newline → <br> properly
    t.innerHTML += "<div>&gt; " + cmd + "</div>";
    t.innerHTML += "<div>" + data.output.replace(/\\n/g, "<br>") + "</div><br>";

    t.scrollTop = t.scrollHeight;

    loadHistory();
    document.getElementById("cmd").value = "";
    historyIndex = -1;
}

window.onload = loadHistory;
</script>

</head>
<body>

<header>
    <div style="display:flex;gap:14px;align-items:center">
        <div class="logo">OC</div>
        <h1 style="width: 80vw;">OttoCompiler's Sandboxed WebTerminal</h1>
        <button class="btn"> View Github </button>
    </div>
</header>

<div class="panel">
    <div id="terminal"></div>

    <div class="input-row">
        <input id="cmd" placeholder="Enter a safe command (e.g., ls, pwd, date)">
        <button class="btn" onclick="runCmd()">Run</button>
    </div>
</div>

<div class="panel history">
    <b>Command History:</b>
    <pre id="history"></pre>
</div>

</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/run", methods=["POST"])
def run():
    data = request.json
    cmd = data.get("cmd", "").strip()

    ok, reason = safe_command(cmd)
    if not ok:
        output = f"[ERROR] {reason}"
        HISTORY.append(f"{datetime.now().strftime('%H:%M:%S')}  BLOCKED: {cmd}")
        return jsonify({"output": output})

    try:
        proc = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
        )
        output = proc.stdout + proc.stderr
    except Exception as e:
        output = f"[Exception] {e}"

    HISTORY.append(f"{datetime.now().strftime('%H:%M:%S')}  {cmd}")

    return jsonify({"output": output})


@app.route("/history")
def history():
    return jsonify(HISTORY[-40:])  # last 40



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5025, debug=True)
