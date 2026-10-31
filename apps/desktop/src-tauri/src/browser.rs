//! Her browser (ADR 0013): tabs, hands and the relay to the daemon.
//!
//! Each tab is its own window labelled `page-<n>`, holding a remote page with `hands.js` injected
//! into its top document. All tabs share the app's one signed-in WebView2 profile. The daemon owns
//! every decision (trust, cards, files); the shell only does what a call asks, on the tab and the
//! page load the call names, and answers once:
//!
//! ```text
//! daemon <- GET  /browser/next?wait=20 -- relay thread -- eval run(id, hand, input) --> page
//! daemon <- POST /browser/done {id, result} <-- relay  <-- invoke browser_reply {nonce} -- page
//! ```
//!
//! A call bound to a page load (`load`, `url`) is refused with `moved` when the tab has left that
//! page: an approval is spent on the page it was given for, never on what replaced it. A download
//! lands only while a `download` call has armed its tab; every other download is cancelled.

use std::collections::{BTreeMap, HashMap};
use std::hash::{BuildHasher, Hasher};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tauri::webview::{DownloadEvent, PageLoadEvent, PermissionKind, PermissionResponse};
use tauri::{AppHandle, Manager, State, Webview, WebviewUrl, WebviewWindowBuilder};

use crate::daemon::{self, Daemon, DaemonInfo};

const HANDS_JS: &str = include_str!("hands.js");
const POLL_WAIT_S: u64 = 20;
const PAGE_TIMEOUT: Duration = Duration::from_secs(30);
const OPEN_TIMEOUT: Duration = Duration::from_secs(30);
const DOWNLOAD_TIMEOUT: Duration = Duration::from_secs(300);
const WHEEL_LIMIT: Duration = Duration::from_secs(30 * 60);
/// Raw bytes per staged part of an upload; base64 makes each eval about 700 KB.
const UPLOAD_PART: usize = 512 * 1024;
const UPLOAD_MAX: u64 = 2 * 1024 * 1024 * 1024;

struct Tab {
    nonce: String,
    /// Page loads finished in this tab; a call bound to an older one is refused.
    load: u64,
    title: String,
}

struct Armed {
    dir: PathBuf,
    call: String,
    done: Option<Result<PathBuf, String>>,
}

#[derive(Default)]
struct Inner {
    tabs: BTreeMap<u32, Tab>,
    next: u32,
    pending: HashMap<String, Sender<Value>>,
    armed: HashMap<u32, Armed>,
}

pub struct Browser {
    inner: Mutex<Inner>,
    data_dir: PathBuf,
}

pub type Shared = Arc<Browser>;

pub fn new_shared(data_dir: PathBuf) -> Shared {
    Arc::new(Browser { inner: Mutex::new(Inner { next: 1, ..Inner::default() }), data_dir })
}

fn label_of(tab: u32) -> String {
    format!("page-{tab}")
}

fn tab_of(label: &str) -> Option<u32> {
    label.strip_prefix("page-")?.parse().ok()
}

/// 128 bits from the standard library's OS-seeded hasher keys; enough for a per-tab nonce.
fn random_hex() -> String {
    let a = std::collections::hash_map::RandomState::new().build_hasher().finish();
    let mut h = std::collections::hash_map::RandomState::new().build_hasher();
    h.write_u128(std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_nanos()));
    format!("{a:016x}{:016x}", h.finish())
}

fn refused(reason: &str, output: &str) -> Value {
    json!({ "ok": false, "reason": reason, "output": output })
}

// ---- the page's one command ---------------------------------------------------------------------

/// The page's answer to a hand. A wrong nonce or an id nobody is waiting on is dropped.
#[tauri::command]
pub fn browser_reply(webview: Webview, state: State<'_, Shared>, nonce: String, id: String, payload: Value) {
    let Some(tab) = tab_of(webview.label()) else { return };
    let mut inner = state.inner.lock().unwrap();
    let matches = inner.tabs.get(&tab).is_some_and(|t| t.nonce == nonce);
    if !matches {
        return;
    }
    if let Some(title) = payload.get("title").and_then(Value::as_str) {
        if let Some(t) = inner.tabs.get_mut(&tab) {
            t.title = title.chars().take(200).collect();
        }
    }
    if let Some(tx) = inner.pending.remove(&id) {
        let _ = tx.send(payload);
    }
}

