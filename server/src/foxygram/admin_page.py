PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FoxyGram Server</title>
<style>
  :root { color-scheme: dark; --bg:#0d1117; --panel:#161b22; --line:#30363d; --text:#e6edf3; --muted:#8b949e;
          --accent:#a371f7; --strong:#8957e5; --ok:#3fb950; --warn:#d29922; --bad:#f85149; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:14px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif; }
  main { max-width:720px; margin:0 auto; padding:32px 16px 64px; }
  h1 { font-size:22px; margin:0 0 4px; font-weight:600; }
  .sub { color:var(--muted); margin:0 0 24px; }
  section { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-bottom:12px; }
  h2 { font-size:15px; margin:0 0 10px; font-weight:600; display:flex; justify-content:space-between; align-items:center; gap:12px; }
  .pill { font-size:12px; font-weight:500; padding:2px 10px; border-radius:999px; background:#21262d; color:var(--muted); white-space:nowrap; }
  .pill.ok { color:var(--ok); } .pill.warn { color:var(--warn); } .pill.bad { color:var(--bad); }
  .row { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
  input[type=text], input[type=password], input[type=search] { flex:1; min-width:0; background:var(--bg); color:var(--text);
    border:1px solid var(--line); border-radius:8px; padding:8px 10px; font:inherit; outline:none; }
  input:focus { border-color:var(--accent); }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:8px 14px; font:inherit; font-weight:500; cursor:pointer; flex-shrink:0; }
  button:hover { background:var(--strong); }
  button.ghost { background:#21262d; color:var(--text); }
  .muted { color:var(--muted); } .err { color:var(--bad); margin-top:8px; }
  .qr { background:#fff; border-radius:10px; padding:10px; width:max-content; margin-top:12px; line-height:0; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; }
  .stat b { display:block; font-size:18px; font-weight:600; }
  .chats { max-height:380px; overflow:auto; margin-top:10px; border:1px solid var(--line); border-radius:8px; }
  .chat { display:flex; align-items:center; gap:10px; padding:8px 12px; border-bottom:1px solid var(--line); cursor:pointer; }
  .chat:last-child { border-bottom:0; } .chat:hover { background:#1c2128; }
  .chat span { flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .kind { flex:none !important; color:var(--muted); font-size:12px; }
  input[type=checkbox] { accent-color:var(--accent); width:16px; height:16px; }
</style>
</head>
<body>
<main>
  <h1>FoxyGram Server</h1>
  <p class="sub" id="version"></p>

  <section id="tg"><h2>Telegram <span class="pill" id="tgPill"></span></h2><div id="tgBody"></div></section>

  <section id="phone" hidden>
    <h2>Телефон <span class="pill" id="phonePill"></span></h2>
    <div class="muted">В приложении FoxyGram нажмите «Сканировать код с компьютера» и наведите камеру.</div>
    <div class="qr" id="pairQr"></div>
  </section>

  <section id="claude">
    <h2>Claude <span class="pill" id="claudePill"></span></h2>
    <div class="grid">
      <div class="stat"><b id="calls">0</b><span class="muted">вызовов за сутки</span></div>
      <div class="stat"><b id="pending">0</b><span class="muted">в очереди</span></div>
      <div class="stat"><b id="cases">0</b><span class="muted">открытых дел</span></div>
    </div>
    <div class="err" id="claudeDetail"></div>
  </section>

  <section id="chatsBox" hidden>
    <h2>Чаты для анализа <span class="pill" id="selected"></span></h2>
    <div class="muted">Только отмеченные чаты сохраняются здесь и отправляются в Claude. Всё остальное остаётся только в Telegram.</div>
    <div class="row"><input type="search" id="filter" placeholder="Поиск чата"></div>
    <div class="chats" id="chatList"></div>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
const post = (url, body) => fetch(url, {method:'POST', headers:{'content-type':'application/json','x-foxygram':'1'}, body: JSON.stringify(body||{})});
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let lastTg = '', chats = [], pairedUrl = null;

const KIND = {private:'личный', group:'группа', channel:'канал'};

function renderTelegram(t) {
  const key = t.state + '|' + t.error;
  if (key === lastTg) { if (t.state === 'qr') $('loginQr').src = '/api/qr/login.svg?' + Date.now(); return; }
  lastTg = key;
  const pill = $('tgPill'); const body = $('tgBody');
  const err = t.error ? `<div class="err">${esc(t.error)}</div>` : '';
  if (!t.has_app_id) { pill.textContent='нужна настройка'; pill.className='pill bad'; body.innerHTML='<div class="muted">В config.toml не заполнены api_id и api_hash.</div>'; return; }
  switch (t.state) {
    case 'ready': pill.textContent='подключён'; pill.className='pill ok'; body.innerHTML='<div class="muted">Сессия активна. Сервер не отмечает сообщения прочитанными.</div>'; break;
    case 'need_login':
      pill.textContent='нужен вход'; pill.className='pill warn';
      body.innerHTML=`<div class="row"><button onclick="post('/api/login/qr')">Войти по QR-коду</button></div>
        <div class="row"><input type="text" id="ph" placeholder="+7..."><button class="ghost" onclick="post('/api/login/phone',{phone:$('ph').value})">Войти по номеру</button></div>${err}`; break;
    case 'qr':
      pill.textContent='сканируйте код'; pill.className='pill warn';
      body.innerHTML=`<div class="muted">Telegram на телефоне: Настройки, Устройства, Подключить устройство.</div><div class="qr"><img id="loginQr" src="/api/qr/login.svg?${Date.now()}"></div>${err}`; break;
    case 'need_code':
      pill.textContent='введите код'; pill.className='pill warn';
      body.innerHTML=`<div class="row"><input type="text" id="code" placeholder="Код из Telegram"><button onclick="post('/api/login/code',{code:$('code').value})">Подтвердить</button></div>${err}`; break;
    case 'need_password':
      pill.textContent='нужен пароль'; pill.className='pill warn';
      body.innerHTML=`<div class="muted">${esc(t.password_hint)}</div><div class="row"><input type="password" id="pw" placeholder="Облачный пароль"><button onclick="post('/api/login/password',{password:$('pw').value})">Войти</button></div>${err}`; break;
    default: pill.textContent='запуск'; pill.className='pill'; body.innerHTML=err || '<div class="muted">Запускается...</div>';
  }
}

function renderChats() {
  const q = $('filter').value.toLowerCase();
  $('chatList').innerHTML = chats.filter(c => c.title.toLowerCase().includes(q)).slice(0,300).map(c =>
    `<label class="chat"><input type="checkbox" ${c.ai_enabled?'checked':''} data-id="${c.chat_id}"><span>${esc(c.title)}</span><span class="kind">${KIND[c.kind]||''}</span></label>`).join('');
}

$('chatList').addEventListener('change', async e => {
  const id = e.target.dataset.id; if (!id) return;
  await post(`/api/chats/${id}/ai`, {enabled: e.target.checked});
  const c = chats.find(x => String(x.chat_id) === id); if (c) c.ai_enabled = e.target.checked ? 1 : 0;
});
$('filter').addEventListener('input', renderChats);

async function refreshChats() { chats = await (await fetch('/api/chats')).json(); renderChats(); }

const CLAUDE = {ok:['работает','ok'], quota:['лимит','warn'], capped:['пауза','warn'], login_needed:['нужен вход','bad'], missing:['не найден','bad']};

async function tick() {
  let s; try { s = await (await fetch('/api/state')).json(); } catch { return; }
  $('version').textContent = 'Версия ' + s.version + (s.url ? ' · ' + s.url : '');
  renderTelegram(s.telegram);
  const ready = s.telegram.state === 'ready';
  $('phone').hidden = !ready; $('chatsBox').hidden = !ready;
  $('phonePill').textContent = s.devices ? 'подключён' : 'не подключён'; $('phonePill').className = 'pill ' + (s.devices?'ok':'warn');
  if (ready && s.url && s.url !== pairedUrl) { pairedUrl = s.url; $('pairQr').innerHTML = `<img src="/api/qr/pair.svg?${Date.now()}">`; }
  if (ready && !chats.length) refreshChats();
  const c = CLAUDE[s.claude.state] || [s.claude.state,''];
  $('claudePill').textContent = c[0]; $('claudePill').className = 'pill ' + c[1];
  $('claudeDetail').textContent = s.claude.detail || '';
  $('calls').textContent = s.claude.calls_today + ' / ' + s.claude.max_per_day;
  $('pending').textContent = s.pending; $('cases').textContent = s.open_cases;
  $('selected').textContent = 'выбрано: ' + s.selected;
}
tick(); setInterval(tick, 2000);
</script>
</body>
</html>
"""
