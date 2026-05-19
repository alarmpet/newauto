use std::{
    io::{BufRead, BufReader},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{mpsc, Mutex},
    time::Duration,
};

use tauri::{Manager, Url};

struct SidecarState {
    child: Mutex<Option<Child>>,
    #[cfg(windows)]
    _job: windows_job::JobHandle,
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let (child, port) = start_sidecar(app)?;
            #[cfg(windows)]
            let job = windows_job::create_kill_on_close_job(&child)?;
            app.manage(SidecarState {
                child: Mutex::new(Some(child)),
                #[cfg(windows)]
                _job: job,
            });

            if let Some(port_file) = std::env::var_os("NEWAUTO_STUDIO_PORT_FILE").map(PathBuf::from)
            {
                if let Some(parent) = port_file.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(port_file, port.to_string())?;
            }

            if let Some(window) = app.get_webview_window("main") {
                let url = Url::parse(&format!("http://127.0.0.1:{port}/"))?;
                window.navigate(url)?;
                window.show()?;
                window.unminimize()?;
                window.center()?;
                window.set_focus()?;
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running newauto Studio");
}

fn start_sidecar(app: &tauri::App) -> Result<(Child, u16), Box<dyn std::error::Error>> {
    let sidecar = find_sidecar(app)?;
    let data_dir = app.path().app_local_data_dir()?;
    std::fs::create_dir_all(&data_dir)?;

    let mut command = Command::new(&sidecar);
    command
        .args(["--serve", "--host", "127.0.0.1", "--port", "0"])
        .env("NEWAUTO_DATA_DIR", data_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    if std::env::var_os("NEWAUTO_STUDIO_DISABLE_BACKGROUND_WORKERS").as_deref()
        == Some(std::ffi::OsStr::new("1"))
    {
        command.env("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1");
    }
    let mut child = command.spawn()?;

    let stdout = child
        .stdout
        .take()
        .ok_or("sidecar stdout pipe was not available")?;
    let (port_sender, port_receiver) = mpsc::channel();

    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().map_while(Result::ok) {
            if let Some(port_text) = line.strip_prefix("NEWAUTO_LISTEN_PORT=") {
                if let Ok(port) = port_text.trim().parse::<u16>() {
                    let _ = port_sender.send(port);
                }
            }
        }
    });

    if let Ok(port) = port_receiver.recv_timeout(Duration::from_secs(30)) {
        return Ok((child, port));
    };

    let _ = child.kill();
    let _ = child.wait();
    Err(format!(
        "sidecar did not print NEWAUTO_LISTEN_PORT before timeout: {}",
        sidecar.display()
    )
    .into())
}

fn find_sidecar(app: &tauri::App) -> Result<PathBuf, Box<dyn std::error::Error>> {
    if let Some(path) = std::env::var_os("NEWAUTO_SIDECAR_EXE").map(PathBuf::from) {
        if path.exists() {
            return Ok(path);
        }
    }

    let resource_candidate = app
        .path()
        .resource_dir()
        .ok()
        .map(|dir| dir.join("newauto-sidecar").join("newauto-sidecar.exe"));
    if let Some(path) = resource_candidate {
        if path.exists() {
            return Ok(path);
        }
    }

    let dev_candidate = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("dist")
        .join("newauto-sidecar")
        .join("newauto-sidecar.exe");
    if dev_candidate.exists() {
        return Ok(dev_candidate);
    }

    Err("newauto sidecar executable was not found".into())
}

#[cfg(windows)]
mod windows_job {
    use std::{mem::size_of, os::windows::io::AsRawHandle, process::Child};

    use windows_sys::Win32::{
        Foundation::{CloseHandle, HANDLE},
        System::JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
            SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        },
    };

    pub struct JobHandle(HANDLE);

    unsafe impl Send for JobHandle {}
    unsafe impl Sync for JobHandle {}

    impl Drop for JobHandle {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe {
                    CloseHandle(self.0);
                }
            }
        }
    }

    pub fn create_kill_on_close_job(
        child: &Child,
    ) -> Result<JobHandle, Box<dyn std::error::Error>> {
        let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if job.is_null() {
            return Err(std::io::Error::last_os_error().into());
        }

        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

        let set_ok = unsafe {
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        };
        if set_ok == 0 {
            let error = std::io::Error::last_os_error();
            unsafe {
                CloseHandle(job);
            }
            return Err(error.into());
        }

        let process_handle = child.as_raw_handle() as HANDLE;
        let assign_ok = unsafe { AssignProcessToJobObject(job, process_handle) };
        if assign_ok == 0 {
            let error = std::io::Error::last_os_error();
            unsafe {
                CloseHandle(job);
            }
            return Err(error.into());
        }

        Ok(JobHandle(job))
    }
}
