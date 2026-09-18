# main.py — the web app (API + login/register + a good-looking screen)

import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from matching import rank_matches
from auth import login_user, create_token, get_current_user, register_user

app = FastAPI(title="CapMatch")

with open("issuers.json") as f:
    ISSUERS = json.load(f)
with open("investors.json") as f:
    INVESTORS = json.load(f)


# ---------- REGISTER (sign up) ----------
class RegisterBody(BaseModel):
    username: str
    password: str
    role: str = "issuer"   # "issuer" or "investor"


@app.post("/register")
def register(body: RegisterBody):
    ok, message = register_user(body.username, body.password, body.role)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    # Auto-login: give them a token straight away so they can start using it.
    token = create_token(body.username, body.role)
    return {"access_token": token, "token_type": "bearer", "role": body.role,
            "message": message}


# ---------- LOGIN ----------
# ---------- LOGIN ----------
@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = login_user(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(form.username, user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

# ---------- API endpoints (PROTECTED — need a valid token) ----------
@app.get("/issuers")
def get_issuers(user=Depends(get_current_user)):
    return ISSUERS


@app.get("/investors")
def get_investors(user=Depends(get_current_user)):
    return INVESTORS


@app.get("/match/{issuer_id}")
def match(issuer_id: str, top_k: int = 5, user=Depends(get_current_user)):
    issuer = next((i for i in ISSUERS if i["id"] == issuer_id), None)
    if issuer is None:
        return {"error": f"Issuer '{issuer_id}' not found"}
    results = rank_matches(issuer, INVESTORS, top_k=top_k)
    return {"issuer": issuer, "matches": results, "requested_by": user["username"]}

# ---------- AGENTIC matching (LangGraph) ----------
@app.get("/agent/{issuer_id}")
def agent_match(issuer_id: str, top_k: int = 4, user=Depends(get_current_user)):
    """Run the autonomous LangGraph agent: ingest -> retrieve (tool) ->
    score (tool) -> reflect/loop -> explain."""
    from matching_agent_graph import run_agent
    result = run_agent(issuer_id, top_k=top_k)
    result["requested_by"] = user["username"]
    return result

# ---------- The good-looking screen ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CapMatch — Investor Matching</title>
<style>
  :root{
    --bg:#0b1120; --panel:#141d33; --panel2:#1c2842; --line:#2a3a5c;
    --txt:#eaf0fb; --mut:#93a5c7; --acc:#5b8cff; --acc2:#8a5cff;
    --good:#37d99a; --warn:#ffb454; --bad:#ff6b81;
  }
  *{box-sizing:border-box; margin:0; padding:0}
  body{font-family:'Segoe UI',system-ui,sans-serif; background:
      radial-gradient(1200px 500px at 80% -10%, #1a2748 0, transparent 60%), var(--bg);
    background-color:var(--bg); color:var(--txt); min-height:100vh}
  .top{padding:20px 34px; border-bottom:1px solid var(--line);
    display:flex; align-items:center; gap:16px;
    background:linear-gradient(90deg,#0d1526,#16213f)}
  .logo{width:46px; height:46px; border-radius:12px; font-weight:800; font-size:22px;
    display:flex; align-items:center; justify-content:center; color:#fff;
    background:linear-gradient(135deg,var(--acc),var(--acc2)); box-shadow:0 8px 24px rgba(91,140,255,.4)}
  h1{font-size:22px; letter-spacing:.3px}
  .tag{color:var(--mut); font-size:13px; margin-top:3px}
  .who{margin-left:auto; font-size:13px; color:var(--mut)}
  .who b{color:var(--good)}
  .logout{margin-left:12px; padding:7px 14px; font-size:12px; border-radius:8px; cursor:pointer;
    border:1px solid var(--line); background:var(--panel2); color:var(--txt)}
  .wrap{max-width:1080px; margin:0 auto; padding:26px 20px; display:grid;
    grid-template-columns:330px 1fr; gap:22px}
  @media(max-width:820px){.wrap{grid-template-columns:1fr}}
  .card{background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:22px}
  .card h2{font-size:12px; text-transform:uppercase; letter-spacing:.12em; color:var(--mut); margin-bottom:16px}
  label{display:block; font-size:12px; color:var(--mut); margin:14px 0 6px}
  select,input{width:100%; padding:12px; background:var(--panel2); border:1px solid var(--line);
    border-radius:10px; color:var(--txt); font-size:15px; outline:none}
  select:focus,input:focus{border-color:var(--acc)}
  .issuer-box{margin-top:16px; padding:14px; background:var(--panel2); border-radius:12px;
    border:1px solid var(--line); font-size:13px; line-height:1.55}
  .issuer-box b{color:#cfe0ff}
  .chip{display:inline-block; font-size:11px; padding:3px 9px; border-radius:20px;
    background:transparent; border:1px solid var(--line); color:var(--mut); margin:4px 4px 0 0}
  button.primary{margin-top:20px; width:100%; padding:14px; border:0; border-radius:12px; cursor:pointer;
    background:linear-gradient(135deg,var(--acc),var(--acc2)); color:#fff; font-weight:700; font-size:15px;
    box-shadow:0 8px 22px rgba(91,140,255,.35); transition:.15s}
  button.primary:hover{filter:brightness(1.1); transform:translateY(-1px)}
  .status{color:var(--mut); font-size:14px; margin-bottom:16px}
  .result{background:var(--panel); border:1px solid var(--line); border-radius:18px;
    padding:20px; margin-bottom:16px; position:relative; overflow:hidden}
  .result.win{border-color:var(--good); box-shadow:0 0 0 1px rgba(55,217,154,.3)}
  .rank{position:absolute; top:16px; right:18px; font-size:12px; color:var(--mut)}
  .rname{font-size:18px; font-weight:700}
  .rid{font-size:12px; color:var(--mut); margin-left:8px; font-weight:400}
  .scorewrap{display:flex; align-items:center; gap:14px; margin:14px 0}
  .scoreval{font-size:30px; font-weight:800; min-width:78px}
  .bar{flex:1; height:12px; border-radius:8px; background:var(--panel2); overflow:hidden}
  .bar > i{display:block; height:100%; border-radius:8px;
    background:linear-gradient(90deg,var(--acc),var(--good))}
  .factors{display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px}
  @media(max-width:560px){.factors{grid-template-columns:1fr}}
  .factor{background:var(--panel2); border:1px solid var(--line); border-radius:12px; padding:11px 13px}
  .frow{display:flex; justify-content:space-between; align-items:center}
  .fname{text-transform:capitalize; font-weight:600; font-size:13px}
  .fpct{font-weight:800; font-size:13px}
  .hi{color:var(--good)} .mid{color:var(--warn)} .lo{color:var(--bad)}
  .fdetail{color:var(--mut); font-size:12px; margin-top:5px; line-height:1.45}
  .empty{color:var(--mut); text-align:center; padding:50px 20px; font-size:15px}
  .badge{display:inline-block; background:rgba(55,217,154,.15); color:var(--good);
    font-size:11px; font-weight:700; padding:3px 10px; border-radius:20px; margin-left:8px}

  /* Login overlay */
  .overlay{position:fixed; inset:0; background:rgba(6,10,20,.88); backdrop-filter:blur(6px);
    display:flex; align-items:center; justify-content:center; z-index:50}
  .login{width:360px; max-width:92vw; background:var(--panel); border:1px solid var(--line);
    border-radius:20px; padding:30px; box-shadow:0 30px 80px rgba(0,0,0,.5)}
  .login .logo{margin:0 auto 16px}
  .login h3{text-align:center; font-size:20px; margin-bottom:4px}
  .login p{text-align:center; color:var(--mut); font-size:13px; margin-bottom:18px}
  .login .err{color:var(--bad); font-size:13px; text-align:center; min-height:18px; margin-top:10px}
  .hint{margin-top:16px; font-size:12px; color:var(--mut); text-align:center; line-height:1.6;
    background:var(--panel2); border:1px solid var(--line); border-radius:10px; padding:10px}
  .hidden{display:none}
</style>
</head>
<body>

  <!-- LOGIN / REGISTER SCREEN -->
  <div class="overlay" id="loginScreen">
    <div class="login">
      <div class="logo">C</div>
      <h3 id="authTitle">Sign in to CapMatch</h3>
      <p id="authSub">Secure access — JWT authentication</p>

      <label>Username</label>
      <input id="u" placeholder="e.g. rahul123" onkeydown="if(event.key==='Enter')submitAuth()">

      <label>Password</label>
      <input id="p" type="password" placeholder="your password" onkeydown="if(event.key==='Enter')submitAuth()">

      <!-- Role picker: only shown on Register -->
      <div id="roleRow" style="display:none">
        <label>I am a…</label>
        <select id="role">
          <option value="issuer">Issuer (company seeking capital)</option>
          <option value="investor">Investor (providing capital)</option>
        </select>
      </div>

      <button class="primary" id="authBtn" onclick="submitAuth()">🔒 Sign in</button>
      <div class="err" id="loginErr"></div>

      <div class="hint">
        <span id="toggleText">New here?</span>
        <a href="#" onclick="toggleMode();return false;" id="toggleLink"
           style="color:var(--acc); font-weight:700; text-decoration:none">Create an account</a>
      </div>
    </div>
  </div>

  <!-- MAIN APP (hidden until logged in) -->
  <div id="app" class="hidden">
    <div class="top">
      <div class="logo">C</div>
      <div>
        <h1>CapMatch</h1>
        <div class="tag">Agentic AI matching — connecting issuers with investors, explained.</div>
      </div>
      <div class="who">Signed in as <b id="whoName"></b>
        <button class="logout" onclick="logout()">Log out</button></div>
    </div>

    <div class="wrap">
      <div class="card">
        <h2>Find investors for an issuer</h2>
        <label>Issuer (company seeking capital)</label>
        <select id="issuer"></select>
        <div class="issuer-box" id="issuerInfo">Loading…</div>
        <label>How many matches to show</label>
        <input id="topk" type="number" value="4" min="1" max="10">
        <button class="primary" onclick="runMatch()">⚡ Find best investors</button>
      </div>

      <div>
        <div class="status" id="status">Pick an issuer and click the button.</div>
        <div id="results">
          <div class="empty">🔍 Your ranked matches will appear here.</div>
        </div>
      </div>
    </div>
  </div>

<script>
let issuers = [];
let TOKEN = null;
let mode = 'login';   // 'login' or 'register'

// Switch between Sign in and Create account
function toggleMode(){
  mode = (mode === 'login') ? 'register' : 'login';
  const isReg = mode === 'register';
  document.getElementById('authTitle').textContent = isReg ? 'Create your account' : 'Sign in to CapMatch';
  document.getElementById('authSub').textContent   = isReg ? 'Register to start matching' : 'Secure access — JWT authentication';
  document.getElementById('authBtn').textContent   = isReg ? '✨ Create account' : '🔒 Sign in';
  document.getElementById('roleRow').style.display  = isReg ? 'block' : 'none';
  document.getElementById('toggleText').textContent = isReg ? 'Already have an account?' : 'New here?';
  document.getElementById('toggleLink').textContent = isReg ? 'Sign in instead' : 'Create an account';
  document.getElementById('loginErr').textContent = '';
}

// One button handles both modes
async function submitAuth(){
  if(mode === 'register') await doRegister();
  else await doLogin();
}

function enterApp(username, role){
  document.getElementById('whoName').textContent = username + ' (' + role + ')';
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  load();
}

// ---- LOGIN ----
async function doLogin(){
  const u = document.getElementById('u').value;
  const p = document.getElementById('p').value;
  const body = new URLSearchParams({username:u, password:p});
  const res = await fetch('/login', {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'}, body});
  if(!res.ok){
    document.getElementById('loginErr').textContent = '❌ Invalid username or password';
    return;
  }
  const data = await res.json();
  TOKEN = data.access_token;
  enterApp(u, data.role);
}

// ---- REGISTER ----
async function doRegister(){
  const u = document.getElementById('u').value;
  const p = document.getElementById('p').value;
  const role = document.getElementById('role').value;
  const res = await fetch('/register', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({username:u, password:p, role:role})});
  const data = await res.json();
  if(!res.ok){
    document.getElementById('loginErr').textContent = '❌ ' + (data.detail || 'Could not register');
    return;
  }
  // Registration auto-logs you in (token returned).
  TOKEN = data.access_token;
  enterApp(u, data.role);
}

function logout(){
  TOKEN = null;
  document.getElementById('app').classList.add('hidden');
  document.getElementById('loginScreen').classList.remove('hidden');
  document.getElementById('loginErr').textContent = '';
}

// Every protected request sends the token in the header.
function authHeaders(){ return {'Authorization': 'Bearer ' + TOKEN}; }

async function load(){
  issuers = await (await fetch('/issuers', {headers:authHeaders()})).json();
  const sel = document.getElementById('issuer');
  sel.innerHTML = issuers.map(i =>
    `<option value="${i.id}">${i.name} — ${i.sector} / ${i.stage}</option>`).join('');
  sel.onchange = showIssuer;
  showIssuer();
}

function money(n){ return '$' + Number(n).toLocaleString(); }

function showIssuer(){
  const i = issuers.find(x => x.id === document.getElementById('issuer').value);
  document.getElementById('issuerInfo').innerHTML =
    `<b>${i.name}</b> needs <b>${money(i.ask_amount_usd)}</b><br>` +
    `<span class="chip">${i.sector}</span><span class="chip">${i.stage}</span>` +
    `<span class="chip">${i.instrument}</span><span class="chip">${i.geography}</span>` +
    (i.esg_focus ? `<span class="chip">🌱 ESG</span>` : '') +
    `<div style="margin-top:10px;color:var(--mut)">${i.summary}</div>`;
}

function cls(s){ return s >= 0.75 ? 'hi' : s >= 0.4 ? 'mid' : 'lo'; }

async function runMatch(){
  const id = document.getElementById('issuer').value;
  const k = document.getElementById('topk').value || 4;
  document.getElementById('status').textContent = 'Agent scoring investors…';
  const data = await (await fetch(`/match/${id}?top_k=${k}`, {headers:authHeaders()})).json();
  render(data);
}

function render(data){
  const m = data.matches;
  document.getElementById('status').innerHTML =
    `Found <b>${m.length}</b> ranked matches for <b>${data.issuer.name}</b>.`;
  document.getElementById('results').innerHTML = m.map((r, idx) => {
    const pct = Math.round(r.score * 100);
    const factors = r.factors.map(f => `
      <div class="factor">
        <div class="frow">
          <span class="fname">${f.name}</span>
          <span class="fpct ${cls(f.score)}">${Math.round(f.score*100)}%</span>
        </div>
        <div class="fdetail">${f.detail}</div>
      </div>`).join('');
    return `
      <div class="result ${idx===0?'win':''}">
        <div class="rank">#${idx+1}</div>
        <div class="rname">${r.investor_name}<span class="rid">${r.investor_id}</span>
          ${idx===0?'<span class="badge">BEST MATCH</span>':''}</div>
        <div class="scorewrap">
          <div class="scoreval ${cls(r.score)}">${pct}%</div>
          <div class="bar"><i style="width:${pct}%"></i></div>
        </div>
        <div class="factors">${factors}</div>
      </div>`;
  }).join('');
}
</script>
</body>
</html>
"""