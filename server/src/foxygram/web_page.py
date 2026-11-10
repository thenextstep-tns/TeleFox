PAGE = r"""<!doctype html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<title>FoxyGram</title>
<style>
:root, [data-theme=dark] {
  --bg:#0D1117; --surface:#161B22; --surface-high:#21262D; --border:#30363D; --text:#E6EDF3; --text2:#8B949E;
  --accent:#A371F7; --accent-strong:#8957E5; --on-accent:#FFFFFF; --accent-soft:rgba(163,113,247,.16);
  --bubble-in:#161B22; --bubble-in-meta:#8B949E; --bubble-out:#36275E; --bubble-out-meta:#B4A5D4;
  --link:#BC8CFF; --link-out:#D2B8FF; --success:#3FB950; --warning:#D29922; --danger:#F85149;
  --muted-badge:#484F58; --service:rgba(33,38,45,.8); --on-service:#E6EDF3; --hover:rgba(230,237,243,.06);
  --scrim:rgba(0,0,0,.5); color-scheme:dark;
}
[data-theme=light] {
  --bg:#FFFFFF; --surface:#F6F8FA; --surface-high:#EAEEF2; --border:#D0D7DE; --text:#1F2328; --text2:#59636E;
  --accent:#8250DF; --accent-strong:#6E40C9; --on-accent:#FFFFFF; --accent-soft:rgba(130,80,223,.12);
  --bubble-in:#F6F8FA; --bubble-in-meta:#59636E; --bubble-out:#EBE1FC; --bubble-out-meta:#6E5A96;
  --link:#6639BA; --link-out:#5128A0; --success:#1A7F37; --warning:#9A6700; --danger:#CF222E;
  --muted-badge:#8C959F; --service:rgba(234,238,242,.7); --on-service:#1F2328; --hover:rgba(31,35,40,.05);
  --scrim:rgba(0,0,0,.32); color-scheme:light;
}
* { box-sizing:border-box; scrollbar-width:thin; scrollbar-color:var(--surface-high) transparent; }
html, body { height:100%; margin:0; }
body { background:var(--bg); color:var(--text); font:15px/1.35 Roboto, "Segoe UI", system-ui, -apple-system, sans-serif;
  overflow:hidden; -webkit-font-smoothing:antialiased; }
button { font:inherit; color:inherit; }
a { color:inherit; }
.ic { fill:currentColor; flex:none; display:block; }
.hidden { display:none !important; }

#app { display:flex; height:100vh; height:100dvh; width:100%; }
#listPane { flex:0 0 400px; display:flex; flex-direction:column; min-width:0; border-right:1px solid var(--border); position:relative; background:var(--bg); }
#mainPane { flex:1; display:flex; flex-direction:column; min-width:0; position:relative; background:var(--bg); }
@media (max-width: 899px) {
  #listPane { flex:1 1 auto; border-right:0; }
  #mainPane { display:none; }
  body.routed #listPane { display:none; }
  body.routed #mainPane { display:flex; }
  .wide-only { display:none !important; }
}
.screen { flex:1; display:flex; flex-direction:column; min-height:0; }

.bar { height:56px; display:flex; align-items:center; background:var(--surface); flex:none; padding:0 4px; }
.bar-title { font-size:20px; font-weight:500; flex:1; padding-left:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ib { width:48px; height:48px; border:0; background:none; border-radius:50%; display:grid; place-items:center; cursor:pointer; color:var(--text); flex:none; }
.ib:hover { background:var(--hover); }
.ib.dim { color:var(--text2); }
.search-input { flex:1; min-width:0; background:none; border:0; outline:none; color:var(--text); font-size:17px; padding:0 4px; }
.search-input::placeholder, textarea::placeholder { color:var(--text2); }

.folders { display:flex; height:44px; overflow-x:auto; gap:2px; background:var(--surface); flex:none; scrollbar-width:none; }
.folders::-webkit-scrollbar { display:none; }
.folder { position:relative; padding:0 12px; display:flex; align-items:center; gap:5px; color:var(--text2); font-weight:500; font-size:15px; cursor:pointer; white-space:nowrap; user-select:none; }
.folder.active { color:var(--accent); }
.folder.active::after { content:""; position:absolute; left:0; right:0; bottom:0; height:3px; border-radius:3px 3px 0 0; background:var(--accent); }

.badge { height:22px; min-width:22px; border-radius:11px; padding:0 6px; display:inline-flex; align-items:center; justify-content:center; color:#fff; font-size:13px; font-weight:500; background:var(--accent); flex:none; white-space:nowrap; }
.badge.muted { background:var(--muted-badge); }
.badge.small { font-size:12px; }

.list { flex:1; overflow-y:auto; overscroll-behavior:contain; }
.row { position:relative; height:76px; display:flex; align-items:center; gap:12px; padding:0 12px; cursor:pointer; user-select:none; }
.row:hover { background:var(--hover); }
.row.sel { background:var(--accent-soft); }
.row::after { content:""; position:absolute; left:80px; right:0; bottom:0; height:1px; background:var(--border); transform:scaleY(.5); transform-origin:bottom; }
.rb { flex:1; min-width:0; display:flex; flex-direction:column; gap:3px; }
.rl { display:flex; align-items:center; min-width:0; }
.rtitle { font-size:16.5px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.grow { flex:1; min-width:0; }
.rtime { color:var(--text2); font-size:13px; margin-left:3px; white-space:nowrap; }
.prev { color:var(--text2); font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; min-width:0; }
.prev .who { color:var(--text); }
.prev .lbl { color:var(--accent); }
.prev .draft { color:var(--danger); }
.dot { width:8px; height:8px; border-radius:50%; background:var(--accent); flex:none; margin-right:5px; }
.dot.urgent { background:var(--danger); }
.pill { border-radius:6px; padding:1px 6px; font-size:11px; font-weight:500; white-space:nowrap; flex:none; line-height:15px; }
.pthumb { width:18px; height:18px; border-radius:3px; object-fit:cover; margin-right:4px; flex:none; }
.circle { width:22px; height:22px; border-radius:50%; display:grid; place-items:center; color:#fff; flex:none; margin-left:6px; font-size:13px; font-weight:500; }

.av { flex:none; border-radius:50%; position:relative; overflow:hidden; display:grid; place-items:center; color:#fff; font-weight:500; user-select:none; }
.av img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:0; transition:opacity .15s; }
.av img.ok { opacity:1; }

.empty-main { flex:1; display:grid; place-items:center; }
.svc { align-self:center; margin:6px 32px; padding:3px 10px; border-radius:12px; background:var(--service); color:var(--on-service); font-size:13px; text-align:center; max-width:calc(100% - 64px); }

.chead { background:var(--surface); flex:none; }
.chead-row { height:56px; display:flex; align-items:center; padding:0 4px; }
.chead-main { flex:1; min-width:0; display:flex; align-items:center; gap:10px; cursor:pointer; border-radius:8px; padding:4px 0; }
.chead-title { font-size:17px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.chead-sub { font-size:13px; color:var(--text2); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.case-line { display:flex; align-items:center; gap:6px; padding:0 12px 6px; cursor:pointer; font-size:13px; }
.case-line span:last-child { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

.feedbox { flex:1; position:relative; min-height:0; }
.feed { position:absolute; inset:0; overflow-y:auto; overflow-x:hidden; display:flex; flex-direction:column; padding:6px 0; overscroll-behavior:contain; }
.feed-inner { margin-top:auto; display:flex; flex-direction:column; }
.unread-line { margin:6px 0; padding:4px 0; background:var(--surface); color:var(--accent); font-size:14px; font-weight:500; text-align:center; }
.m { display:flex; align-items:flex-end; padding:0 8px; margin-top:2px; }
.m.starts { margin-top:6px; }
.m.out { justify-content:flex-end; }
.m .avslot { width:38px; flex:none; margin-right:4px; }
.bub { position:relative; margin-left:7px; background:var(--bubble-in); min-width:0; }
.m.out .bub { margin-left:0; margin-right:7px; background:var(--bubble-out); }
.bub .clip { overflow:hidden; border-radius:inherit; }
.tail { position:absolute; bottom:0; left:-7px; fill:var(--bubble-in); }
.m.out .tail { left:auto; right:-7px; transform:scaleX(-1); fill:var(--bubble-out); }
.bhead { padding:6px 10px 0; }
.bhead.vis { padding-bottom:5px; }
.sname { font-size:14px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; cursor:default; }
.fwd { font-size:13px; color:var(--accent); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.quote-reply { display:flex; border-radius:5px; overflow:hidden; margin:3px 0; cursor:pointer; min-width:0; }
.quote-reply .qbar { width:3px; flex:none; }
.quote-reply .qthumb { width:32px; height:32px; border-radius:4px; object-fit:cover; margin:4px 0 4px 5px; flex:none; }
.quote-reply .qbody { padding:3px 6px; min-width:0; }
.quote-reply .qname { font-size:13px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.quote-reply .qtext { font-size:13px; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tbox { position:relative; min-width:72px; }
.txt { font-size:16px; line-height:21px; padding:6px 10px; white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; }
.txt.hd { padding-top:2px; }
.txt::after { content:""; display:inline-block; width:var(--mw, 0px); height:1px; }
.txt a, .txt .lnk { color:var(--link); text-decoration:none; cursor:pointer; }
.txt a:hover { text-decoration:underline; }
.m.out .txt a, .m.out .txt .lnk { color:var(--link-out); }
.txt .code { font-family:Consolas, "Roboto Mono", monospace; font-size:14px; background:var(--accent-soft); border-radius:4px; padding:0 3px; }
.txt .pre { display:block; font-family:Consolas, "Roboto Mono", monospace; font-size:14px; background:var(--accent-soft); border-radius:6px; padding:6px 8px; margin:2px 0; white-space:pre-wrap; }
.txt .quote { display:block; border-left:3px solid var(--accent); background:var(--accent-soft); border-radius:4px; padding:2px 8px; margin:2px 0; }
.txt .spoiler { background:var(--text2); color:transparent; border-radius:3px; cursor:pointer; }
.txt .spoiler.open { background:none; color:inherit; }
.meta { position:absolute; right:8px; bottom:4px; display:flex; align-items:center; font-size:12px; color:var(--bubble-in-meta); white-space:nowrap; pointer-events:none; }
.m.out .meta { color:var(--bubble-out-meta); }
.meta .ic { margin-left:3px; }
.meta .read { color:var(--accent); }
.meta .fail { color:var(--danger); }
.metapill { position:absolute; right:6px; bottom:6px; border-radius:999px; background:rgba(0,0,0,.6); padding:2px 6px; display:flex; align-items:center; font-size:12px; color:#fff; pointer-events:none; }
.metapill .ic { margin-left:3px; }
.metapill .read { color:#fff; }
.reacts { display:flex; flex-wrap:wrap; gap:4px; padding:0 8px 22px; }
.reacts.bare { padding:4px 0 0; }
.react { display:flex; align-items:center; gap:4px; border-radius:13px; padding:3px 8px; background:var(--accent-soft); font-size:13px; }
.react .e { font-size:14px; }
.react.mine { background:var(--accent); color:var(--on-accent); }
.inset { padding:8px 10px 0; }
.spacer16 { height:16px; }
.unsupported { color:var(--text2); font-size:15px; }
.media { position:relative; background:#000 center/cover no-repeat; cursor:pointer; overflow:hidden; }
.media img.full, .media video.full { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:0; transition:opacity .15s; }
.media img.full.ok { opacity:1; }
.media video.full { opacity:1; }
.media img.blur { position:absolute; inset:-8px; width:calc(100% + 16px); height:calc(100% + 16px); object-fit:cover; filter:blur(8px); }
.play { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:44px; height:44px; border-radius:50%; background:rgba(0,0,0,.6); display:grid; place-items:center; color:#fff; }
.dur { position:absolute; left:6px; top:6px; border-radius:999px; background:rgba(0,0,0,.6); color:#fff; font-size:12px; padding:1px 6px; }
.album { display:grid; gap:2px; }
.album .media { width:100%; height:100%; }
.web { display:flex; border-radius:5px; overflow:hidden; margin:0 10px 22px; cursor:pointer; }
.web .wbar { width:3px; flex:none; background:var(--link); }
.m.out .web .wbar { background:var(--link-out); }
.web .wbody { padding:4px 8px; min-width:0; font-size:14px; }
.web .wsite { color:var(--link); font-weight:500; }
.m.out .web .wsite { color:var(--link-out); }
.web .wtitle { font-weight:500; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.web .wdesc { display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical; overflow:hidden; white-space:pre-wrap; }
.web .wphoto { width:100%; height:140px; border-radius:4px; object-fit:cover; margin-top:4px; display:block; opacity:0; }
.web .wphoto.ok { opacity:1; }
.hrow { display:flex; align-items:center; gap:10px; min-width:0; }
.round-btn { width:44px; height:44px; border-radius:50%; display:grid; place-items:center; flex:none; cursor:pointer; border:0; }
.b1 { font-size:15px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.b2 { font-size:13px; color:var(--bubble-in-meta); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.m.out .b2 { color:var(--bubble-out-meta); }
.voice { min-width:230px; }
.wave { width:180px; height:26px; display:flex; align-items:center; gap:1px; cursor:pointer; }
.wave i { flex:1; border-radius:1px; min-height:2px; background:var(--wave-rest); }
.wave i.on { background:var(--wave-on); }
.vmeta { display:flex; align-items:center; gap:4px; font-size:12px; color:var(--bubble-in-meta); margin-top:2px; }
.m.out .vmeta { color:var(--bubble-out-meta); }
.vdot { width:6px; height:6px; border-radius:50%; background:var(--accent); }
.docthumb { width:44px; height:44px; border-radius:6px; object-fit:cover; flex:none; }
.poll { min-width:240px; }
.poll .q { font-size:16px; font-weight:500; }
.poll .kind { font-size:13px; color:var(--bubble-in-meta); margin-bottom:6px; }
.m.out .poll .kind { color:var(--bubble-out-meta); }
.popt { margin:8px 0; }
.popt .l { display:flex; align-items:center; gap:6px; font-size:15px; }
.popt .pct { width:38px; font-size:13px; font-weight:500; flex:none; }
.popt .barbg { height:3px; border-radius:2px; background:var(--accent-soft); margin:4px 0 0 44px; overflow:hidden; }
.popt .barfg { height:100%; background:var(--accent); }
.m.out .popt .barfg { background:var(--link-out); }
.bare { position:relative; margin:0 7px; }
.sticker img, .sticker video { width:100%; height:100%; object-fit:contain; }
.sticker .emoji { font-size:96px; line-height:1; display:grid; place-items:center; width:100%; height:100%; }
.roundv { width:220px; height:220px; border-radius:50%; overflow:hidden; position:relative; background:#000; cursor:pointer; }
.roundv img, .roundv video { width:100%; height:100%; object-fit:cover; position:absolute; inset:0; }

.down { position:absolute; right:12px; bottom:12px; width:44px; height:44px; border-radius:50%; background:var(--surface-high); display:grid; place-items:center; cursor:pointer; border:0; color:var(--text); box-shadow:0 2px 6px rgba(0,0,0,.25); }
.down .badge { position:absolute; top:-12px; left:50%; transform:translateX(-50%); }

.composer { background:var(--surface); flex:none; }
.target { height:48px; display:flex; align-items:center; }
.target .tline { width:2px; align-self:stretch; margin:8px 8px 8px 12px; background:var(--accent); }
.target .tt { font-size:14px; font-weight:500; color:var(--accent); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.target .tx { font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.crow { display:flex; align-items:flex-end; min-height:52px; }
.crow textarea { flex:1; min-width:0; resize:none; border:0; outline:none; background:none; color:var(--text); font:17px/22px Roboto, "Segoe UI", system-ui, sans-serif; padding:15px 0 15px 16px; max-height:184px; height:52px; }
.send { width:52px; height:52px; display:grid; place-items:center; background:none; border:0; cursor:pointer; color:var(--accent); flex:none; }
.send.off { color:var(--text2); cursor:default; }

.scrim { position:fixed; inset:0; background:var(--scrim); z-index:20; }
.drawer { position:fixed; top:0; bottom:0; left:0; width:300px; max-width:85vw; background:var(--surface); z-index:21; border-radius:0 16px 16px 0; padding:8px 0; box-shadow:0 8px 24px rgba(0,0,0,.35); }
.drawer-title { font-size:20px; font-weight:500; padding:16px; }
.divider { height:1px; background:var(--border); transform:scaleY(.5); }
.ditem { display:flex; align-items:center; gap:24px; padding:14px 16px; cursor:pointer; font-size:16px; color:var(--text); text-decoration:none; }
.ditem .ic { color:var(--text2); }
.ditem:hover { background:var(--hover); }
.sheet { position:fixed; left:50%; bottom:0; transform:translateX(-50%); width:min(560px, 100%); max-height:85vh; overflow-y:auto; background:var(--surface); border-radius:28px 28px 0 0; z-index:21; padding-bottom:12px; box-shadow:0 -4px 24px rgba(0,0,0,.3); }
.handle { width:32px; height:4px; border-radius:2px; background:var(--text2); opacity:.4; margin:22px auto 14px; }
.sheet-title { font-size:17px; font-weight:500; padding:8px 20px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.srow { display:flex; align-items:center; gap:20px; padding:14px 20px; cursor:pointer; font-size:16px; }
.srow .ic { color:var(--text2); }
.srow:hover { background:var(--hover); }
.srow.danger, .srow.danger .ic { color:var(--danger); }
.ptitle { color:var(--text2); font-size:13px; font-weight:500; padding:12px 20px 6px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; padding:0 20px; }
.chip { border-radius:16px; padding:7px 14px; background:var(--surface-high); color:var(--text); font-size:14px; cursor:pointer; border:0; }
.chip.on { background:var(--accent-soft); color:var(--accent); font-weight:500; }
.brain-note { color:var(--text2); font-size:14px; padding:4px 20px 12px; }
.ib.on { color:var(--accent); }
.chat-wrap { flex:1; display:flex; min-height:0; position:relative; }
.chat-wrap > .screen { min-width:0; }
.bpanel { flex:0 0 360px; display:flex; flex-direction:column; min-height:0; border-left:1px solid var(--border); background:var(--bg); }
.bpanel.closed { display:none; }
@media (max-width: 1279px) {
  .bpanel { position:absolute; top:0; right:0; bottom:0; width:min(360px, 100%); z-index:6; box-shadow:-8px 0 24px rgba(0,0,0,.35); }
}
.bp-head { height:56px; display:flex; align-items:center; gap:6px; padding:0 4px 0 16px; background:var(--surface); flex:none; }
.bp-title { font-size:17px; font-weight:500; flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bp-body { flex:1; overflow-y:auto; padding:12px; }
.bp-banner { border-radius:10px; padding:10px 12px; font-size:14px; margin-bottom:10px; color:var(--warning); background:color-mix(in srgb, var(--warning) 12%, transparent); }
.bp-hint { color:var(--text2); font-size:14px; padding:2px 2px 10px; }
.bp-sub { color:var(--text2); font-size:13px; font-weight:500; margin:6px 2px 8px; }
.bp-msg { border-left:3px solid var(--accent); background:var(--accent-soft); border-radius:6px; padding:6px 10px; margin-bottom:10px; font-size:14px; }
.bp-msg .who { font-weight:500; color:var(--accent); }
.bp-msg .txt2 { display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical; overflow:hidden; white-space:pre-wrap; overflow-wrap:anywhere; }
.brun { background:var(--surface); border-radius:12px; padding:12px; margin-bottom:10px; }
.brun-top { display:flex; align-items:center; flex-wrap:wrap; gap:6px; font-size:13px; color:var(--text2); }
.brun-label { color:var(--text2); font-size:12px; font-weight:500; text-transform:uppercase; letter-spacing:.03em; margin-top:10px; }
.brun-text { font-size:15px; margin-top:4px; white-space:pre-wrap; overflow-wrap:anywhere; }
.brun-sum { font-size:13px; color:var(--text2); margin-top:8px; white-space:pre-wrap; overflow-wrap:anywhere; display:-webkit-box; -webkit-line-clamp:5; -webkit-box-orient:vertical; overflow:hidden; }
.working { display:inline-flex; align-items:center; gap:6px; color:var(--accent); font-weight:500; }
.spin-sm { width:12px; height:12px; border-radius:50%; border:2px solid var(--accent-soft); border-top-color:var(--accent); animation:spin 1s linear infinite; display:inline-block; }
.bact { border:1px solid var(--border); border-radius:10px; padding:10px; margin-top:8px; }
.bact-kind { font-size:13px; color:var(--text2); }
.bact-line { font-size:13px; margin-top:4px; overflow-wrap:anywhere; }
.bact-text { margin-top:6px; padding:8px 10px; border-radius:8px; background:var(--bubble-out); white-space:pre-wrap; overflow-wrap:anywhere; font-size:15px; }
.bact-status { margin-top:6px; font-size:13px; font-weight:500; }
.bact-buttons { display:flex; flex-wrap:wrap; gap:2px; margin:6px 0 0 -12px; }
.bact-input { width:100%; margin-top:6px; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font:15px/20px Roboto, "Segoe UI", system-ui, sans-serif; resize:vertical; outline:none; }
.bact-input:focus { border-color:var(--accent); }
.bopt { border:1px solid var(--accent); color:var(--accent); background:none; border-radius:16px; padding:5px 12px; font-size:14px; cursor:pointer; margin:6px 6px 0 0; }
.bopt:hover { background:var(--accent-soft); }
.bmark { align-self:flex-end; width:22px; height:22px; border-radius:50%; display:grid; place-items:center; margin:0 4px 2px; background:var(--accent-soft); color:var(--accent); flex:none; cursor:pointer; }
.bmark.open { color:var(--warning); background:color-mix(in srgb, var(--warning) 18%, transparent); }
.bmark.failed { color:var(--danger); background:color-mix(in srgb, var(--danger) 16%, transparent); }
.m.bsel .bub { box-shadow:0 0 0 2px var(--accent); }
.m.bsel .bare { outline:2px solid var(--accent); outline-offset:2px; border-radius:12px; }
.brain-hint { color:var(--text2); font-size:13px; }
.sw { width:52px; height:32px; border-radius:16px; border:2px solid var(--text2); background:var(--surface-high); position:relative; flex:none; cursor:pointer; padding:0; }
.sw::after { content:""; position:absolute; width:16px; height:16px; border-radius:50%; background:var(--text2); left:6px; top:6px; transition:all .15s; }
.sw.on { background:var(--accent); border-color:var(--accent); }
.sw.on::after { width:24px; height:24px; left:22px; top:2px; background:var(--on-accent); }
.menu { position:fixed; background:var(--surface-high); border-radius:4px; box-shadow:0 4px 16px rgba(0,0,0,.35); padding:8px 0; z-index:25; min-width:200px; }
.menu div { padding:12px 16px; cursor:pointer; font-size:15px; }
.menu div:hover { background:var(--hover); }

.tabs { display:flex; background:var(--surface); padding:0 8px; flex:none; }
.tbtn { background:none; border:0; color:var(--accent); font-weight:500; font-size:14px; padding:10px 12px; border-radius:20px; cursor:pointer; }
.tbtn:hover { background:var(--accent-soft); }
.tbtn.dim { color:var(--text2); }
.tbtn.danger { color:var(--danger); }
.field { margin:8px 16px; display:flex; align-items:center; gap:8px; background:var(--surface-high); border-radius:24px; padding:0 14px; height:44px; color:var(--text2); }
.field input { flex:1; background:none; border:0; outline:none; color:var(--text); font-size:16px; }
.note { flex:1; display:grid; place-items:center; padding:32px; color:var(--text2); font-size:15px; text-align:center; }
.scroll { flex:1; overflow-y:auto; }
.topic-all { color:var(--accent); font-size:16px; padding:14px 16px; cursor:pointer; }
.topic-all:hover, .topic-row:hover { background:var(--hover); }
.topic-row { display:flex; align-items:center; gap:12px; padding:10px 16px; cursor:pointer; }
.case-row { padding:12px 16px; cursor:pointer; border-bottom:1px solid var(--border); }
.case-row:hover { background:var(--hover); }
.case-top { display:flex; align-items:center; gap:8px; }
.case-title { font-size:16px; font-weight:500; flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.case-sum { font-size:14px; color:var(--text2); margin-top:3px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.case-foot { display:flex; align-items:center; gap:6px; margin-top:5px; min-width:0; }
.case-chats { font-size:13px; color:var(--accent); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card { background:var(--surface); border-radius:12px; padding:12px; margin-bottom:10px; cursor:pointer; }
.card-top { display:flex; align-items:center; gap:6px; }
.card-chat { font-size:14px; font-weight:500; color:var(--accent); flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card-sum { font-size:15px; margin-top:4px; }
.card-msg { font-size:13px; color:var(--text2); margin-top:4px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.section { color:var(--accent); font-size:14px; font-weight:500; padding:20px 16px 6px; }
.set-row { display:flex; align-items:center; gap:16px; padding:12px 16px; cursor:pointer; }
.set-row:hover { background:var(--hover); }
.set-row .t1 { font-size:16px; }
.set-row .t2 { font-size:13px; color:var(--text2); }
.radio { width:20px; height:20px; border-radius:50%; border:2px solid var(--text2); flex:none; display:grid; place-items:center; }
.radio.on { border-color:var(--accent); }
.radio.on::after { content:""; width:10px; height:10px; border-radius:50%; background:var(--accent); }
.ai-row { display:flex; align-items:center; gap:12px; padding:10px 16px; }
.ai-row .t1 { flex:1; min-width:0; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

.viewer { position:fixed; inset:0; background:rgba(0,0,0,.92); z-index:30; display:flex; align-items:center; justify-content:center; }
.viewer img, .viewer video { max-width:94vw; max-height:88vh; object-fit:contain; }
.viewer .vbar { position:absolute; top:8px; right:8px; display:flex; gap:4px; }
.viewer .ib { color:#fff; }
.viewer .ib:hover { background:rgba(255,255,255,.12); }
.viewer .loading { position:absolute; color:#ccc; font-size:14px; }
.toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%); background:#323232; color:#fff; padding:10px 16px; border-radius:8px; z-index:40; font-size:14px; max-width:90vw; box-shadow:0 4px 12px rgba(0,0,0,.3); }
.gate { position:fixed; inset:0; background:var(--bg); z-index:50; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; padding:32px; text-align:center; color:var(--text2); }
.gate a { color:var(--accent); font-weight:500; }
.spin { width:36px; height:36px; border-radius:50%; border:3px solid var(--surface-high); border-top-color:var(--accent); animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
</head>
<body>
<div id="app">
  <section id="listPane"></section>
  <section id="mainPane"></section>
</div>
<div id="overlays"></div>
<script>
"use strict";

// ---------- small helpers ----------
const LS = {
  get(key, fallback) { try { const v = localStorage.getItem("fg." + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem("fg." + key, JSON.stringify(value)); } catch {} },
};

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  append(el, kids);
  return el;
}
function append(el, kids) {
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : String(kid));
  }
  return el;
}

const PATHS = {
  menu: "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z",
  search: "M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
  back: "M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  more: "M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z",
  send: "M2.01 21L23 12 2.01 3 2 10l15 2-15 2z",
  check: "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
  doneAll: "M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z",
  clock: "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z",
  error: "M11 15h2v2h-2zm0-8h2v6h-2zm.99-5C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z",
  pin: "M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z",
  volumeOff: "M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51A8.8 8.8 0 0 0 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.99 8.99 0 0 0 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z",
  verified: "M23 12l-2.44-2.79.34-3.69-3.61-.82-1.89-3.2L12 2.96 8.6 1.5 6.71 4.69 3.1 5.5l.34 3.7L1 12l2.44 2.79-.34 3.7 3.61.82L8.6 22.5l3.4-1.47 3.4 1.46 1.89-3.19 3.61-.82-.34-3.69L23 12zm-12.91 4.72l-3.8-3.81 1.48-1.48 2.32 2.33 5.85-5.87 1.48 1.48-7.33 7.35z",
  heart: "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
  down: "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z",
  reply: "M10 9V5l-7 7 7 7v-4.1c5 0 8.5 1.6 11 5.1-1-5-4-10-11-11z",
  bookmark: "M17 3H7c-1.1 0-1.99.9-1.99 2L5 21l7-3 7 3V5c0-1.1-.9-2-2-2z",
  work: "M14 6V4h-4v2h4zM4 8v11h16V8H4zm16-2c1.11 0 2 .89 2 2v11c0 1.11-.89 2-2 2H4c-1.11 0-2-.89-2-2l.01-11c0-1.11.88-2 1.99-2h4V4c0-1.11.89-2 2-2h4c1.11 0 2 .89 2 2v2h4z",
  robot: "M20 9V7c0-1.1-.9-2-2-2h-3c0-1.66-1.34-3-3-3S9 3.34 9 5H6c-1.1 0-2 .9-2 2v2c-1.66 0-3 1.34-3 3s1.34 3 3 3v4c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4c1.66 0 3-1.34 3-3s-1.34-3-3-3zM7.5 11.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5S9.83 13 9 13s-1.5-.67-1.5-1.5zM16 17H8v-2h8v2zm-1-4c-.83 0-1.5-.67-1.5-1.5S14.17 10 15 10s1.5.67 1.5 1.5S15.83 13 15 13z",
  settings: "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z",
  review: "M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 14v-2.47l6.88-6.88c.2-.2.51-.2.71 0l1.77 1.77c.2.2.2.51 0 .71L8.47 14H6zm12 0h-7.5l2-2H18v2z",
  play: "M8 5v14l11-7z",
  pause: "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
  file: "M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z",
  download: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
  place: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 0 1 0-5 2.5 2.5 0 0 1 0 5z",
  call: "M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.98.98 0 0 0-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z",
  archive: "M20.54 5.23l-1.39-1.68C18.88 3.21 18.47 3 18 3H6c-.47 0-.88.21-1.16.55L3.46 5.23C3.17 5.57 3 6.02 3 6.5V19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6.5c0-.48-.17-.93-.46-1.27zM12 17.5L6.5 12H10v-2h4v2h3.5L12 17.5zM5.12 5l.81-1h12l.94 1H5.12z",
  unarchive: "M20.55 5.22l-1.39-1.68C18.88 3.21 18.47 3 18 3H6c-.47 0-.88.21-1.15.55L3.46 5.22C3.17 5.57 3 6.01 3 6.5V19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6.5c0-.49-.17-.93-.45-1.28zM12 9.5l5.5 5.5H14v2h-4v-2H6.5L12 9.5zM5.12 5l.82-1h12l.93 1H5.12z",
  bellOff: "M20 18.69L7.84 6.14 5.27 3.49 4 4.76l2.8 2.8v.01c-.52.99-.8 2.16-.8 3.42v5l-2 2v1h13.73l2 2L21 19.72l-1-1.03zM12 22c1.11 0 2-.89 2-2h-4c0 1.11.89 2 2 2zm6-7.32V11c0-3.08-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68c-.15.03-.29.08-.42.12-.1.03-.2.07-.3.11h-.01l-.02.01c-.23.09-.46.2-.68.31L18 14.68z",
  bell: "M18 11c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2v-5zm-6 11c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2z",
  markRead: "M17.34 20l-3.54-3.54 1.41-1.41 2.12 2.12 4.24-4.24L23 14.34 17.34 20zM12 17c0-3.87 3.13-7 7-7 1.08 0 2.09.25 3 .68V4c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v18l4-4h6c0-.17.01-.33.03-.5-.02-.16-.03-.33-.03-.5z",
  markUnread: "M22 6.98V16c0 1.1-.9 2-2 2H6l-4 4V4c0-1.1.9-2 2-2h10.1c-.06.32-.1.66-.1 1 0 2.76 2.24 5 5 5 1.13 0 2.16-.39 3-1.02zM16 3c0 1.66 1.34 3 3 3s3-1.34 3-3-1.34-3-3-3-3 1.34-3 3z",
  person: "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
  openExternal: "M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z",
};
function icon(name, size = 24, cls = "") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("class", "ic " + cls);
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", PATHS[name]);
  svg.append(path);
  return svg;
}
function iconButton(name, title, onclick, cls = "") {
  return h("button", { class: "ib " + cls, title, "aria-label": title, onclick }, icon(name));
}
function tailSvg() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "tail");
  svg.setAttribute("width", "17");
  svg.setAttribute("height", "12");
  svg.setAttribute("viewBox", "0 0 17 12");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M7 0Q6.3 9.6 0 12L16.6 12Z");
  svg.append(path);
  return svg;
}

const timers = {};
function debounce(key, fn, ms) { clearTimeout(timers[key]); timers[key] = setTimeout(fn, ms); }

async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: {} };
  if (init.method !== "GET") {
    init.headers["x-foxygram"] = "1";
    init.headers["content-type"] = "application/json";
    init.body = JSON.stringify(options.body || {});
  }
  if (options.keepalive) init.keepalive = true;
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail; } catch {}
    throw new Error(typeof detail === "string" && detail ? detail : "ошибка " + response.status);
  }
  return response.json();
}
const post = (path, body) => api(path, { method: "POST", body });

let toastTimer = 0;
function toast(text) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const el = h("div", { class: "toast", text });
  document.body.append(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 3500);
}

// ---------- theme ----------
const AVATAR = {
  dark: ["#8957E5", "#1F6FEB", "#238636", "#9E6A03", "#DA3633", "#BF3989", "#0E7C86", "#6E7681"],
  light: ["#8250DF", "#0969DA", "#1A7F37", "#9A6700", "#CF222E", "#BF3989", "#0E7C86", "#6E7781"],
};
const NAME = {
  dark: ["#FF7B72", "#FFA657", "#D2A8FF", "#3FB950", "#39C5CF", "#79C0FF", "#F778BA"],
  light: ["#CF222E", "#BC4C00", "#8250DF", "#1A7F37", "#0E7C86", "#0969DA", "#BF3989"],
};
const darkQuery = matchMedia("(prefers-color-scheme: dark)");
const themeMode = () => LS.get("theme", "dark");
const theme = () => { const m = themeMode(); return m === "system" ? (darkQuery.matches ? "dark" : "light") : m; };
const pick = (list, i) => list[((Number(i) || 0) % list.length + list.length) % list.length];
const avatarColor = i => pick(AVATAR[theme()], i);
const nameColor = i => pick(NAME[theme()], i);
function applyTheme() { document.documentElement.dataset.theme = theme(); }
darkQuery.addEventListener("change", () => { if (themeMode() === "system") { applyTheme(); rerender(); } });
applyTheme();

// ---------- formatting, as on the phone ----------
const fmtClock = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const fmtWeekday = new Intl.DateTimeFormat("ru-RU", { weekday: "short" });
const fmtDay = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
const fmtLong = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
const fmtLongYear = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
const fmtShortYear = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
const dayOf = epoch => { const d = new Date(epoch * 1000); return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 86400000); };
const today = () => dayOf(Date.now() / 1000);
const clock = epoch => fmtClock.format(new Date(epoch * 1000));
function listTime(epoch) {
  if (!epoch) return "";
  const moment = new Date(epoch * 1000);
  const days = today() - dayOf(epoch);
  if (days === 0) return clock(epoch);
  if (days > 0 && days < 7) { const w = fmtWeekday.format(moment); return w.charAt(0).toUpperCase() + w.slice(1); }
  if (moment.getFullYear() === new Date().getFullYear()) return fmtDay.format(moment).replace(/\.$/, "");
  return fmtShortYear.format(moment);
}
function dayHeader(epoch) {
  const days = today() - dayOf(epoch);
  if (days === 0) return "Сегодня";
  if (days === 1) return "Вчера";
  const moment = new Date(epoch * 1000);
  const same = moment.getFullYear() === new Date().getFullYear();
  return (same ? fmtLong : fmtLongYear).format(moment).replace(/\s*г\.$/, "");
}
function duration(seconds) {
  seconds = Math.max(0, Math.round(seconds || 0));
  const m = Math.floor(seconds / 60), s = String(seconds % 60).padStart(2, "0");
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
function fileSize(bytes) {
  const f = n => n.toLocaleString("ru-RU", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  if (bytes >= 1073741824) return f(bytes / 1073741824) + " ГБ";
  if (bytes >= 1048576) return f(bytes / 1048576) + " МБ";
  if (bytes >= 1024) return Math.round(bytes / 1024) + " КБ";
  return bytes + " Б";
}
function count(n) { return n >= 1e6 ? Math.floor(n / 1e6) + "M" : n >= 1e4 ? Math.floor(n / 1000) + "K" : String(n); }
function plural(n, one, few, many) {
  const m100 = n % 100, m10 = n % 10;
  if (m100 >= 11 && m100 <= 14) return many;
  if (m10 === 1) return one;
  if (m10 >= 2 && m10 <= 4) return few;
  return many;
}
function initials(title) {
  const words = (title || "").trim().split(/\s+/).filter(w => /^[\p{L}\p{N}]/u.test(w));
  const first = w => Array.from(w)[0] || "";
  if (words.length === 0) return first(title || "?").toUpperCase();
  if (words.length === 1) return first(words[0]).toUpperCase();
  return (first(words[0]) + first(words[1])).toUpperCase();
}
const soft = (color, alpha) => `color-mix(in srgb, ${color} ${Math.round(alpha * 100)}%, transparent)`;

// ---------- images: the server downloads from Telegram on demand, so only a few load at a time ----------
const fileUrl = (id, name, download) => {
  const q = new URLSearchParams();
  if (name) q.set("name", name);
  if (download) q.set("download", "1");
  const s = q.toString();
  return `/app/api/files/${id}` + (s ? "?" + s : "");
};
const loaded = new Set();
const imageQueue = [];
let imagesActive = 0;
const lazy = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    lazy.unobserve(entry.target);
    queueMedia(entry.target);
  }
}, { rootMargin: "300px" });
function queueMedia(el) {
  const src = el.dataset.src;
  if (!src) return;
  if (el.tagName === "VIDEO" || loaded.has(src)) { start(el); return; }
  imageQueue.push(el);
  pumpImages();
}
function start(el, done) {
  const src = el.dataset.src;
  el.addEventListener("load", () => { loaded.add(src); el.classList.add("ok"); done && done(); }, { once: true });
  el.addEventListener("error", () => { el.remove(); done && done(); }, { once: true });
  el.src = src;
  delete el.dataset.src;
}
function pumpImages() {
  while (imagesActive < 3 && imageQueue.length) {
    const el = imageQueue.shift();
    if (!el.isConnected || !el.dataset.src) continue;
    imagesActive++;
    start(el, () => { imagesActive--; pumpImages(); });
  }
}
function lazyImage(fileId, cls, name) {
  if (!fileId) return null;
  const el = h("img", { class: cls || "", alt: "", draggable: "false" });
  el.dataset.src = fileUrl(fileId, name);
  lazy.observe(el);
  return el;
}
function miniImage(image, cls) {
  return image && image.mini ? h("img", { class: cls, alt: "", src: "data:image/jpeg;base64," + image.mini }) : null;
}
function avatar(title, photo, color, size, kind) {
  const el = h("div", { class: "av", style: `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.36)}px;background:${avatarColor(color)}` });
  if (kind === "saved") { el.append(icon("bookmark", Math.round(size * 0.5))); return el; }
  el.append(initials(title));
  if (photo && photo.file) el.append(lazyImage(photo.file));
  return el;
}

// ---------- app state ----------
const S = {
  state: null,
  folders: [{ key: "main", title: "Все", unread: 0 }],
  folder: LS.get("folder", "main"),
  chats: [],
  results: null,
  searching: false,
  stack: [],
  live: false,
  drafts: {},
  projects: null,
};
const listPane = document.getElementById("listPane");
const mainPane = document.getElementById("mainPane");
const overlays = document.getElementById("overlays");
const markReadOn = () => LS.get("markRead", true);
const topRoute = () => S.stack[S.stack.length - 1] || null;

function rerender() {
  renderList(true);
  if (CV) { CV.rows = new Map(); renderFeed(); renderHeader(); }
}

// ---------- chat list ----------
let listEls = { rows: new Map() };
function renderListShell() {
  listPane.replaceChildren();
  const head = h("div", { style: "background:var(--surface);flex:none" });
  const scroller = h("div", { class: "list" });
  listPane.append(head, scroller);
  listEls = { head, scroller, rows: new Map() };
  renderListHead();
}
function renderListHead() {
  const head = listEls.head;
  head.replaceChildren();
  if (S.searching) {
    const input = h("input", { class: "search-input", placeholder: "Поиск", oninput: e => runSearch(e.target.value) });
    head.append(h("div", { class: "bar" },
      iconButton("back", "Назад", () => { S.searching = false; S.results = null; renderListHead(); renderList(); }),
      input,
      iconButton("close", "Очистить", () => { input.value = ""; runSearch(""); input.focus(); }, "dim")));
    setTimeout(() => input.focus(), 0);
    return;
  }
  const title = !S.live ? "Соединение с сервером…" : (S.state && S.state.connection) || "FoxyGram";
  head.append(h("div", { class: "bar" },
    iconButton("menu", "Меню", openDrawer),
    h("div", { class: "bar-title", text: title }),
    iconButton("search", "Поиск", () => { S.searching = true; renderListHead(); })));
  if (S.folders.length > 1) {
    const bar = h("div", { class: "folders" });
    for (const folder of S.folders) {
      const active = folder.key === S.folder;
      bar.append(h("div", {
        class: "folder" + (active ? " active" : ""),
        onclick: () => selectFolder(folder.key),
        oncontextmenu: e => { e.preventDefault(); contextMenu(e, [["Прочитать всё", () => readList(folder.key)]]); },
      }, folder.title, folder.unread > 0 ? h("span", { class: "badge small" + (active ? "" : " muted"), text: count(folder.unread) }) : null));
    }
    head.append(bar);
  }
}
function runSearch(query) {
  debounce("search", async () => {
    if (!query.trim()) { S.results = null; renderList(); return; }
    try { S.results = (await api("/app/api/search?q=" + encodeURIComponent(query))).chats; } catch { S.results = []; }
    renderList();
  }, 250);
}
function selectFolder(key) {
  if (S.folder === key) return;
  S.folder = key;
  LS.set("folder", key);
  renderListHead();
  loadChats().then(() => { listEls.scroller.scrollTop = 0; });
}
async function readList(key) {
  try { await post(`/app/api/lists/${key}/read`); } catch (e) { toast("Не удалось: " + e.message); }
}
async function loadChats() {
  try {
    const data = await api("/app/api/chats?list=" + encodeURIComponent(S.folder));
    S.chats = data.chats;
    const changedTabs = JSON.stringify(S.folders) !== JSON.stringify(data.folders);
    S.folders = data.folders;
    if (S.state) S.state.connection = data.connection;
    if (!S.folders.some(f => f.key === S.folder)) { S.folder = "main"; LS.set("folder", "main"); return loadChats(); }
    if (changedTabs && !S.searching) renderListHead();
    renderList();
    const total = (S.folders[0] || {}).unread || 0;
    document.title = total ? `(${total}) FoxyGram` : "FoxyGram";
  } catch {
    debounce("state", loadState, 1000);
  }
}
function renderList(force) {
  const list = S.searching && S.results ? S.results : S.chats;
  const old = force ? new Map() : listEls.rows;
  const next = new Map();
  const kids = [];
  const route = topRoute();
  const selected = route && (route.name === "chat" || route.name === "topics") ? route.id : null;
  for (const chat of list) {
    const sig = JSON.stringify(chat) + (chat.id === selected ? "*" : "");
    let rec = old.get(chat.id);
    if (!rec || rec.sig !== sig) rec = { el: chatRow(chat, chat.id === selected), sig };
    next.set(chat.id, rec);
    kids.push(rec.el);
  }
  listEls.scroller.replaceChildren(...kids);
  if (S.searching && S.results && !list.length) listEls.scroller.append(h("div", { class: "note", text: "Ничего не найдено" }));
  listEls.rows = next;
}
function chatRow(chat, selected) {
  const label = chat.label;
  const line1 = h("div", { class: "rl" },
    h("div", { class: "rl grow" },
      h("span", { class: "rtitle", text: chat.title }),
      chat.verified ? h("span", { style: "margin-left:3px;color:var(--accent);display:flex" }, icon("verified", 15)) : null,
      chat.muted ? h("span", { style: "margin-left:3px;color:var(--text2);display:flex" }, icon("volumeOff", 14)) : null),
    statusIcon(chat.status),
    h("span", { class: "rtime", text: listTime(chat.date) }));
  const preview = h("span", { class: "prev" });
  if (chat.draft) {
    preview.append(h("span", { class: "draft", text: "Черновик: " }), chat.draft);
  } else {
    if (chat.sender) preview.append(h("span", { class: "who", text: chat.sender + ": " }));
    preview.append(chat.preview_label ? h("span", { class: "lbl", text: chat.preview }) : chat.preview);
  }
  const bottom = h("div", { class: "rl" },
    label && label.needs_reply ? h("div", { class: "dot" + (label.urgent ? " urgent" : "") }) : null,
    label && label.project ? labelPill(label.project, label.project_color || "var(--accent)", "margin-right:5px") : null,
    chat.thumb ? lazyImage(chat.thumb.file, "pthumb") : null,
    preview,
    chat.reactions > 0 ? h("div", { class: "circle", style: "background:var(--danger)" }, icon("heart", 12)) : null,
    chat.mentions > 0 ? h("div", { class: "circle", style: "background:var(--accent)", text: "@" }) : null,
    chat.unread > 0 ? h("span", { class: "badge" + (chat.muted ? " muted" : ""), style: "margin-left:6px", text: count(chat.unread) })
      : chat.pinned ? h("span", { style: "margin-left:6px;color:var(--text2);display:flex" }, icon("pin", 18)) : null);
  return h("div", {
    class: "row" + (selected ? " sel" : ""),
    // A group with topics opens on its list of topics, as on the phone.
    onclick: () => openFromList(chat.forum ? { name: "topics", id: chat.id, title: chat.title } : { name: "chat", id: chat.id }),
    oncontextmenu: e => { e.preventDefault(); chatSheet(chat, S.folder); },
  }, avatar(chat.title, chat.photo, chat.color, 56, chat.kind), h("div", { class: "rb" }, line1, bottom));
}
function statusIcon(status) {
  const wrap = (name, size, color) => h("span", { style: `margin-left:6px;color:${color};display:flex` }, icon(name, size));
  if (status === "read") return wrap("doneAll", 16, "var(--accent)");
  if (status === "sent") return wrap("check", 16, "var(--accent)");
  if (status === "sending") return wrap("clock", 14, "var(--text2)");
  if (status === "failed") return wrap("error", 16, "var(--danger)");
  return null;
}
function labelPill(text, color, style = "") {
  return h("span", { class: "pill", style: `color:${color};background:${soft(color, 0.16)};${style}`, text });
}

// ---------- navigation ----------
function go(route, replace) {
  const stack = replace ? [...S.stack.slice(0, -1), route] : [...S.stack, route];
  setStack(stack, replace ? "replace" : "push");
}
function setStack(stack, how) {
  S.stack = stack;
  if (how === "push") history.pushState({ stack }, "");
  else if (how === "replace") history.replaceState({ stack }, "");
  renderMain();
}
function back() {
  if (S.stack.length) history.back();
}
window.addEventListener("popstate", e => {
  S.stack = (e.state && e.state.stack) || [];
  renderMain();
});
function sameRoute(a, b) {
  return !!a && !!b && a.name === b.name && a.id === b.id && (a.topic || 0) === (b.topic || 0);
}
// From the chat list: whatever was open on the right is replaced, not stacked.
function openFromList(route) {
  if (sameRoute(topRoute(), route)) return;
  if (S.stack.length) setStack([route], "replace");
  else go(route);
}
// From inside a screen (a case, a topic list): back returns to that screen.
function openChat(id, topic = 0, title = null) {
  const route = topic ? { name: "chat", id, topic, title } : { name: "chat", id };
  if (!sameRoute(topRoute(), route)) go(route);
}
function renderMain() {
  const route = topRoute();
  document.body.classList.toggle("routed", !!route);
  if (!route || route.name !== "chat" || !CV || CV.id !== route.id || CV.topic !== (route.topic || 0)) closeChatView();
  TV = null;
  if (!route) {
    mainPane.replaceChildren(h("div", { class: "empty-main" }, h("div", { class: "svc", text: "Выберите чат" })));
  } else if (route.name === "chat") {
    if (!CV) openChatView(route.id, route.topic || 0, route.title || null);
  } else if (route.name === "topics") topicsScreen(route.id, route.title);
  else if (route.name === "cases") casesScreen();
  else if (route.name === "case") caseScreen(route.id);
  else if (route.name === "review") reviewScreen();
  else if (route.name === "ai") aiChatsScreen();
  else if (route.name === "settings") settingsScreen();
  renderList();
}

// ---------- overlays ----------
function closeOverlays() { overlays.replaceChildren(); }
function openDrawer() {
  closeOverlays();
  const item = (name, title, route) => h("div", { class: "ditem", onclick: () => { closeOverlays(); go(route); } }, icon(name), title);
  overlays.append(
    h("div", { class: "scrim", onclick: closeOverlays }),
    h("nav", { class: "drawer" },
      h("div", { class: "drawer-title", text: "FoxyGram" }),
      h("div", { class: "divider" }),
      item("work", "Дела", { name: "cases" }),
      item("review", "Проверить", { name: "review" }),
      item("robot", "Чаты для Claude", { name: "ai" }),
      item("settings", "Настройки", { name: "settings" })));
}
function contextMenu(event, items) {
  closeOverlays();
  const menu = h("div", { class: "menu" }, items.map(([title, action]) => h("div", { text: title, onclick: () => { closeOverlays(); action(); } })));
  overlays.append(h("div", { class: "scrim", style: "background:transparent", onclick: closeOverlays, oncontextmenu: e => { e.preventDefault(); closeOverlays(); } }), menu);
  const x = Math.min(event.clientX, innerWidth - menu.offsetWidth - 8);
  const y = Math.min(event.clientY, innerHeight - menu.offsetHeight - 8);
  menu.style.left = x + "px";
  menu.style.top = y + "px";
}
function openSheet(...content) {
  closeOverlays();
  const sheet = h("div", { class: "sheet" }, h("div", { class: "handle" }), content);
  overlays.append(h("div", { class: "scrim", onclick: closeOverlays }), sheet);
  return sheet;
}
function sheetRow(name, title, action, danger) {
  return h("div", { class: "srow" + (danger ? " danger" : ""), onclick: action }, icon(name), title);
}
function switchEl(on, onchange) {
  const el = h("button", { class: "sw" + (on ? " on" : ""), role: "switch", "aria-checked": on ? "true" : "false" });
  el.addEventListener("click", e => {
    e.stopPropagation();
    const value = !el.classList.contains("on");
    el.classList.toggle("on", value);
    el.setAttribute("aria-checked", value ? "true" : "false");
    onchange(value);
  });
  return el;
}
async function projects() {
  if (!S.projects) S.projects = await api("/v1/projects");
  return S.projects;
}
async function setChat(chatId, body, list) {
  try { await post(`/app/api/chats/${chatId}/settings`, { list: list || "main", ...body }); }
  catch (e) { toast("Не удалось: " + e.message); }
}
async function patchServerChat(chatId, body) {
  try { await post(`/v1/chats/${chatId}`, body); loadChats(); if (CV && CV.id === chatId) refreshHeader(); }
  catch (e) { toast("Не удалось: " + e.message); }
}
function chatSheet(chat, list) {
  const act = fn => () => { closeOverlays(); fn(); };
  const label = chat.label || {};
  const claude = h("div");
  const sheet = openSheet(
    h("div", { class: "sheet-title", text: chat.title }),
    chat.unread > 0
      ? sheetRow("markRead", "Отметить прочитанным", act(() => setChat(chat.id, { unread: false })))
      : sheetRow("markUnread", "Отметить непрочитанным", act(() => setChat(chat.id, { unread: true }))),
    sheetRow("pin", chat.pinned ? "Открепить" : "Закрепить", act(() => setChat(chat.id, { pinned: !chat.pinned }, list))),
    sheetRow(chat.muted ? "bell" : "bellOff", chat.muted ? "Включить уведомления" : "Без звука", act(() => setChat(chat.id, { muted: !chat.muted }))),
    sheetRow(chat.archived ? "unarchive" : "archive", chat.archived ? "Вернуть из архива" : "В архив", act(() => setChat(chat.id, { archived: !chat.archived }))),
    claude,
    brainJobs(chat));
  claude.append(
    h("div", { class: "divider", style: "margin:6px 0" }),
    h("div", { class: "srow", style: "cursor:default" }, icon("robot"),
      h("div", { class: "grow" },
        h("div", { text: "Анализировать в Claude" }),
        h("div", { style: "font-size:13px;color:var(--text2)", text: "Сообщения этого чата пойдут на ваш компьютер и в Claude" })),
      switchEl(!!label.ai, value => patchServerChat(chat.id, { ai_enabled: value }))));
  projects().then(list => {
    if (!sheet.isConnected) return;
    let current = list.find(p => p.name === label.project) || null;
    const projectChips = h("div", { class: "chips" });
    const categoryBox = h("div");
    const drawCategories = () => {
      categoryBox.replaceChildren();
      if (!current || !current.categories.length) return;
      let category = label.category;
      const chips = h("div", { class: "chips" });
      const options = [["Без категории", null], ...current.categories.map(c => [c.name, c.id])];
      const draw = () => chips.replaceChildren(...options.map(([name, id]) => h("button", {
        class: "chip" + ((category || "Без категории") === name ? " on" : ""),
        onclick: () => { category = id === null ? null : name; draw(); patchServerChat(chat.id, { category_id: id }); },
      }, name)));
      draw();
      categoryBox.append(h("div", { class: "ptitle", text: "Категория" }), chips);
    };
    const options = [["Без проекта", null], ...list.map(p => [p.name, p])];
    const drawProjects = () => projectChips.replaceChildren(...options.map(([name, project]) => h("button", {
      class: "chip" + ((current ? current.name : "Без проекта") === name ? " on" : ""),
      onclick: () => {
        current = project;
        label.category = null;
        drawProjects();
        drawCategories();
        patchServerChat(chat.id, { project_id: project ? project.id : null });
      },
    }, name)));
    drawProjects();
    drawCategories();
    claude.append(h("div", { class: "ptitle", text: "Проект" }), projectChips, categoryBox, h("div", { style: "height:12px" }));
  }).catch(() => {});
}
// Brain jobs: which of Brain's jobs get this chat. Like Brain's own /chats page: one switch per job, a note when a
// Telegram folder brings the chat in, and "follow folders only" once the chat has changes of its own.
function brainJobs(chat) {
  const body = h("div");
  const box = h("div", {}, h("div", { class: "divider", style: "margin:6px 0" }), h("div", { class: "ptitle", text: "Работы в Brain" }), body);
  let data = null;
  const note = text => body.replaceChildren(h("div", { class: "brain-note", text }));
  const draw = () => {
    const c = data.chat;
    if (!data.jobs.length) { note("В Brain нет включённых работ."); return; }
    body.replaceChildren(...data.jobs.map(job => {
      const on = c.jobs.includes(job.id);
      const viaFolder = c.viaFolder.includes(job.id);
      const removed = c.removed.includes(job.id);
      const hint = on && viaFolder ? "из папки" : removed ? "убран, хотя папка его добавляет" : "";
      return h("div", { class: "srow", style: "cursor:default;padding:8px 20px" },
        h("div", { class: "grow" }, h("div", { text: job.name }), hint ? h("div", { class: "brain-hint", text: hint }) : null),
        switchEl(on, value => change(`/v1/brain/chats/${chat.id}/jobs`, { job_id: job.id, on: value })));
    }));
    if (c.added.length || c.removed.length) {
      body.append(h("div", { style: "padding:0 8px" },
        h("button", { class: "tbtn", title: "Забыть изменения для этого чата", text: "Только по папкам",
          onclick: () => change(`/v1/brain/chats/${chat.id}/reset`, {}) })));
    }
    if (!data.connected) body.append(h("div", { class: "brain-note", text: "Brain сейчас не подключён к Telegram." }));
  };
  async function change(path, payload) {
    try {
      const result = await post(path, payload);
      if (result.text) toast(result.text);
      if (data && result.chat) { data.chat = result.chat; draw(); }
    } catch (e) {
      toast(e.message);
      load();
    }
  }
  async function load() {
    if (!data) note("Загрузка…");
    try { data = await api(`/v1/brain/chats/${chat.id}`); draw(); }
    catch (e) { data = null; note(e.message); }
  }
  load();
  return box;
}
function viewer(kind, fileId, name) {
  closeOverlays();
  const loading = h("div", { class: "loading", text: "Загрузка…" });
  const src = fileUrl(fileId, name);
  const media = kind === "video"
    ? h("video", { src, controls: true, autoplay: true, playsinline: true, onloadeddata: () => loading.remove(), onerror: () => { loading.textContent = "Не удалось загрузить"; } })
    : h("img", { src, alt: "", onload: () => loading.remove(), onerror: () => { loading.textContent = "Не удалось загрузить"; } });
  overlays.append(h("div", { class: "viewer", onclick: e => { if (e.target.classList.contains("viewer")) closeOverlays(); } },
    loading, media,
    h("div", { class: "vbar" },
      h("a", { class: "ib", href: fileUrl(fileId, name, true), title: "Скачать", "aria-label": "Скачать", download: name || "" }, icon("download")),
      iconButton("close", "Закрыть", closeOverlays))));
}
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (overlays.childElementCount) { closeOverlays(); return; }
  if (CV && CV.replyTo) { setReply(null); return; }
  if (S.searching) { S.searching = false; S.results = null; renderListHead(); renderList(); return; }
  if (document.activeElement && document.activeElement.tagName === "TEXTAREA") return;
  back();
});

// ---------- one open chat ----------
let CV = null;
// A topic of a group opens as a chat of its own; these say which one for every call.
const topicQuery = view => view.topic ? `&topic=${view.topic}` : "";
const draftKey = view => `${view.id}:${view.topic}`;
function closeChatView() {
  if (!CV) return;
  const view = CV;
  CV = null;
  view.readObserver.disconnect();
  clearTimeout(view.brainTimer);
  if (view.textarea) S.drafts[draftKey(view)] = view.textarea.value;
  api(`/app/api/chats/${view.id}/close`, { method: "POST", keepalive: true }).catch(() => {});
}
async function openChatView(id, topic = 0, topicTitle = null) {
  closeChatView();
  const view = {
    id, topic, topicTitle, chat: null, subtitle: null, lastRead: 0, unread: 0, msgs: new Map(), rows: new Map(),
    oldest: false, loadingOlder: false, replyTo: null, firstUnread: null, stickBottom: true, pendingRead: new Set(),
  };
  CV = view;
  view.head = h("div", { class: "chead" });
  view.inner = h("div", { class: "feed-inner" });
  view.scroller = h("div", { class: "feed" }, view.inner);
  view.down = h("button", { class: "down hidden", title: "Вниз", onclick: () => { view.scroller.scrollTop = view.scroller.scrollHeight; } }, icon("down"));
  view.composer = h("div", { class: "composer" });
  // The chat on the left, and Brain's side panel on the right once Brain says this chat is in one of its jobs.
  view.wrap = h("div", { class: "chat-wrap" },
    h("div", { class: "screen" }, view.head, h("div", { class: "feedbox" }, view.scroller, view.down), view.composer));
  mainPane.replaceChildren(view.wrap);
  view.readObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const mid of (entry.target.dataset.ids || "").split(",")) if (mid) view.pendingRead.add(Number(mid));
    }
    scheduleRead();
  }, { root: view.scroller, threshold: 0.15 });
  view.scroller.addEventListener("scroll", () => {
    const gap = view.scroller.scrollHeight - view.scroller.scrollTop - view.scroller.clientHeight;
    view.down.classList.toggle("hidden", gap < 300);
    if (view.scroller.scrollTop < 400) loadOlder();
  });
  renderComposer();
  renderList();
  try {
    const [detail, topicInfo] = await Promise.all([
      api(`/app/api/chats/${id}`),
      topic ? api(`/app/api/chats/${id}/topics/${topic}`).then(r => r.topic) : Promise.resolve(null),
    ]);
    if (CV !== view) return;
    view.chat = detail.chat;
    view.subtitle = detail.subtitle;
    view.lastRead = topicInfo ? topicInfo.last_read_inbox : detail.last_read_inbox || 0;
    view.unread = topicInfo ? topicInfo.unread : detail.chat.unread;
    if (topicInfo) view.topicTitle = topicInfo.title;
    renderHeader();
    post(`/app/api/chats/${id}/open`).catch(() => {});
    loadBrainPanel(view);
    await loadNewest(true);
  } catch (e) {
    if (CV === view) view.inner.replaceChildren(h("div", { class: "svc", text: "Не удалось открыть чат: " + e.message }));
  }
}
async function refreshHeader() {
  const view = CV;
  if (!view) return;
  try {
    const [detail, topicInfo] = await Promise.all([
      api(`/app/api/chats/${view.id}`),
      view.topic ? api(`/app/api/chats/${view.id}/topics/${view.topic}`).then(r => r.topic) : Promise.resolve(null),
    ]);
    if (CV !== view) return;
    view.chat = detail.chat;
    view.subtitle = detail.subtitle;
    view.unread = topicInfo ? topicInfo.unread : detail.chat.unread;
    renderHeader();
  } catch {}
}
function renderHeader() {
  const view = CV;
  if (!view || !view.chat) return;
  const chat = view.chat;
  const sub = view.subtitle || { text: "" };
  // In a topic the topic is the title and its group the line under it, as on the phone.
  const title = view.topic ? view.topicTitle || "Тема" : chat.title;
  const subText = view.topic ? chat.title : sub.seen ? `${sub.text} ${listTime(sub.seen)}` : sub.text;
  view.head.replaceChildren(h("div", { class: "chead-row" },
    iconButton("back", "Назад", back),
    h("div", { class: "chead-main", onclick: () => chatSheet(chat, "main") },
      avatar(title, chat.photo, chat.color, 40, chat.kind),
      h("div", { style: "min-width:0" },
        h("div", { class: "chead-title", text: title }),
        subText ? h("div", { class: "chead-sub", text: subText }) : null)),
    view.brain ? iconButton("robot", "Brain", () => toggleBrainPanel(view), view.panel && !view.panel.classList.contains("closed") ? "on" : "dim") : null,
    iconButton("more", "Ещё", () => chatSheet(chat, "main"))));
  const label = chat.label;
  if (label && label.case_title) {
    view.head.append(h("div", { class: "case-line", onclick: () => go({ name: "case", id: label.case_id }) },
      labelPill("Дело", "var(--accent)"), h("span", { text: label.case_title })));
  }
  const badge = view.down.querySelector(".badge");
  if (badge) badge.remove();
  if (view.unread > 0) view.down.append(h("span", { class: "badge small", text: count(view.unread) }));
}
function sortedIds(view) { return [...view.msgs.keys()].sort((a, b) => a - b); }
async function loadNewest(initial) {
  const view = CV;
  if (!view) return;
  let page;
  try { page = (await api(`/app/api/chats/${view.id}/messages?limit=50${topicQuery(view)}`)).messages; } catch { return; }
  if (CV !== view) return;
  if (page.length) {
    const ids = new Set(page.map(m => m.id));
    const lowest = Math.min(...ids);
    for (const mid of [...view.msgs.keys()]) if (mid >= lowest && !ids.has(mid)) view.msgs.delete(mid);
    for (const m of page) view.msgs.set(m.id, m);
  } else if (initial) {
    view.oldest = true;
  }
  if (initial) {
    await findUnread(view);
    if (CV !== view) return;
  }
  renderFeed();
  if (initial) {
    const marker = view.rows.get("u");
    if (marker) {
      view.scroller.scrollTop = marker.el.offsetTop - 60;
      view.stickBottom = false;
    } else {
      view.scroller.scrollTop = view.scroller.scrollHeight;
    }
    if (view.scroller.scrollTop < 400) loadOlder();
  }
}
async function findUnread(view) {
  if (!view.unread || !view.lastRead) return;
  // Load back to the last read message, a few pages at most, so the unread line can sit where it belongs.
  for (let round = 0; round < 4 && !view.oldest; round++) {
    const ids = sortedIds(view);
    if (ids.length && ids[0] <= view.lastRead) break;
    await loadOlderPage(view);
    if (CV !== view) return;
  }
  view.firstUnread = sortedIds(view).find(mid => mid > view.lastRead && !view.msgs.get(mid).out) || null;
}
async function loadOlderPage(view) {
  const from = sortedIds(view)[0] || 0;
  if (!from) { view.oldest = true; return; }
  let page;
  try { page = (await api(`/app/api/chats/${view.id}/messages?from=${from}&limit=50${topicQuery(view)}`)).messages; } catch { return; }
  if (CV !== view) return;
  const before = view.msgs.size;
  for (const m of page) view.msgs.set(m.id, m);
  if (view.msgs.size === before) view.oldest = true;
}
async function loadOlder() {
  const view = CV;
  if (!view || view.loadingOlder || view.oldest || !view.msgs.size) return;
  view.loadingOlder = true;
  await loadOlderPage(view);
  view.loadingOlder = false;
  if (CV === view) renderFeed();
}

// The feed, built like model/Feed.kt: albums merged, runs from one sender grouped, day pills, the unread line.
function sameGroup(older, newer) {
  if (older.body.type === "service" || newer.body.type === "service") return false;
  if (older.out !== newer.out) return false;
  if ((older.sender && older.sender.id) !== (newer.sender && newer.sender.id)) return false;
  if (dayOf(older.date) !== dayOf(newer.date)) return false;
  return newer.date - older.date <= 300;
}
function buildFeed(view) {
  const list = sortedIds(view).map(mid => view.msgs.get(mid));
  const merged = [];
  for (let i = 0; i < list.length;) {
    const m = list[i];
    let j = i + 1;
    if (m.album !== "0") while (j < list.length && list[j].album === m.album) j++;
    if (j - i === 1) { merged.push(m); i = j; continue; }
    const members = list.slice(i, j);
    const withCaption = members.find(x => x.body.caption && x.body.caption.text.trim());
    const last = members[members.length - 1];
    merged.push({
      ...last,
      body: { type: "album", items: members.map(x => x.body), caption: withCaption ? withCaption.body.caption : { text: "", spans: [] } },
      reply: (members.find(x => x.reply) || {}).reply || null,
      ids: members.map(x => x.id),
      reactions: members.flatMap(x => x.reactions),
    });
    i = j;
  }
  const isGroup = view.chat && view.chat.kind === "group";
  const rows = [];
  for (let i = 0; i < merged.length; i++) {
    const cur = merged[i], older = merged[i - 1], newer = merged[i + 1];
    if (!older || dayOf(older.date) !== dayOf(cur.date)) rows.push({ t: "date", key: "d" + dayOf(cur.date), text: dayHeader(cur.date) });
    if (view.firstUnread !== null && (cur.ids || [cur.id]).includes(view.firstUnread)) rows.push({ t: "unread", key: "u" });
    const joinsOlder = !!older && sameGroup(older, cur);
    const joinsNewer = !!newer && sameGroup(cur, newer);
    const bare = cur.body.type === "sticker" || cur.body.type === "round";
    rows.push({
      t: "msg", key: "m" + cur.id, m: cur, starts: !joinsOlder, ends: !joinsNewer,
      name: isGroup && !cur.out && !joinsOlder && !bare, avatar: isGroup && !cur.out && !joinsNewer, group: isGroup,
    });
  }
  return rows;
}
function renderFeed() {
  const view = CV;
  if (!view) return;
  const sc = view.scroller;
  const atBottom = view.stickBottom || sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80;
  view.stickBottom = false;
  let anchor = null;
  if (!atBottom) {
    for (const [key, rec] of view.rows) {
      if (rec.el.offsetTop + rec.el.offsetHeight > sc.scrollTop) { anchor = { key, offset: rec.el.offsetTop - sc.scrollTop }; break; }
    }
  }
  const rows = buildFeed(view);
  const next = new Map();
  const kids = [];
  const mediaWidth = Math.max(200, Math.min(340, sc.clientWidth * 0.86 - 70));
  for (const row of rows) {
    const sig = row.t === "msg" ? JSON.stringify([row.m, row.starts, row.ends, row.name, row.avatar, mediaWidth]) : row.t + (row.text || "");
    let rec = view.rows.get(row.key);
    if (!rec || rec.sig !== sig) {
      const el = renderRow(row, mediaWidth);
      if (row.t === "msg" && !row.m.out) { el.dataset.ids = (row.m.ids || [row.m.id]).join(","); view.readObserver.observe(el); }
      rec = { el, sig, ids: row.t === "msg" ? (row.m.ids || [row.m.id]) : [] };
    }
    next.set(row.key, rec);
    kids.push(rec.el);
  }
  view.inner.replaceChildren(...kids);
  view.rows = next;
  if (!rows.length) view.inner.append(h("div", { class: "svc", text: view.oldest ? "Сообщений пока нет" : "Загрузка…" }));
  applyBrainMarks(view);
  if (atBottom) sc.scrollTop = sc.scrollHeight;
  else if (anchor && next.get(anchor.key)) sc.scrollTop = next.get(anchor.key).el.offsetTop - anchor.offset;
}

function renderRow(row, mediaWidth) {
  if (row.t === "date") return h("div", { class: "svc", text: row.text });
  if (row.t === "unread") return h("div", { class: "unread-line", text: "Непрочитанные сообщения" });
  const m = row.m;
  if (m.body.type === "service") return h("div", { class: "svc", text: m.body.text });
  const el = h("div", { class: "m" + (m.out ? " out" : "") + (row.starts ? " starts" : "") });
  if (row.group && !m.out) {
    if (row.avatar && m.sender) el.append(h("div", { class: "avslot" }, avatar(m.sender.name, m.sender.photo, m.sender.color, 38)));
    else el.append(h("div", { class: "avslot" }));
  }
  const bare = m.body.type === "sticker" || m.body.type === "round";
  el.append(bare ? bareMessage(m) : bubble(row, mediaWidth));
  el.addEventListener("dblclick", e => { if (!e.target.closest("a, .media, .round-btn, .wave")) setReply(m); });
  // In a chat Brain analyses, a click on a message shows what Brain made of it.
  el.addEventListener("click", e => {
    if (!CV || !CV.brain || e.target.closest("a, .media, button, .wave, .roundv, .quote-reply, .web, .spoiler, .bmark")) return;
    selectBrainMessage(CV, m.ids || [m.id]);
  });
  el.addEventListener("contextmenu", e => {
    if (e.target.closest("a")) return;
    e.preventDefault();
    const text = textOf(m);
    const items = [["Ответить", () => setReply(m)]];
    if (text) items.push(["Копировать текст", () => navigator.clipboard.writeText(text).then(() => toast("Скопировано"), () => toast("Не удалось скопировать"))]);
    contextMenu(e, items);
  });
  return el;
}
function textOf(m) {
  const b = m.body;
  return b.type === "text" ? b.text.text : (b.caption && b.caption.text) || "";
}
function radius(out, starts, ends) {
  const L = 17, s = 6;
  const topInner = starts ? L : s;
  const bottomInner = ends ? 0 : s;
  return out ? `${L}px ${topInner}px ${bottomInner}px ${L}px` : `${topInner}px ${L}px ${L}px ${bottomInner}px`;
}
function metaWidth(m) {
  let w = 44;
  if (m.out) w += 18;
  if (m.edited) w += 28;
  if (m.views > 0) w += 40;
  return w;
}
function meta(m, pill) {
  const el = h("div", { class: pill ? "metapill" : "meta" });
  if (m.views > 0) el.append(count(m.views) + "  ");
  if (m.edited) el.append("изм. ");
  el.append(clock(m.date));
  if (m.out) {
    if (m.state === "read") el.append(icon("doneAll", 15, "read"));
    else if (m.state === "sent") el.append(icon("check", 15));
    else if (m.state === "sending") el.append(icon("clock", 13));
    else if (m.state === "failed") el.append(icon("error", 15, "fail"));
  }
  return el;
}
function bubble(row, mediaWidth) {
  const m = row.m;
  const b = m.body;
  const visual = b.type === "photo" || b.type === "video" || b.type === "album";
  const caption = b.type === "text" ? b.text : (b.caption || { text: "", spans: [] });
  const hasHeader = (row.name && m.sender) || (m.forward !== null && m.forward !== undefined) || m.reply;
  const box = h("div", { class: "bub", style: `border-radius:${radius(m.out, row.starts, row.ends)};max-width:min(${m.out ? 82 : 86}%, 560px)` });
  const clip = h("div", { class: "clip" });
  box.append(clip);
  if (row.ends) box.append(tailSvg());
  if (hasHeader) {
    const head = h("div", { class: "bhead" + (visual ? " vis" : "") });
    if (row.name && m.sender) head.append(h("div", { class: "sname", style: `color:${nameColor(m.sender.color)}`, text: m.sender.name }));
    if (m.forward !== null && m.forward !== undefined) head.append(h("div", { class: "fwd", text: "Переслано от " + m.forward }));
    if (m.reply) head.append(replyQuote(m.reply, m.out));
    clip.append(head);
  }
  const hasText = caption.text.trim().length > 0;
  if (visual) {
    // A caption wraps at the photo's width, as on the phone.
    const media = visualMedia(m, b, mediaWidth, !hasText && !m.reactions.length);
    box.style.width = media.dataset.w + "px";
    clip.append(media);
  }
  const inset = insetBody(m, b);
  if (inset) clip.append(h("div", { class: "inset" }, inset));
  const tbox = h("div", { class: "tbox" });
  if (hasText) {
    const reserve = m.reactions.length || (b.type === "text" && b.web) ? 0 : metaWidth(m);
    tbox.append(h("div", { class: "txt" + (hasHeader && !visual ? " hd" : ""), style: `--mw:${reserve}px` }, richText(caption)));
  }
  if (b.type === "text" && b.web) tbox.append(webCard(b.web));
  if (m.reactions.length) tbox.append(reactions(m, false));
  else if (!hasText && !visual && b.type !== "text") tbox.append(h("div", { class: "spacer16" }));
  if (!(visual && !hasText && !m.reactions.length)) tbox.append(meta(m, false));
  clip.append(tbox);
  return box;
}
function replyQuote(reply, out) {
  const color = out ? "var(--link-out)" : nameColor(reply.color);
  return h("div", { class: "quote-reply", style: `background:${soft(color, 0.12)}`, onclick: e => { e.stopPropagation(); jumpTo(reply.id); } },
    h("div", { class: "qbar", style: `background:${color}` }),
    reply.thumb ? lazyImage(reply.thumb.file, "qthumb") : null,
    h("div", { class: "qbody" },
      h("div", { class: "qname", style: `color:${color}`, text: reply.sender }),
      h("div", { class: "qtext", text: reply.text })));
}
async function jumpTo(messageId) {
  const view = CV;
  const find = () => [...view.rows.values()].find(rec => rec.ids.includes(messageId));
  for (let round = 0; round < 6 && !find() && !view.oldest; round++) {
    await loadOlderPage(view);
    if (CV !== view) return;
    renderFeed();
  }
  const rec = find();
  if (!rec) { toast("Сообщение не найдено"); return; }
  rec.el.scrollIntoView({ block: "center", behavior: "smooth" });
  rec.el.animate([{ background: "var(--accent-soft)" }, { background: "transparent" }], { duration: 1200 });
}
function reactions(m, bare) {
  return h("div", { class: "reacts" + (bare ? " bare" : "") },
    m.reactions.map(r => h("span", { class: "react" + (r.chosen ? " mine" : "") }, h("span", { class: "e", text: r.emoji }), count(r.count))));
}
function mediaSize(w, h2, maxWidth) {
  if (!w || !h2) return [maxWidth, maxWidth * 0.75];
  const aspect = w / h2;
  let width = maxWidth, height = width / aspect;
  if (height > 420) { height = 420; width = Math.max(180, height * aspect); }
  return [Math.round(width), Math.round(height)];
}
function mediaTile(body, width, height, onclick) {
  const image = body.type === "photo" ? body.image : body.thumb;
  const tile = h("div", { class: "media", style: `width:${width}px;height:${height}px`, onclick });
  if (image) {
    const mini = miniImage(image, "blur");
    if (mini) tile.append(mini);
    if (image.file) tile.append(lazyImage(image.file, "full"));
  }
  if (body.type === "video") {
    tile.append(h("div", { class: "play" }, icon("play", 28)));
    tile.append(h("div", { class: "dur", text: body.gif ? "GIF" : duration(body.duration) }));
  }
  return tile;
}
function openMedia(body) {
  if (body.type === "photo") { if (body.image && body.image.file) viewer("image", body.image.file); }
  else if (body.file) viewer("video", body.file);
}
function visualMedia(m, b, width, overlayMeta) {
  const wrap = h("div", { style: "position:relative" });
  if (b.type === "album") {
    const n = b.items.length;
    const cols = n === 2 || n === 4 ? 2 : n >= 3 ? 3 : 1;
    const cell = Math.floor((width - (cols - 1) * 2) / cols);
    const grid = h("div", { class: "album", style: `grid-template-columns:repeat(${cols}, ${cell}px);width:${width}px` });
    for (const item of b.items) {
      if (item.type === "photo" || item.type === "video") grid.append(mediaTile(item, cell, cell, () => openMedia(item)));
    }
    wrap.append(grid);
    wrap.dataset.w = width;
  } else {
    const [w, hgt] = b.type === "photo" ? mediaSize(b.image && b.image.w, b.image && b.image.h, width) : mediaSize(b.w, b.h, width);
    wrap.append(mediaTile(b, w, hgt, () => openMedia(b)));
    wrap.dataset.w = w;
  }
  if (overlayMeta) wrap.append(meta(m, true));
  return wrap;
}

// One player for voice and music, like the phone's TdAudioController.
const player = { audio: new Audio(), file: 0 };
player.audio.preload = "none";
function syncPlayers() {
  document.querySelectorAll("[data-play]").forEach(btn => {
    const mine = Number(btn.dataset.play) === player.file;
    const playing = mine && !player.audio.paused;
    btn.replaceChildren(icon(playing ? "pause" : "play", 28));
  });
  document.querySelectorAll("[data-wave]").forEach(wave => {
    const mine = Number(wave.dataset.wave) === player.file;
    const fraction = mine && player.audio.duration ? player.audio.currentTime / player.audio.duration : 0;
    const bars = wave.children;
    for (let i = 0; i < bars.length; i++) bars[i].classList.toggle("on", i / bars.length < fraction);
  });
  document.querySelectorAll("[data-time]").forEach(el => {
    const mine = Number(el.dataset.time) === player.file;
    el.textContent = duration(mine && !player.audio.paused ? player.audio.currentTime : Number(el.dataset.total));
  });
}
["play", "pause", "timeupdate", "ended"].forEach(ev => player.audio.addEventListener(ev, syncPlayers));
player.audio.addEventListener("error", () => {
  if (!player.file) return;
  toast("Не удалось воспроизвести");
  player.file = 0;
  syncPlayers();
});
function togglePlay(fileId) {
  if (player.file === fileId) { player.audio.paused ? player.audio.play() : player.audio.pause(); return; }
  player.file = fileId;
  player.audio.src = fileUrl(fileId);
  player.audio.play().catch(() => {});
  syncPlayers();
}
function playButton(fileId, out) {
  const color = out ? "var(--link-out)" : "var(--accent)";
  const fg = out ? "var(--bubble-out)" : "var(--on-accent)";
  const btn = h("button", { class: "round-btn", style: `background:${color};color:${fg}`, onclick: e => { e.stopPropagation(); togglePlay(fileId); } });
  btn.dataset.play = fileId;
  btn.append(icon(player.file === fileId && !player.audio.paused ? "pause" : "play", 28));
  return btn;
}
function insetBody(m, b) {
  const out = m.out;
  switch (b.type) {
    case "voice": {
      const bars = (b.waveform.length ? b.waveform : new Array(40).fill(4));
      const step = Math.max(1, Math.floor(bars.length / 48));
      const shown = bars.filter((_, i) => i % step === 0);
      const wave = h("div", { class: "wave", style: `--wave-on:${out ? "var(--link-out)" : "var(--accent)"};--wave-rest:${soft(out ? "var(--bubble-out-meta)" : "var(--text2)", 0.45)}`,
        onclick: e => {
          e.stopPropagation();
          if (player.file !== b.file) { togglePlay(b.file); return; }
          const r = wave.getBoundingClientRect();
          if (player.audio.duration) player.audio.currentTime = player.audio.duration * (e.clientX - r.left) / r.width;
        } },
        shown.map(v => h("i", { style: `height:${Math.max(2, Math.round(v / 31 * 26))}px` })));
      wave.dataset.wave = b.file;
      const time = h("span", { text: duration(b.duration) });
      time.dataset.time = b.file;
      time.dataset.total = b.duration;
      return h("div", { class: "hrow voice" }, playButton(b.file, out),
        h("div", {}, wave, h("div", { class: "vmeta" }, time)));
    }
    case "audio": {
      const time = h("span", { text: duration(b.duration) });
      time.dataset.time = b.file;
      time.dataset.total = b.duration;
      return h("div", { class: "hrow", style: "min-width:220px" }, playButton(b.file, out),
        h("div", { style: "min-width:0" }, h("div", { class: "b1", text: b.title || "Аудио" }),
          h("div", { class: "b2" }, b.performer ? b.performer + " · " : "", time)));
    }
    case "document": {
      const name = b.name || "Файл";
      const thumbEl = b.thumb && b.thumb.file ? lazyImage(b.thumb.file, "docthumb") : null;
      return h("a", { class: "hrow", style: "min-width:220px;text-decoration:none;color:inherit", href: fileUrl(b.file, name, true), download: name,
        onclick: () => toast("Файл скачивается с Telegram…") },
        thumbEl || h("div", { class: "round-btn", style: `background:${out ? "var(--link-out)" : "var(--accent)"};color:${out ? "var(--bubble-out)" : "var(--on-accent)"}` }, icon("file", 24)),
        h("div", { style: "min-width:0" }, h("div", { class: "b1", text: name }), h("div", { class: "b2", text: fileSize(b.size) })));
    }
    case "poll": {
      const accent = out ? "var(--link-out)" : "var(--accent)";
      return h("div", { class: "poll" },
        h("div", { class: "q", text: b.question }),
        h("div", { class: "kind", text: (b.quiz ? "Викторина" : "Опрос") + (b.closed ? " завершён" : "") }),
        b.options.map(o => h("div", { class: "popt" },
          h("div", { class: "l" }, h("span", { class: "pct", text: o.percent + "%" }), h("span", { class: "grow", text: o.text }),
            o.chosen ? h("span", { style: `color:${accent};display:flex` }, icon("check", 16)) : null),
          h("div", { class: "barbg" }, h("div", { class: "barfg", style: `width:${o.percent}%` })))),
        h("div", { class: "kind", style: "margin:4px 0 0", text: `${b.total} ${plural(b.total, "голос", "голоса", "голосов")}` }));
    }
    case "location": {
      const url = `https://www.openstreetmap.org/?mlat=${b.lat}&mlon=${b.lon}#map=16/${b.lat}/${b.lon}`;
      return h("a", { class: "hrow", style: "text-decoration:none;color:inherit;min-width:200px", href: url, target: "_blank", rel: "noopener noreferrer" },
        h("div", { class: "round-btn", style: "background:var(--accent);color:var(--on-accent)" }, icon("place", 24)),
        h("div", { style: "min-width:0" }, h("div", { class: "b1", text: b.title || "Геопозиция" }),
          h("div", { class: "b2", text: `${b.lat.toFixed(5)}, ${b.lon.toFixed(5)}` })));
    }
    case "contact":
      return h("div", { class: "hrow", style: "min-width:200px" }, avatar(b.name, null, 0, 44),
        h("div", { style: "min-width:0" }, h("div", { class: "b1", text: b.name }), h("div", { class: "b2", text: b.phone })));
    case "call": {
      const title = b.missed ? "Пропущенный звонок" : out ? "Исходящий звонок" : "Входящий звонок";
      return h("div", { class: "hrow", style: "min-width:200px" },
        h("span", { style: `color:${b.missed ? "var(--danger)" : "var(--success)"};display:flex` }, icon("call", 22)),
        h("div", {}, h("div", { class: "b1", text: title }), b.duration > 0 ? h("div", { class: "b2", text: duration(b.duration) }) : null));
    }
    case "unsupported":
      return h("div", { class: "unsupported", text: "Этот тип сообщения пока не поддерживается" });
    default:
      return null;
  }
}
function bareMessage(m) {
  const b = m.body;
  const box = h("div", { class: "bare" });
  if (b.type === "sticker") {
    const side = 180;
    const aspect = b.h > 0 ? b.w / b.h : 1;
    const [w, hgt] = aspect >= 1 ? [side, side / aspect] : [side * aspect, side];
    const holder = h("div", { class: "sticker", style: `width:${Math.round(w)}px;height:${Math.round(hgt)}px` });
    if (b.format === "webp" && b.file) holder.append(lazyImage(b.file, "", "sticker.webp"));
    else if (b.format === "webm" && b.file) {
      const v = h("video", { autoplay: true, loop: true, muted: true, playsinline: true });
      v.muted = true;
      v.dataset.src = fileUrl(b.file, "sticker.webm");
      lazy.observe(v);
      holder.append(v);
    } else if (b.thumb && b.thumb.file) holder.append(lazyImage(b.thumb.file, "", "sticker.webp"));
    else holder.append(h("div", { class: "emoji", text: b.emoji || "🙂" }));
    box.append(holder);
  } else {
    const circle = h("div", { class: "roundv" });
    if (b.thumb && b.thumb.file) circle.append(lazyImage(b.thumb.file));
    const playIcon = h("div", { class: "play" }, icon("play", 28));
    const dur = h("div", { class: "dur", style: "left:50%;top:auto;bottom:10px;transform:translateX(-50%)", text: duration(b.duration) });
    circle.append(playIcon, dur);
    circle.addEventListener("click", () => {
      let video = circle.querySelector("video");
      if (!video) {
        video = h("video", { src: fileUrl(b.file, "round.mp4"), playsinline: true });
        video.addEventListener("ended", () => { playIcon.classList.remove("hidden"); });
        circle.insertBefore(video, playIcon);
      }
      if (video.paused) { video.play().catch(() => toast("Не удалось воспроизвести")); playIcon.classList.add("hidden"); }
      else { video.pause(); playIcon.classList.remove("hidden"); }
    });
    box.append(circle);
  }
  box.append(meta(m, true));
  if (m.reactions.length) return h("div", { style: "display:flex;flex-direction:column;align-items:" + (m.out ? "flex-end" : "flex-start") }, box, reactions(m, true));
  return box;
}
function webCard(web) {
  const photo = web.photo && web.photo.file ? lazyImage(web.photo.file, "wphoto") : null;
  return h("div", { class: "web", style: "background:var(--accent-soft)", onclick: () => openLink(web.url) },
    h("div", { class: "wbar" }),
    h("div", { class: "wbody" },
      web.site ? h("div", { class: "wsite", text: web.site }) : null,
      web.title ? h("div", { class: "wtitle", text: web.title }) : null,
      web.description ? h("div", { class: "wdesc", text: web.description }) : null,
      photo));
}

// Formatted text from Telegram entities. Offsets count UTF-16 units, as JavaScript strings do.
function safeUrl(url) {
  let value = (url || "").trim();
  if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) value = "https://" + value;
  try {
    const parsed = new URL(value);
    return ["http:", "https:", "mailto:", "tel:"].includes(parsed.protocol) ? parsed.href : null;
  } catch { return null; }
}
function openLink(url) {
  const safe = safeUrl(url);
  if (safe) window.open(safe, "_blank", "noopener,noreferrer");
}
function richText(rich) {
  const text = rich.text || "";
  const spans = (rich.spans || [])
    .map(([offset, length, type, url]) => ({ start: offset, end: Math.min(text.length, offset + length), type, url }))
    .filter(s => s.end > s.start)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  return renderRange(text, spans, 0, text.length);
}
function renderRange(text, spans, start, end) {
  const frag = document.createDocumentFragment();
  let pos = start;
  let i = 0;
  while (i < spans.length) {
    const span = spans[i];
    if (span.start < pos) { i++; continue; }
    if (span.start > pos) frag.append(text.slice(pos, span.start));
    const inner = [];
    let j = i + 1;
    while (j < spans.length && spans[j].start < span.end) {
      inner.push({ ...spans[j], end: Math.min(spans[j].end, span.end) });
      j++;
    }
    frag.append(wrapSpan(span, text.slice(span.start, span.end), renderRange(text, inner, span.start, span.end)));
    pos = span.end;
    i = j;
  }
  if (pos < end) frag.append(text.slice(pos, end));
  return frag;
}
function wrapSpan(span, raw, content) {
  const link = href => {
    const safe = safeUrl(href);
    return safe ? h("a", { href: safe, target: "_blank", rel: "noopener noreferrer" }, content) : h("span", { class: "lnk" }, content);
  };
  switch (span.type) {
    case "bold": return h("b", {}, content);
    case "italic": return h("i", {}, content);
    case "underline": return h("u", {}, content);
    case "strike": return h("s", {}, content);
    case "code": return h("span", { class: "code" }, content);
    case "pre": return h("span", { class: "pre" }, content);
    case "quote": return h("span", { class: "quote" }, content);
    case "spoiler": return h("span", { class: "spoiler", onclick: e => { e.currentTarget.classList.add("open"); } }, content);
    case "url": return link(raw);
    case "text_url": return link(span.url);
    case "email": return h("a", { href: "mailto:" + raw.trim() }, content);
    case "phone": return h("a", { href: "tel:" + raw.replace(/[^+\d]/g, "") }, content);
    case "mention": return raw.startsWith("@") ? link("https://t.me/" + raw.slice(1)) : h("span", { class: "lnk" }, content);
    default: return h("span", { class: "lnk" }, content);
  }
}

// Reading: what you see in the open chat is marked read, while this tab is in front.
function scheduleRead() {
  if (!markReadOn() || document.hidden || !document.hasFocus()) return;
  debounce("read", flushRead, 300);
}
async function flushRead() {
  const view = CV;
  if (!view || !view.pendingRead.size || !markReadOn() || document.hidden || !document.hasFocus()) return;
  const ids = [...view.pendingRead].filter(mid => mid > view.lastRead);
  view.pendingRead.clear();
  if (!ids.length) return;
  view.lastRead = Math.max(view.lastRead, ...ids);
  try { await post(`/app/api/chats/${view.id}/read`, { ids, topic: view.topic }); } catch {}
}
window.addEventListener("focus", scheduleRead);
document.addEventListener("visibilitychange", scheduleRead);

// ---------- Brain's side panel: what Brain decided about a message, and what it proposed ----------
const BRAIN_STATUS = {
  open: "Ждёт вашего решения", approved: "Одобрено, выполняется", executed: "Одобрено и выполнено",
  failed: "Одобрено, но не получилось", rejected: "Отклонено: ничего не отправлено", answered: "Отвечено",
  dismissed: "Скрыто: ничего не отправлено",
};
const BRAIN_COLOR = { open: "var(--warning)", failed: "var(--danger)", executed: "var(--success)", answered: "var(--success)", approved: "var(--accent)" };
S.brainChats = LS.get("brainChats", {});

function brainEpoch(at) {
  // Brain writes "YYYY-MM-DD HH:MM:SS" in this PC's local time; without a zone the browser reads it as local too.
  const text = String(at || "");
  const iso = /^\d{4}-\d\d-\d\d \d\d:\d\d(:\d\d)?$/.test(text) ? text.replace(" ", "T") : text;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? 0 : Math.floor(ms / 1000);
}
function brainTime(at) {
  const epoch = brainEpoch(at);
  if (!epoch) return "";
  return dayOf(epoch) === today() ? clock(epoch) : `${listTime(epoch)}, ${clock(epoch)}`;
}
function scheduleBrain(view, ms) {
  clearTimeout(view.brainTimer);
  view.brainTimer = setTimeout(() => { if (CV === view) loadBrainPanel(view); }, ms);
}
async function loadBrainPanel(view) {
  let data = null;
  try {
    data = await api(`/v1/brain/chats/${view.id}/panel`);
    view.brainError = null;
  } catch (e) {
    view.brainError = e.message;
  }
  if (CV !== view) return;
  if (data) {
    S.brainChats[view.id] = data.active;
    LS.set("brainChats", S.brainChats);
  }
  if (data && !data.active) {
    view.brain = null;
    if (view.panel) { view.panel.remove(); view.panel = null; renderHeader(); }
    applyBrainMarks(view);
    scheduleBrain(view, 60000);
    return;
  }
  if (!data && !view.brain && !S.brainChats[view.id]) {
    // Brain is unreachable and this chat wasn't in a job last time: nothing to show.
    scheduleBrain(view, 30000);
    return;
  }
  if (data) view.brain = data;
  else if (!view.brain) view.brain = { active: true, jobs: [], items: [] };
  const created = ensureBrainPanel(view);
  // Leave the panel alone while you type an answer in it; the next look picks up the changes.
  const typing = view.panel.contains(document.activeElement) && /INPUT|TEXTAREA/.test(document.activeElement.tagName);
  if (!typing) renderBrainPanel(view);
  applyBrainMarks(view);
  if (created) renderHeader();
  const working = view.brain.items.some(item => item.working);
  scheduleBrain(view, document.hidden ? 30000 : working ? 4000 : 15000);
}
function ensureBrainPanel(view) {
  if (view.panel) return false;
  view.panelBody = h("div", { class: "bp-body" });
  view.panelTitle = h("div", { class: "bp-title", text: "Brain" });
  view.panel = h("aside", { class: "bpanel" + (matchMedia("(min-width: 1280px)").matches ? "" : " closed") },
    h("div", { class: "bp-head" }, view.panelTitle, iconButton("close", "Скрыть панель", () => toggleBrainPanel(view, false), "dim")),
    view.panelBody);
  view.wrap.append(view.panel);
  return true;
}
function toggleBrainPanel(view, open) {
  if (!view.panel) return;
  const show = open === undefined ? view.panel.classList.contains("closed") : open;
  view.panel.classList.toggle("closed", !show);
  renderHeader();
}
function selectBrainMessage(view, ids) {
  view.brainSelected = ids;
  toggleBrainPanel(view, true);
  renderBrainPanel(view);
  applyBrainMarks(view);
}
function brainState(view) {
  const byMessage = new Map();
  for (const item of (view.brain && view.brain.items) || []) {
    const open = item.actions.some(a => a.status === "open");
    const failed = item.status === "error" || item.actions.some(a => a.status === "failed");
    for (const id of item.messageIds) {
      const s = byMessage.get(id) || { working: false, open: false, failed: false };
      s.working = s.working || item.working;
      s.open = s.open || open;
      s.failed = s.failed || failed;
      byMessage.set(id, s);
    }
  }
  return byMessage;
}
// Marks the messages Brain has looked at, with a spinner while it is still working on them.
function applyBrainMarks(view) {
  if (!view || !view.rows) return;
  const byMessage = brainState(view);
  const selected = new Set(view.brain ? view.brainSelected || [] : []);
  for (const rec of view.rows.values()) {
    if (!rec.ids || !rec.ids.length) continue;
    const el = rec.el;
    el.classList.toggle("bsel", rec.ids.some(id => selected.has(id)));
    let state = null;
    for (const id of rec.ids) {
      const s = byMessage.get(id);
      if (s) state = state ? { working: state.working || s.working, open: state.open || s.open, failed: state.failed || s.failed } : s;
    }
    let mark = el.querySelector(":scope > .bmark");
    if (!state) { if (mark) mark.remove(); continue; }
    if (!mark) {
      mark = h("div", { class: "bmark", onclick: e => { e.stopPropagation(); selectBrainMessage(view, rec.ids); } });
      if (el.classList.contains("out")) el.prepend(mark); else el.append(mark);
    }
    const kind = state.working ? "working" : state.open ? "open" : state.failed ? "failed" : "";
    if (mark.dataset.kind !== kind || !mark.childElementCount) {
      mark.dataset.kind = kind;
      mark.className = "bmark" + (kind && kind !== "working" ? " " + kind : "");
      mark.title = state.working ? "Brain разбирает это сообщение…" : state.open ? "Brain ждёт вашего решения" : "Brain разобрал это сообщение";
      mark.replaceChildren(state.working ? h("span", { class: "spin-sm" }) : icon("robot", 14));
    }
  }
}
function renderBrainPanel(view) {
  if (!view.panel || !view.brain) return;
  const brain = view.brain;
  const jobs = brain.jobs.map(j => j.name).join(", ");
  view.panelTitle.textContent = jobs ? `Brain · ${jobs}` : "Brain";
  const kids = [];
  if (view.brainError) kids.push(h("div", { class: "bp-banner", text: view.brainError }));
  for (const job of brain.jobs.filter(j => j.paused)) {
    kids.push(h("div", { class: "bp-banner", text: `Работа «${job.name}» на паузе: новые сообщения не анализируются.` }));
  }
  const selected = view.brainSelected;
  if (selected && selected.length) {
    const message = selected.map(id => view.msgs.get(id)).find(Boolean);
    const items = brain.items.filter(item => item.messageIds.some(id => selected.includes(id)));
    kids.push(h("div", { class: "bp-sub", text: "Сообщение" }));
    if (message) {
      const who = message.out ? "Вы" : message.sender ? message.sender.name : (view.chat ? view.chat.title : "");
      kids.push(h("div", { class: "bp-msg" },
        h("div", { class: "who", text: `${who} · ${clock(message.date)}` }),
        h("div", { class: "txt2", text: textOf(message) || "(без текста)" })));
    }
    if (!items.length) {
      const paused = brain.jobs.some(j => j.paused);
      kids.push(h("div", { class: "bp-hint", text: "Brain не разбирал это сообщение." + (paused ? " Пока работа на паузе, новые сообщения не разбираются." : "") }));
    }
    for (const item of items) kids.push(brainRun(view, item, false));
    kids.push(h("button", { class: "tbtn", style: "margin-left:-12px", text: "Все разборы в этом чате",
      onclick: () => { view.brainSelected = null; renderBrainPanel(view); applyBrainMarks(view); } }));
  } else {
    kids.push(h("div", { class: "bp-hint", text: "Нажмите на сообщение, чтобы увидеть, что решил Brain и что он предлагает сделать." }));
    if (!brain.items.length) kids.push(h("div", { class: "bp-hint", text: "В этом чате Brain пока ничего не разбирал." }));
    else kids.push(h("div", { class: "bp-sub", text: "Последние разборы" }), ...brain.items.slice(0, 30).map(item => brainRun(view, item, true)));
  }
  view.panelBody.replaceChildren(...kids);
}
function brainRun(view, item, withJump) {
  const run = h("div", { class: "brun" });
  run.append(h("div", { class: "brun-top" },
    labelPill(item.jobName, "var(--accent)"),
    h("span", { text: `разбор №${item.runId} · ${brainTime(item.at)}` }),
    item.working ? h("span", { class: "working" }, h("span", { class: "spin-sm" }), "Работает…")
      : item.status === "error" ? labelPill("Ошибка", "var(--danger)") : null));
  if (withJump && item.messageIds.length) {
    const count = item.messageIds.length;
    run.append(h("button", { class: "tbtn", style: "margin:2px 0 0 -12px;padding:4px 12px",
      text: count > 1 ? `К сообщениям (${count})` : "К сообщению",
      onclick: () => { selectBrainMessage(view, item.messageIds); jumpTo(item.messageIds[0]); } }));
  }
  if (item.decisions.length) {
    run.append(h("div", { class: "brun-label", text: "Решение" }), ...item.decisions.map(d => h("div", { class: "brun-text", text: d.text })));
  } else if (item.working) {
    run.append(h("div", { class: "brun-text", style: "color:var(--text2)", text: "Brain разбирает сообщения…" }));
  }
  if (item.actions.length) {
    run.append(h("div", { class: "brun-label", text: "Предлагает" }), ...item.actions.map(action => brainAction(view, action)));
  } else if (!item.working && item.decisions.length) {
    run.append(h("div", { class: "brun-sum", text: "Ничего не предлагает." }));
  }
  if (item.summary && !item.working) run.append(h("div", { class: "brun-sum", title: item.summary, text: item.summary }));
  return run;
}
function brainAction(view, action) {
  const card = h("div", { class: "bact" });
  const question = action.kind === "escalation";
  card.append(h("div", { class: "bact-kind", text: question ? "Вопрос к вам" : `Действие: ${action.actionType || "—"}` }));
  if (action.to) card.append(h("div", { class: "bact-line" }, "Кому: ", h("b", { text: action.to })));
  if (question && action.question) card.append(h("div", { class: "brun-text", text: action.question }));
  if (action.text) card.append(h("div", { class: "bact-text", text: action.text }));
  if (question && action.options && action.options.length && action.status !== "open") {
    card.append(h("div", { class: "bact-line", style: "color:var(--text2)", text: "Варианты: " + action.options.join(" · ") }));
  }
  card.append(h("div", { class: "bact-status", style: `color:${BRAIN_COLOR[action.status] || "var(--text2)"}`,
    text: BRAIN_STATUS[action.status] || action.statusText || action.status }));
  if (action.answer) card.append(h("div", { class: "bact-line" }, "Ваш ответ: ", h("b", { text: action.answer })));
  if (action.reason) card.append(h("div", { class: "bact-line", style: "color:var(--text2)", text: "Пояснение: " + action.reason }));
  if (action.result) card.append(h("div", { class: "bact-line", style: "color:var(--text2)", text: action.result }));
  if (action.status === "open") card.append(brainControls(view, action));
  return card;
}
// Your answer goes to Brain, which applies its own rules: nothing is sent to anyone without "approve".
function brainControls(view, action) {
  const box = h("div");
  const send = async body => {
    box.querySelectorAll("button").forEach(b => { b.disabled = true; });
    // The answer is in, so the panel may redraw even though its text box still has the focus.
    if (box.contains(document.activeElement)) document.activeElement.blur();
    try {
      const result = await post(`/v1/brain/actions/${action.id}/decide`, body);
      toast(result.text || "Готово");
    } catch (e) {
      toast("Не удалось: " + e.message);
    }
    loadBrainPanel(view);
  };
  const input = (placeholder, value = "") => {
    const el = h("textarea", { class: "bact-input", rows: 2, placeholder });
    el.value = value;
    return el;
  };
  if (action.kind === "escalation") {
    for (const option of action.options || []) box.append(h("button", { class: "bopt", text: option, onclick: () => send({ decision: "answer", text: option }) }));
    const answer = input("Свой ответ");
    box.append(answer, h("div", { class: "bact-buttons" },
      h("button", { class: "tbtn", text: "Ответить", onclick: () => { if (answer.value.trim()) send({ decision: "answer", text: answer.value.trim() }); else answer.focus(); } }),
      h("button", { class: "tbtn dim", text: "Скрыть", onclick: () => send({ decision: "dismiss" }) })));
    return box;
  }
  const buttons = h("div", { class: "bact-buttons" });
  const extra = h("div");
  buttons.append(
    h("button", { class: "tbtn", text: "Одобрить", onclick: () => {
      if (confirm(`Brain выполнит это действие${action.to ? ` (${action.to})` : ""}:\n\n${action.text || action.actionType}\n\nОдобрить?`)) send({ decision: "approve" });
    } }),
    h("button", { class: "tbtn", text: "Изменить", onclick: () => {
      const edited = input("Текст", action.text || "");
      extra.replaceChildren(edited, h("div", { class: "bact-buttons" },
        h("button", { class: "tbtn", text: "Одобрить с изменениями", onclick: () => {
          if (edited.value.trim() && confirm(`Отправить так?\n\n${edited.value.trim()}`)) send({ decision: "approve", text: edited.value.trim() });
        } })));
      edited.focus();
    } }),
    h("button", { class: "tbtn danger", text: "Отклонить", onclick: () => {
      const reason = input("Почему (необязательно) — Brain это учтёт");
      extra.replaceChildren(reason, h("div", { class: "bact-buttons" },
        h("button", { class: "tbtn danger", text: "Отклонить", onclick: () => send({ decision: "reject", reason: reason.value.trim() || undefined }) })));
      reason.focus();
    } }),
    h("button", { class: "tbtn dim", text: "Скрыть", onclick: () => send({ decision: "dismiss" }) }));
  box.append(buttons, extra);
  return box;
}

// ---------- composer ----------
function renderComposer() {
  const view = CV;
  const target = h("div");
  const textarea = h("textarea", { rows: 1, placeholder: "Сообщение", "aria-label": "Сообщение" });
  textarea.value = S.drafts[draftKey(view)] || "";
  const sendBtn = h("button", { class: "send", title: "Отправить", "aria-label": "Отправить", onclick: () => send() }, icon("send"));
  const grow = () => {
    textarea.style.height = "52px";
    textarea.style.height = Math.min(textarea.scrollHeight, 184) + "px";
    sendBtn.classList.toggle("off", !textarea.value.trim());
  };
  textarea.addEventListener("input", grow);
  textarea.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
  view.textarea = textarea;
  view.target = target;
  view.grow = grow;
  view.composer.replaceChildren(target, h("div", { class: "crow" }, textarea, sendBtn));
  setTimeout(() => { grow(); if (matchMedia("(pointer: fine)").matches) textarea.focus(); }, 0);
}
function setReply(m) {
  const view = CV;
  if (!view) return;
  view.replyTo = m;
  view.target.replaceChildren();
  if (m) {
    const who = m.out ? "Вы" : (m.sender ? m.sender.name : view.chat.title);
    const preview = textOf(m) || ({ photo: "Фото", video: "Видео", voice: "Голосовое сообщение", document: "Файл", sticker: "Стикер", album: "Альбом" })[m.body.type] || "Сообщение";
    view.target.append(h("div", { class: "target" },
      h("span", { style: "margin-left:14px;color:var(--accent);display:flex" }, icon("reply", 22)),
      h("div", { class: "tline" }),
      h("div", { class: "grow" }, h("div", { class: "tt", text: who }), h("div", { class: "tx", text: preview.replace(/\n/g, " ") })),
      iconButton("close", "Отменить", () => setReply(null), "dim")));
    view.textarea.focus();
  }
}
async function send() {
  const view = CV;
  if (!view) return;
  const text = view.textarea.value.trim();
  if (!text) return;
  if (text.length > 4096) { toast("Слишком длинное сообщение"); return; }
  const reply = view.replyTo;
  view.textarea.value = "";
  S.drafts[draftKey(view)] = "";
  view.grow();
  setReply(null);
  try {
    const result = await post(`/app/api/chats/${view.id}/send`, { text, reply_to: reply ? reply.id : 0, topic: view.topic });
    if (CV === view && result.message) {
      view.msgs.set(result.message.id, result.message);
      view.stickBottom = true;
      renderFeed();
    }
  } catch (e) {
    toast("Не удалось отправить: " + e.message);
    if (CV === view && !view.textarea.value) { view.textarea.value = text; view.grow(); }
  }
}

// ---------- FoxyGram screens: cases, review, Claude chats, settings ----------
const INTENTS = { question: "Вопрос", request: "Запрос", status_update: "Статус", payment: "Оплата", document: "Документ",
  complaint: "Жалоба", agreement: "Договорённость", smalltalk: "Разговор", spam: "Спам", other: "Другое" };
function screenBar(title) {
  return h("div", { class: "bar" }, iconButton("back", "Назад", back), h("div", { class: "bar-title", text: title }));
}
function emptyNote(text) { return h("div", { class: "note", text }); }
const OFFLINE = "Не удалось получить данные с сервера.";

// A group with topics: "all messages", then each topic, pinned first, as the phone's TopicsRoute.
let TV = null;
function topicsScreen(chatId, title) {
  const body = h("div", { class: "scroll" });
  mainPane.replaceChildren(h("div", { class: "screen" }, screenBar(title || "Темы"), body));
  const view = { chatId, loaded: false };
  TV = view;
  view.load = async () => {
    let topics;
    try { topics = (await api(`/app/api/chats/${chatId}/topics`)).topics; }
    catch { if (TV === view && !view.loaded) body.replaceChildren(emptyNote("Не удалось загрузить темы.")); return; }
    if (TV !== view) return;
    view.loaded = true;
    body.replaceChildren(
      h("div", { class: "topic-all", text: "Все сообщения", onclick: () => openChat(chatId) }),
      ...topics.map(topic => topicRow(chatId, topic)));
  };
  view.load();
}
function topicRow(chatId, topic) {
  const color = topic.color && topic.color !== "#000000" ? topic.color : avatarColor(topic.id);
  return h("div", { class: "topic-row", onclick: () => openChat(chatId, topic.id, topic.title) },
    h("div", { class: "av", style: `width:40px;height:40px;font-size:17px;background:${color}`, text: (Array.from(topic.title)[0] || "#").toUpperCase() }),
    h("div", { class: "rb", style: "gap:2px" },
      h("div", { class: "rl" },
        h("span", { class: "rtitle", style: "font-size:16px;flex:1", text: topic.title }),
        h("span", { class: "rtime", style: "font-size:12px;margin-left:8px", text: listTime(topic.date) })),
      h("div", { class: "rl" },
        h("span", { class: "prev", style: "font-size:14px", text: topic.preview }),
        topic.unread > 0 ? h("span", { class: "badge small" + (topic.mentions > 0 ? "" : " muted"), style: "margin-left:8px", text: count(topic.unread) }) : null)));
}

function casesScreen() {
  let closed = false;
  let query = "";
  const tabs = h("div", { class: "tabs" });
  const body = h("div", { class: "scroll" });
  const input = h("input", { placeholder: "Поиск по делам", oninput: e => { query = e.target.value; debounce("cases", load, 250); } });
  const drawTabs = () => tabs.replaceChildren(
    h("button", { class: "tbtn" + (closed ? " dim" : ""), onclick: () => { closed = false; drawTabs(); load(); }, text: "Открытые" }),
    h("button", { class: "tbtn" + (closed ? "" : " dim"), onclick: () => { closed = true; drawTabs(); load(); }, text: "Закрытые" }));
  async function load() {
    let list;
    try { list = await api(`/v1/cases?status=${closed ? "closed" : "open"}&q=${encodeURIComponent(query)}`); }
    catch { body.replaceChildren(emptyNote(OFFLINE)); return; }
    if (!list.length) {
      body.replaceChildren(emptyNote(query ? "Ничего не найдено" : "Пока нет дел. Выберите чаты для Claude, и здесь появятся темы, которые в них обсуждают."));
      return;
    }
    body.replaceChildren(...list.map(c => h("div", { class: "case-row", onclick: () => go({ name: "case", id: c.id }) },
      h("div", { class: "case-top" }, h("div", { class: "case-title", text: c.title }), h("span", { class: "rtime", text: listTime(c.updated_at) })),
      c.summary ? h("div", { class: "case-sum", text: c.summary }) : null,
      h("div", { class: "case-foot" },
        c.needs_review > 0 ? labelPill("Проверить", "var(--warning)") : null,
        h("span", { class: "case-chats", text: c.chats.map(x => x.title || "").filter(Boolean).join(", ") })))));
  }
  drawTabs();
  mainPane.replaceChildren(h("div", { class: "screen" }, screenBar("Дела"), tabs,
    h("div", { style: "background:var(--surface);padding:0 0 8px" }, h("div", { class: "field" }, icon("search", 20), input)), body));
  load();
}
function caseScreen(caseId) {
  const bar = screenBar("Дело");
  const body = h("div", { class: "scroll", style: "padding:0 12px" });
  mainPane.replaceChildren(h("div", { class: "screen" }, bar, body));
  async function change(path, payload) {
    try { await post(path, payload); } catch (e) { toast("Не удалось: " + e.message); }
    load();
  }
  async function load() {
    let c;
    try { c = await api(`/v1/cases/${caseId}`); } catch { body.replaceChildren(emptyNote(OFFLINE)); return; }
    bar.querySelector(".bar-title").textContent = c.title;
    const entities = c.entities.map(e => e.value);
    const head = h("div", { style: "padding:12px 0" },
      c.summary ? h("div", { style: "font-size:15px", text: c.summary }) : null,
      entities.length ? h("div", { style: "font-size:13px;color:var(--text2);margin-top:8px", text: entities.join("  ·  ") }) : null,
      h("div", {}, h("button", { class: "tbtn", style: "margin-left:-12px",
        onclick: () => change(`/v1/cases/${caseId}`, { status: c.status === "open" ? "closed" : "open" }),
        text: c.status === "open" ? "Закрыть дело" : "Открыть снова" })));
    const cards = c.timeline.map(ev => h("div", { class: "card", onclick: () => openChat(ev.chat_id) },
      h("div", { class: "card-top" },
        h("div", { class: "card-chat", text: ev.chat_title || "Чат" }),
        INTENTS[ev.intent] ? labelPill(INTENTS[ev.intent], "var(--text2)") : null,
        ev.urgency === "high" ? labelPill("Срочно", "var(--danger)") : null),
      ev.summary ? h("div", { class: "card-sum", text: ev.summary }) : null,
      ev.messages.slice(-3).map(msg => h("div", { class: "card-msg", text: (msg.outgoing ? "Вы" : msg.sender_name) + ": " + msg.text })),
      ev.needs_review ? h("div", {},
        h("button", { class: "tbtn", onclick: e => { e.stopPropagation(); change(`/v1/bursts/${ev.burst_id}/confirm`); }, text: "Верно" }),
        h("button", { class: "tbtn danger", onclick: e => { e.stopPropagation(); change(`/v1/bursts/${ev.burst_id}/move`, {}); }, text: "Не относится" })) : null));
    body.replaceChildren(head, ...cards);
  }
  load();
}
function reviewScreen() {
  const body = h("div", { class: "scroll", style: "padding:12px" });
  mainPane.replaceChildren(h("div", { class: "screen" }, screenBar("Проверить"), body));
  async function act(path, payload) {
    try { await post(path, payload); } catch (e) { toast("Не удалось: " + e.message); }
    load();
  }
  async function load() {
    let items;
    try { items = await api("/v1/review"); } catch { body.replaceChildren(emptyNote(OFFLINE)); return; }
    if (!items.length) { body.replaceChildren(emptyNote("Нечего проверять. Здесь появятся сообщения, которые Claude отнёс к делу без полной уверенности.")); return; }
    body.replaceChildren(...items.map(item => h("div", { class: "card", onclick: () => go({ name: "case", id: item.case_id }) },
      h("div", { class: "card-top" },
        h("div", { class: "card-chat", text: item.case_title }),
        INTENTS[item.intent] ? labelPill(INTENTS[item.intent], "var(--text2)") : null,
        labelPill(Math.round((item.confidence || 0) * 100) + "%", "var(--warning)")),
      h("div", { class: "card-msg", style: "-webkit-line-clamp:1", text: item.chat_title || "" }),
      item.summary ? h("div", { class: "card-sum", text: item.summary }) : null,
      h("div", {},
        h("button", { class: "tbtn", onclick: e => { e.stopPropagation(); act(`/v1/bursts/${item.burst_id}/confirm`); }, text: "Верно" }),
        h("button", { class: "tbtn danger", onclick: e => { e.stopPropagation(); act(`/v1/bursts/${item.burst_id}/move`, {}); }, text: "Не относится" })))));
  }
  load();
}
function aiChatsScreen() {
  const list = h("div", { class: "scroll" });
  let all = [];
  let query = "";
  const draw = () => {
    const q = query.trim().toLowerCase();
    const shown = all.filter(c => c.title && (!q || c.title.toLowerCase().includes(q)));
    list.replaceChildren(...shown.map(c => h("div", { class: "ai-row" },
      h("div", { class: "t1", text: c.title }),
      switchEl(!!c.ai_enabled, async value => {
        c.ai_enabled = value ? 1 : 0;
        try { await post(`/v1/chats/${c.chat_id}`, { ai_enabled: value }); loadChats(); }
        catch (e) { toast("Не удалось: " + e.message); }
      }))));
  };
  mainPane.replaceChildren(h("div", { class: "screen" }, screenBar("Чаты для Claude"),
    h("div", { style: "padding:16px;font-size:13px;color:var(--text2)", text: "Только отмеченные чаты сохраняются на вашем компьютере и отправляются в Claude." }),
    h("div", { class: "field" }, icon("search", 20), h("input", { placeholder: "Поиск чата", oninput: e => { query = e.target.value; draw(); } })),
    list));
  api("/v1/chats").then(rows => { all = rows; draw(); }).catch(() => list.replaceChildren(emptyNote(OFFLINE)));
}
function settingsScreen() {
  const body = h("div", { class: "scroll" });
  const draw = () => {
    const mode = themeMode();
    const option = (value, title) => h("div", { class: "set-row", onclick: () => { LS.set("theme", value); applyTheme(); rerender(); draw(); } },
      h("div", { class: "radio" + (mode === value ? " on" : "") }), h("div", { class: "t1", text: title }));
    const s = S.state || {};
    body.replaceChildren(
      h("div", { class: "section", text: "Оформление" }),
      option("dark", "Тёмная"), option("light", "Светлая"), option("system", "Как в системе"),
      h("div", { class: "section", text: "Чтение" }),
      h("div", { class: "set-row", style: "cursor:default" },
        h("div", { class: "grow" },
          h("div", { class: "t1", text: "Отмечать прочитанным" }),
          h("div", { class: "t2", text: "Открытый в этой вкладке чат отмечается прочитанным, и уведомление на телефоне пропадает" })),
        switchEl(markReadOn(), value => LS.set("markRead", value))),
      h("div", { class: "section", text: "Сервер" }),
      h("a", { class: "set-row", href: "/", style: "text-decoration:none;color:inherit" },
        h("div", { class: "grow" }, h("div", { class: "t1", text: "Страница управления" }),
          h("div", { class: "t2", text: "Вход в Telegram, телефон, Claude" })), icon("openExternal", 20)),
      h("div", { class: "set-row", style: "cursor:default" },
        h("div", {}, h("div", { class: "t1", text: "Версия сервера" }), h("div", { class: "t2", text: s.version || "—" }))));
  };
  mainPane.replaceChildren(h("div", { class: "screen" }, screenBar("Настройки"), body));
  draw();
}

// ---------- server state and live updates ----------
function gate(content) {
  document.querySelectorAll(".gate").forEach(g => g.remove());
  if (content) document.body.append(h("div", { class: "gate" }, content));
}
async function loadState() {
  try {
    S.state = await api("/app/api/state");
  } catch {
    gate([h("div", { class: "spin" }), h("div", { text: "Нет связи с сервером FoxyGram. Повторяю…" })]);
    debounce("state", loadState, 3000);
    return false;
  }
  if (S.state.telegram !== "ready") {
    gate([h("div", { style: "font-size:17px;color:var(--text)", text: "Сервер ещё не вошёл в Telegram" }),
      h("div", { text: "Войдите на странице управления, и чаты появятся здесь." }),
      h("a", { href: "/", text: "Открыть страницу управления" })]);
    return false;
  }
  gate(null);
  if (!S.searching) renderListHead();
  return true;
}
function connectEvents() {
  const source = new EventSource("/app/api/events");
  source.onopen = () => {
    const wasOffline = !S.live;
    S.live = true;
    if (!S.searching) renderListHead();
    if (wasOffline) refreshAll();
  };
  source.onerror = () => {
    if (S.live) { S.live = false; if (!S.searching) renderListHead(); }
  };
  source.onmessage = e => {
    let event;
    try { event = JSON.parse(e.data); } catch { return; }
    switch (event.t) {
      case "chats":
        debounce("chats", loadChats, 250);
        if (CV) debounce("head", refreshHeader, 500);
        break;
      case "messages":
      case "sent":
        if (CV && event.chat_id === CV.id) debounce("newest", () => loadNewest(false), 150);
        // Brain groups messages for a few seconds before it starts; look again shortly after.
        if (CV && CV.brain && event.chat_id === CV.id) scheduleBrain(CV, 3000);
        if (TV && event.chat_id === TV.chatId) debounce("topics", TV.load, 300);
        break;
      case "topics":
        if (TV && event.chat_id === TV.chatId) debounce("topics", TV.load, 300);
        if (CV && CV.topic && event.chat_id === CV.id) debounce("head", refreshHeader, 500);
        break;
      case "deleted":
        if (CV && event.chat_id === CV.id) { for (const mid of event.ids) CV.msgs.delete(mid); renderFeed(); }
        break;
      case "state":
        debounce("state", async () => { if (await loadState()) loadChats(); }, 300);
        break;
    }
  };
}
async function refreshAll() {
  if (!(await loadState())) return;
  await loadChats();
  if (CV) { refreshHeader(); loadNewest(false); }
}
window.addEventListener("pagehide", () => {
  if (CV) api(`/app/api/chats/${CV.id}/close`, { method: "POST", keepalive: true }).catch(() => {});
});

renderListShell();
S.stack = (history.state && history.state.stack) || [];
history.replaceState({ stack: S.stack }, "");
renderMain();
refreshAll();
connectEvents();
</script>
</body>
</html>
"""
