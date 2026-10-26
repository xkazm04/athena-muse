//! The daemon child process: spawn, handshake, health check, shutdown.
//!
//! The shell owns the daemon's lifetime (ADR 0002). `daemon.json` `{port, token, pid}` is the
//! handshake; the token is never logged and never put in an error message.

use std::collections::VecDeque;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

const HANDSHAKE_WAIT: Duration = Duration::from_secs(20);
const STDERR_KEEP: usize = 12;

/// What a window needs to talk to the daemon.
#[derive(Clone, Serialize)]
pub struct DaemonInfo {
    pub url: String,
    pub token: String,
}

#[derive(Deserialize)]
struct Handshake {
    port: u16,
    token: String,
}

type Outcome = Result<DaemonInfo, String>;
type Tail = Arc<Mutex<VecDeque<String>>>;

/// Shared between the starter thread, the `daemon_info` command and the exit hook.
pub struct Shared {
    outcome: Mutex<Option<Outcome>>,
    ready: Condvar,
    child: Mutex<Option<Child>>,
}

pub type Daemon = Arc<Shared>;

pub fn new_shared() -> Daemon {
    Arc::new(Shared { outcome: Mutex::new(None), ready: Condvar::new(), child: Mutex::new(None) })
}

/// Repo root: `ATHENA_REPO` if set, else three levels above this crate (never a fixed machine path).
fn repo_root() -> PathBuf {
    if let Some(p) = std::env::var_os("ATHENA_REPO") {
        return PathBuf::from(p);
    }
    Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(3).map(Path::to_path_buf).unwrap_or_default()
}

fn finish(shared: &Shared, outcome: Outcome) {
    *shared.outcome.lock().unwrap() = Some(outcome);
    shared.ready.notify_all();
}

/// Spawn the daemon and publish the outcome on a background thread, so the windows paint at once.
pub fn start(shared: Daemon, data_dir: PathBuf) {
    std::thread::spawn(move || {
        let outcome = launch(&shared, &data_dir);
        finish(&shared, outcome);
    });
}

fn launch(shared: &Shared, data_dir: &Path) -> Outcome {
    std::fs::create_dir_all(data_dir).map_err(|e| format!("Athena could not prepare its data folder: {e}"))?;
    let handshake_path = data_dir.join("daemon.json");
    // A stale file from an earlier run would hand the windows a dead port.
    let _ = std::fs::remove_file(&handshake_path);

    let mut cmd = Command::new("uv");
    cmd.arg("run")
        .arg("--project")
        .arg(repo_root())
        .arg("athena-daemon")
        .arg("--data")
        .arg(data_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Athena's background service could not start ({e}). Is uv installed and on the path?"))?;

    // Keep the last stderr lines so a failure can say why, in plain words.
    let tail: Tail = Arc::new(Mutex::new(VecDeque::new()));
    if let Some(stderr) = child.stderr.take() {
        let tail = Arc::clone(&tail);
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                let mut t = tail.lock().unwrap();
                if t.len() == STDERR_KEEP {
                    t.pop_front();
                }
                t.push_back(line);
            }
        });
    }
    *shared.child.lock().unwrap() = Some(child);

    let started = Instant::now();
    let info = loop {
        if let Some(info) = read_handshake(&handshake_path) {
            break info;
        }
        let exited = {
            let mut guard = shared.child.lock().unwrap();
            match guard.as_mut().map(Child::try_wait) {
                Some(Ok(Some(status))) => Some(status.to_string()),
                _ => None,
            }
        };
        if let Some(status) = exited {
            return Err(failure(&format!("Athena's background service stopped at start ({status})"), &tail, None));
        }
        if started.elapsed() > HANDSHAKE_WAIT {
            return Err(failure("Athena's background service did not answer within 20 seconds", &tail, None));
        }
        std::thread::sleep(Duration::from_millis(150));
    };

    // The file proves the process wrote it; one health call proves it is serving.
    if !health_ok(&info.url) {
        return Err(failure("Athena's background service started but did not answer", &tail, Some(&info.token)));
    }
    Ok(info)
}

fn read_handshake(path: &Path) -> Option<DaemonInfo> {
    let text = std::fs::read_to_string(path).ok()?;
    let h: Handshake = serde_json::from_str(&text).ok()?;
    Some(DaemonInfo { url: format!("http://127.0.0.1:{}", h.port), token: h.token })
}

/// `GET /health` over a bare socket: the shell has no HTTP client and needs none for one call.
fn health_ok(url: &str) -> bool {
    let Some(addr) = url.strip_prefix("http://") else { return false };
    let Ok(mut stream) = TcpStream::connect(addr) else { return false };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let req = format!("GET /health HTTP/1.1\r\nHost: {addr}\r\nConnection: close\r\n\r\n");
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut head = String::new();
    let _ = stream.take(64).read_to_string(&mut head);
    head.starts_with("HTTP/1.1 200")
}

fn failure(what: &str, tail: &Tail, token: Option<&str>) -> String {
    // Give the reader thread a moment to drain a dying process's last words.
    std::thread::sleep(Duration::from_millis(200));
    let lines: Vec<String> = tail.lock().unwrap().iter().cloned().collect();
    let mut text = what.to_string();
    if !lines.is_empty() {
        text.push_str(". Its last words: ");
        text.push_str(&lines.join(" / "));
    }
    match token {
        Some(t) if !t.is_empty() => text.replace(t, "***"),
        _ => text,
    }
}

/// Block until the handshake is settled; called from the `daemon_info` command off the main thread.
pub fn wait_for_info(shared: &Shared) -> Outcome {
    let mut guard = shared.outcome.lock().unwrap();
    while guard.is_none() {
        guard = shared.ready.wait(guard).unwrap();
    }
    guard.clone().unwrap()
}

/// Stop the daemon and anything `uv` started under it.
pub fn stop(shared: &Shared) {
    let Some(mut child) = shared.child.lock().unwrap().take() else { return };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // `uv run` parents the real daemon; kill the whole tree or Python outlives the app.
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x0800_0000)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}
