/// Declaring the app's own commands turns on the app ACL manifest: a command is then reachable only
/// from a webview a capability grants it to. Without it, the pages of her browser (ADR 0013) could
/// call every command in `invoke_handler`; with it they get exactly one, `browser_reply`
/// (`capabilities/page.json`). A new command is added here, in `lib.rs` and in a capability file.
fn main() {
    println!("cargo:rerun-if-changed=src/hands.js");
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&["daemon_info", "toggle_athena", "browser_reply"]),
        ),
    )
    .expect("failed to run the Tauri build script");
}