/// A tab window was destroyed: forget it.
pub fn forget(app: &AppHandle, label: &str) {
    if let Some(tab) = tab_of(label) {
        let state = app.state::<Shared>();
        let mut inner = state.inner.lock().unwrap();
        inner.tabs.remove(&tab);
        inner.armed.remove(&tab);
    }
}

// ---- tabs ---------------------------------------------------------------------------------------

fn info(app: &AppHandle, browser: &Browser, tab: u32) -> Option<Value> {
    let window = app.get_webview_window(&label_of(tab))?;
    let url = window.url().map(|u| u.to_string()).unwrap_or_default();
    let inner = browser.inner.lock().unwrap();
    let t = inner.tabs.get(&tab)?;
    Some(json!({ "id": tab, "url": url, "title": t.title, "load": t.load }))
}

fn open(app: &AppHandle, browser: &Shared, url: &str) -> Value {
    let Ok(parsed) = tauri::Url::parse(url) else { return refused("refused", "that is not a web address") };
    if !matches!(parsed.scheme(), "http" | "https") {
        return refused("refused", "her browser opens http and https pages only");
    }
    let nonce = random_hex();
    let tab = {
        let mut inner = browser.inner.lock().unwrap();
        let tab = inner.next;
        inner.next += 1;
        inner.tabs.insert(tab, Tab { nonce: nonce.clone(), load: 0, title: String::new() });
        tab
    };
    let script = HANDS_JS.replace("__ATHENA_NONCE__", &nonce);
    let on_load = Arc::clone(browser);
    let on_download = Arc::clone(browser);
    let on_permit = Arc::clone(browser);
    let host = parsed.host_str().unwrap_or("").to_string();
    let built = WebviewWindowBuilder::new(app, label_of(tab), WebviewUrl::External(parsed))
        .title(format!("Her browser - {host}"))
        .inner_size(1180.0, 820.0)
        .focused(false)
        .initialization_script(script)
        .on_page_load(move |window, payload| {
            if let (PageLoadEvent::Finished, Some(tab)) = (payload.event(), tab_of(window.label())) {
                if let Some(t) = on_load.inner.lock().unwrap().tabs.get_mut(&tab) {
                    t.load += 1;
                }
            }
        })
        .on_download(move |webview, event| downloaded(&on_download, webview.label(), event))
        // Chromium holds a page's second script-started download behind a prompt ("this site
        // wants to download multiple files"). Measured on the seam: the second `page_download`
        // from one page never started. Allowed only while a signed download has armed the tab.
        .on_permission_request(move |webview, kind| match kind {
            PermissionKind::AutomaticDownloads => {
                let armed = tab_of(webview.label()).is_some_and(|t| on_permit.inner.lock().unwrap().armed.contains_key(&t));
                if armed { PermissionResponse::Allow } else { PermissionResponse::Deny }
            }
            _ => PermissionResponse::Default,
        })
        .build();
    if let Err(e) = built {
        browser.inner.lock().unwrap().tabs.remove(&tab);
        return refused("failed", &format!("the tab could not be opened ({e})"));
    }
    let started = Instant::now();
    while started.elapsed() < OPEN_TIMEOUT {
        let loaded = browser.inner.lock().unwrap().tabs.get(&tab).is_some_and(|t| t.load > 0);
        if loaded {
            // Ask the page for its title so the tab list can name it.
            let _ = run_page(app, browser, tab, "page_info", &json!({}), Duration::from_secs(5));
            let mut answer = json!({ "ok": true, "output": format!("opened tab {tab}") });
            answer["tab"] = info(app, browser, tab).unwrap_or(Value::Null);
            return answer;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let mut answer = refused("timeout", "the page did not finish loading in 30 seconds; it is still open");
    answer["tab"] = info(app, browser, tab).unwrap_or(Value::Null);
    answer
}

fn tabs(app: &AppHandle, browser: &Browser) -> Value {
    let ids: Vec<u32> = browser.inner.lock().unwrap().tabs.keys().copied().collect();
    let list: Vec<Value> = ids.iter().filter_map(|&t| info(app, browser, t)).collect();
    let lines: Vec<String> = list
        .iter()
        .map(|t| format!("tab {}  {}  {}", t["id"], t["url"].as_str().unwrap_or(""), t["title"].as_str().unwrap_or("")))
        .collect();
    let output = if lines.is_empty() { "no tabs are open".to_string() } else { lines.join("\n") };
    json!({ "ok": true, "output": output, "tabs": list })
}

// ---- hands in the page --------------------------------------------------------------------------

fn run_page(app: &AppHandle, browser: &Browser, tab: u32, hand: &str, input: &Value, timeout: Duration) -> Value {
    let Some(window) = app.get_webview_window(&label_of(tab)) else {
        return refused("no_tab", "that tab is not open");
    };
    let id = random_hex();
    let (tx, rx) = channel();
    browser.inner.lock().unwrap().pending.insert(id.clone(), tx);
    let script = format!(
        "window.__athenaHands && window.__athenaHands.run({}, {}, {});",
        json!(id),
        json!(hand),
        input
    );
    if let Err(e) = window.eval(script) {
        browser.inner.lock().unwrap().pending.remove(&id);
        return refused("failed", &format!("the page could not be reached ({e})"));
    }
    match rx.recv_timeout(timeout) {
        Ok(answer) => answer,
        Err(_) => {
            browser.inner.lock().unwrap().pending.remove(&id);
            refused("timeout", "the page did not answer; it may still be loading")
        }
    }
}

const B64: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let n = (u32::from(chunk[0]) << 16)
            | (u32::from(*chunk.get(1).unwrap_or(&0)) << 8)
            | u32::from(*chunk.get(2).unwrap_or(&0));
        out.push(B64[(n >> 18) as usize & 63] as char);
        out.push(B64[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { B64[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { B64[n as usize & 63] as char } else { '=' });
    }
    out
}

/// A file the daemon names must sit in a project's files under the app's data folder.
fn inside_files(data_dir: &Path, path: &Path) -> Option<PathBuf> {
    let root = data_dir.join("spaces").canonicalize().ok()?;
    let real = path.canonicalize().ok()?;
    (real.starts_with(&root) && real.components().any(|c| c.as_os_str() == "files")).then_some(real)
}

fn upload(app: &AppHandle, browser: &Browser, tab: u32, args: &Value) -> Value {
    let file = &args["file"];
    let Some(path) = file["path"].as_str().and_then(|p| inside_files(&browser.data_dir, Path::new(p))) else {
        return refused("refused", "that file is not in the project's files");
    };
    let Ok(bytes) = std::fs::read(&path) else { return refused("failed", "the file could not be read") };
    if bytes.len() as u64 > UPLOAD_MAX {
        return refused("refused", "the file is larger than 2 GB");
    }
    let Some(window) = app.get_webview_window(&label_of(tab)) else {
        return refused("no_tab", "that tab is not open");
    };
    let started = Instant::now();
    let stage = random_hex();
    let parts: Vec<&[u8]> = if bytes.is_empty() { vec![&[][..]] } else { bytes.chunks(UPLOAD_PART).collect() };
    let count = parts.len();
    for (i, part) in parts.into_iter().enumerate() {
        let script = format!(
            "window.__athenaHands && window.__athenaHands.stage({}, {i}, \"{}\", {count});",
            json!(stage),
            base64(part)
        );
        if window.eval(script).is_err() {
            return refused("failed", "the file could not be handed to the page");
        }
    }
    let staged_ms = started.elapsed().as_millis();
    let input = json!({
        "ref": args["ref"], "expect": args["expect"], "stage": stage,
        "name": file["name"], "mime": file["mime"], "size": bytes.len(),
    });
    let timeout = PAGE_TIMEOUT + Duration::from_millis(bytes.len() as u64 / 20_000);
    let mut answer = run_page(app, browser, tab, "page_upload", &input, timeout);
    answer["measured"] = json!({ "bytes": bytes.len(), "parts": count, "staged_ms": staged_ms,
        "total_ms": started.elapsed().as_millis() });
    answer
}

fn downloaded(browser: &Browser, label: &str, event: DownloadEvent<'_>) -> bool {
    let Some(tab) = tab_of(label) else { return false };
    let mut inner = browser.inner.lock().unwrap();
    let Some(armed) = inner.armed.get_mut(&tab) else { return false };
    match event {
        DownloadEvent::Requested { url, destination } => {
            let suggested = destination
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .or_else(|| url.path_segments().and_then(|mut s| s.next_back()).map(str::to_string))
                .unwrap_or_else(|| "download".to_string());
            let safe: String = suggested
                .chars()
                .map(|c| if c.is_alphanumeric() || matches!(c, '.' | '-' | '_') { c } else { '_' })
                .take(120)
                .collect();
            let _ = std::fs::create_dir_all(&armed.dir);
            *destination = armed.dir.join(format!("{}-{safe}", armed.call));
            true
        }
        DownloadEvent::Finished { path, success, .. } => {
            armed.done = Some(match (success, path) {
                (true, Some(p)) => Ok(p),
                _ => Err("the download did not finish".to_string()),
            });
            true
        }
        _ => true,
    }
}

fn download(app: &AppHandle, browser: &Browser, tab: u32, call: &str, args: &Value) -> Value {
    let Some(dir) = args["dir"].as_str().map(PathBuf::from) else {
        return refused("refused", "no folder was named for the download");
    };
    if !dir.starts_with(&browser.data_dir) {
        return refused("refused", "a download lands only in a project's files");
    }
    browser.inner.lock().unwrap().armed.insert(tab, Armed { dir, call: call.to_string(), done: None });
    let click = run_page(app, browser, tab, "page_click", &json!({ "ref": args["ref"], "expect": args["expect"] }), PAGE_TIMEOUT);
    if click["ok"] != json!(true) {
        browser.inner.lock().unwrap().armed.remove(&tab);
        return click;
    }
    let started = Instant::now();
    loop {
        let finished = {
            let mut inner = browser.inner.lock().unwrap();
            let done = inner.armed.get_mut(&tab).and_then(|a| a.done.take());
            if done.is_some() {
                inner.armed.remove(&tab);
            }
            done
        };
        match finished {
            Some(Ok(path)) => {
                let name = path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
                let name = name.strip_prefix(&format!("{call}-")).unwrap_or(&name).to_string();
                return json!({ "ok": true, "output": format!("downloaded {name}"),
                    "file": { "path": path.to_string_lossy(), "name": name } });
            }
            Some(Err(e)) => return refused("failed", &e),
            None if started.elapsed() > DOWNLOAD_TIMEOUT => {
                browser.inner.lock().unwrap().armed.remove(&tab);
                return refused("timeout", "no download finished within five minutes");
            }
            None => std::thread::sleep(Duration::from_millis(150)),
        }
    }
}

/// Bring the tab forward with her one line, and tell the daemon when the page moves on.
fn wheel(app: &AppHandle, browser: &Shared, conn: &DaemonInfo, tab: u32, say: &str) -> Value {
    let Some(window) = app.get_webview_window(&label_of(tab)) else {
        return refused("no_tab", "that tab is not open");
    };
    let start = info(app, browser, tab).unwrap_or(Value::Null);
    let _ = window.set_title(&format!("Athena asks: {say}"));
    let _ = window.unminimize();
    let _ = window.show();
    let _ = window.set_focus();
    let (app, browser, conn) = (app.clone(), Arc::clone(browser), conn.clone());
    std::thread::spawn(move || {
        let started = Instant::now();
        let back = loop {
            std::thread::sleep(Duration::from_millis(500));
            let Some(now) = info(&app, &browser, tab) else { break "closed" };
            if now["load"] != start["load"] || now["url"] != start["url"] {
                break "back";
            }
            if started.elapsed() > WHEEL_LIMIT {
                break "timeout";
            }
        };
        if let Some(window) = app.get_webview_window(&label_of(tab)) {
            let _ = window.set_title("Her browser");
        }
        let note = json!({ "tab": tab, "state": back });
        let _ = http(&conn, "POST", "/browser/note", Some(&note.to_string()), Duration::from_secs(10));
    });
    json!({ "ok": true, "output": format!("tab {tab} is in front of the person") })
}

// ---- the relay ----------------------------------------------------------------------------------

fn dispatch(app: &AppHandle, browser: &Shared, conn: &DaemonInfo, call: &Value) -> Value {
    let id = call["id"].as_str().unwrap_or("");
    let hand = call["hand"].as_str().unwrap_or("");
    let args = &call["args"];
    match hand {
        "open" => return open(app, browser, args["url"].as_str().unwrap_or("")),
        "tabs" => return tabs(app, browser),
        _ => {}
    }
    let Some(tab) = call["tab"].as_u64().and_then(|t| u32::try_from(t).ok()) else {
        return refused("no_tab", "name the tab to act in");
    };
    let Some(now) = info(app, browser, tab) else { return refused("no_tab", "that tab is not open") };
    let moved_load = call.get("load").is_some_and(|l| !l.is_null() && *l != now["load"]);
    let moved_url = call.get("url").is_some_and(|u| !u.is_null() && *u != now["url"]);
    if moved_load || moved_url {
        return refused("moved", "the page has changed since this was asked; nothing was done");
    }
    let mut answer = match hand {
        "tab" => json!({ "ok": true, "output": format!("tab {tab}") }),
        "close" => {
            if let Some(w) = app.get_webview_window(&label_of(tab)) {
                let _ = w.close();
            }
            return json!({ "ok": true, "output": format!("closed tab {tab}") });
        }
        "wheel" => wheel(app, browser, conn, tab, args["say"].as_str().unwrap_or("")),
        "upload" => upload(app, browser, tab, args),
        "download" => download(app, browser, tab, id, args),
        h if h.starts_with("page_") => run_page(app, browser, tab, h, args, PAGE_TIMEOUT),
        _ => refused("refused", "her browser has no such hand"),
    };
    answer["tab"] = info(app, browser, tab).unwrap_or(Value::Null);
    answer
}

/// A plain HTTP/1.1 call to the loopback daemon: `(status, body)`.
fn http(conn: &DaemonInfo, method: &str, path: &str, body: Option<&str>, timeout: Duration) -> Result<(u16, String), String> {
    let addr = conn.url.strip_prefix("http://").ok_or("bad daemon address")?;
    let mut stream = TcpStream::connect(addr).map_err(|e| e.to_string())?;
    stream.set_read_timeout(Some(timeout)).map_err(|e| e.to_string())?;
    let body = body.unwrap_or("");
    let req = format!(
        "{method} {path} HTTP/1.1\r\nHost: {addr}\r\nAuthorization: Bearer {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        conn.token,
        body.len()
    );
    stream.write_all(req.as_bytes()).map_err(|e| e.to_string())?;
    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).map_err(|e| e.to_string())?;
    let text = String::from_utf8_lossy(&raw);
    let (head, rest) = text.split_once("\r\n\r\n").ok_or("no reply")?;
    let status = head.split_whitespace().nth(1).and_then(|s| s.parse().ok()).ok_or("no status")?;
    Ok((status, rest.to_string()))
}

/// The relay thread: long-poll the daemon for hand calls, run each, answer each once.
pub fn start(app: AppHandle, browser: Shared, daemon: Daemon) {
    std::thread::spawn(move || {
        let Ok(conn) = daemon::wait_for_info(&daemon) else { return };
        let wait = Duration::from_secs(POLL_WAIT_S + 10);
        loop {
            let path = format!("/browser/next?wait={POLL_WAIT_S}");
            let call = match http(&conn, "GET", &path, None, wait) {
                Ok((200, body)) => serde_json::from_str::<Value>(&body).ok().and_then(|v| v.get("call").cloned()),
                _ => {
                    std::thread::sleep(Duration::from_secs(2));
                    continue;
                }
            };
            let Some(call) = call.filter(|c| c.is_object()) else { continue };
            let (app, browser, conn) = (app.clone(), Arc::clone(&browser), conn.clone());
            // Each call on its own thread: a five-minute download never holds up a read.
            std::thread::spawn(move || {
                let result = dispatch(&app, &browser, &conn, &call);
                let done = json!({ "id": call["id"], "result": result });
                let _ = http(&conn, "POST", "/browser/done", Some(&done.to_string()), Duration::from_secs(10));
            });
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base64_matches_the_standard_alphabet_and_padding() {
        assert_eq!(base64(b""), "");
        assert_eq!(base64(b"f"), "Zg==");
        assert_eq!(base64(b"fo"), "Zm8=");
        assert_eq!(base64(b"foo"), "Zm9v");
        assert_eq!(base64(&[0xff, 0xfe, 0x00, 0x01]), "//4AAQ==");
    }

    #[test]
    fn a_tab_label_round_trips_and_nothing_else_is_a_tab() {
        assert_eq!(tab_of(&label_of(7)), Some(7));
        assert_eq!(tab_of("main"), None);
        assert_eq!(tab_of("athena"), None);
    }

    #[test]
    fn the_script_carries_a_nonce_slot_and_the_hands_the_daemon_names() {
        assert!(HANDS_JS.contains("__ATHENA_NONCE__"));
        for hand in ["page_read", "page_find", "page_wait", "page_scroll", "page_click", "page_fill",
            "page_select", "page_submit", "page_upload", "page_info"] {
            assert!(HANDS_JS.contains(&format!("{hand}(")), "{hand}");
        }
    }

    #[test]
    fn two_nonces_differ() {
        assert_ne!(random_hex(), random_hex());
    }
}
