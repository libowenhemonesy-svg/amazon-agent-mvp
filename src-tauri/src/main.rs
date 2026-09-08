#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

/// 包装 Python 子进程，让 Tauri 管理其生命周期
struct Server {
    child: Mutex<Option<Child>>,
}

/// 找到项目根目录（exe 所在目录的父目录，即包含 app/ 的目录）
fn find_project_root() -> PathBuf {
    // 优先用 TAURI_PROJECT_ROOT 环境变量
    if let Ok(path) = env::var("TAURI_PROJECT_ROOT") {
        return PathBuf::from(path);
    }
    // 回退：exe 同级目录（开发模式 exe 在 src-tauri/target/ 下）
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            let candidate = dir.join("..").join("..").canonicalize().ok();
            // debug: target/debug/ → 回退三级到项目根
            if let Some(ref p) = candidate {
                if p.join("app").exists() {
                    return p.clone();
                }
            }
        }
    }
    // 最后回退到当前工作目录
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn main() {
    let project_root = find_project_root();

    // 先探测 Python 位置（.venv / python / python3）
    let venv_python = project_root
        .join(".venv")
        .join("Scripts")
        .join("python.exe");
    let python_cmd: Vec<String> = vec![
        venv_python.display().to_string(),
        "python".to_string(),
        "python3".to_string(),
    ];
    let python_exe = python_cmd
        .iter()
        .find(|cmd| Command::new(cmd).arg("--version").output().is_ok())
        .cloned()
        .unwrap_or_else(|| "python".to_string());

    // ── 启动 FastAPI 后端 ──────────────────────────────
    let python = Command::new(&python_exe)
        .args([
            "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8010",
        ])
        .current_dir(&project_root)
        .spawn()
        .unwrap_or_else(|_| panic!(
            "无法启动 Python 服务器\n项目目录: {}\nPython: {}\n请确保已安装 Python 和项目依赖",
            project_root.display(),
            python_exe
        ));

    // ── 等待服务器就绪 ─────────────────────────────────
    for _try in 1..=30 {
        std::thread::sleep(Duration::from_secs(1));
        if TcpStream::connect("127.0.0.1:8010").is_ok() {
            break;
        }
    }

    // ── 启动 Tauri 原生窗口 ─────────────────────────────
    tauri::Builder::default()
        .manage(Server {
            child: Mutex::new(Some(python)),
        })
        .on_window_event(|window, event| {
            // 用户关闭窗口时，自动结束 Python 进程
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(server) = window.try_state::<Server>() {
                    if let Ok(mut guard) = server.child.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("启动 Tauri 失败");
}
