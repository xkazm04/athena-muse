//! Athena's desktop shell: two windows (`main`, `athena`) over one loopback daemon (ADR 0002).

mod daemon;

use tauri::{AppHandle, Manager, RunEvent, State, WindowEvent};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use daemon::{Daemon, DaemonInfo};

/// Show and focus her window, or hide it when it is already up.
fn toggle(app: &AppHandle) {
    let Some(window) = app.get_webview_window("athena") else { return };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// `{url, token}` for the daemon; waits if it is still starting.
#[tauri::command]
async fn daemon_info(state: State<'_, Daemon>) -> Result<DaemonInfo, String> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || daemon::wait_for_info(&shared))
        .await
        .map_err(|_| "Athena's background service check was interrupted".to_string())?
}

/// Same as the global shortcut, for a button in the main window.
#[tauri::command]
fn toggle_athena(app: AppHandle) {
    toggle(&app);
}

pub fn run() {
    let shared = daemon::new_shared();
    let shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, pressed, event| {
                    if *pressed == shortcut && event.state() == ShortcutState::Pressed {
                        toggle(app);
                    }
                })
                .build(),
        )
        .manage(shared.clone())
        .invoke_handler(tauri::generate_handler![daemon_info, toggle_athena])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "athena" {
                    // Her window is summoned again with the shortcut; closing only puts her away.
                    api.prevent_close();
                    let _ = window.hide();
                } else {
                    // Her hidden window would otherwise keep the process alive after the main one closes.
                    window.app_handle().exit(0);
                }
            }
        })
        .setup(move |app| {
            let data_dir = app.path().app_data_dir()?;
            daemon::start(shared.clone(), data_dir);
            // Another app may own the chord; Athena still works from the button.
            if let Err(e) = app.global_shortcut().register(shortcut) {
                eprintln!("could not register Ctrl+Shift+Space: {e}");
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Athena shell");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            let shared = app.state::<Daemon>();
            daemon::stop(shared.inner());
        }
    });
}
