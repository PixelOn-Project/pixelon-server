import os
import sys
import threading
import requests
import zipfile
import shutil
import ctypes
import winshell
import winreg
from win32com.client import Dispatch
import customtkinter as ctk
from tkinter import messagebox, filedialog
import multiprocessing 
import subprocess
import pythoncom 
from hardware_scan import check_system_capabilities

# [Fix] 스레드 내 COM 객체 사용을 위해 필요 (pywin32 설치 시 포함됨)
import pythoncom 
from hardware_scan import check_system_capabilities

# [Config]
DEBUG = True
APP_NAME = "PixelOn"
DEFAULT_INSTALL_PATH = r"C:\Program Files\PixelOn"
LAUNCHER_FILENAME = "PixelOnLauncher.exe"
MAINTENANCE_FILENAME = "Maintenance.exe" # 설치된 폴더에 복사될 인스톨러 이름

# Registry Key Path (Add/Remove Programs)
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PixelOnServer"

# ==============================================================================
# [GitHub Config] 최신 버전 자동 업데이트 설정
# ==============================================================================
GITHUB_OWNER = "PixelOn-Project"  # 예: leejet
GITHUB_REPO = "pixelon-server"         # 예: pixelon-server
SERVER_ASSET_NAME = "build.zip"        # 릴리즈에 업로드된 압축 파일명

# 1. 엔진(실행 바이너리) 다운로드 링크
MAJOR_VER = "master-377"
MINOR_VER = "2034588"

SERVER_CORE_URL = "https://github.com/PixelOn-Project/pixelon-server/releases/download/v0.0/build.zip" 

ENGINE_URLS = {
    "cuda": f"https://github.com/PixelOn-Project/pixelon-server/releases/download/v0.0/sd_core.zip",
    "vulkan": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-vulkan-x64.zip",
    "cpu_avx512": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx512-x64.zip",
    "cpu_avx2": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx2-x64.zip",
    "cpu_avx": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx-x64.zip",
}

# 2. 모델 다운로드 링크 (확장 가능 구조)
# key: UI 표시 이름, value: { url: 다운로드 주소, filename: 저장될 파일명 }
MODEL_OPTIONS = {
    "Stable Diffusion v1.5 (Standard)": {
        "url": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
        "filename": "sd_v-1-5.safetensors",
        "default": True
    },
    "DreamShaper v8 (Artistic)": {
         "url": "https://civitai.com/api/download/models/128713", 
         "filename": "dreamshaper_8.safetensors",
         "default": False
    },
    "Realistic Vision v6 (Photo)": {
         "url": "https://civitai.com/api/download/models/245598", 
         "filename": "realistic_vision_v6.safetensors",
         "default": False
    }
}

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def get_latest_release_url(owner, repo, asset_name):
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for asset in data.get('assets', []):
                if asset['name'] == asset_name:
                    return asset['browser_download_url']
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest release: {e}")
    return None

def get_installed_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_READ)
        path, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
        return path
    except:
        return None

def register_uninstaller(install_path):
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
        exe_path = os.path.join(install_path, MAINTENANCE_FILENAME)
        icon_path = os.path.join(install_path, LAUNCHER_FILENAME)
        
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_path)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Pixelon")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Registry registration failed: {e}")

def unregister_uninstaller():
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    except:
        pass

class PixelonInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pixelon Server Setup")
        self.geometry("700x800")
        self.resizable(False, False)

        self.sys_info = check_system_capabilities()
        self.selected_option = ctk.StringVar(value=self.sys_info['recommended'])
        
        self.model_vars = {} 
        self.model_checkboxes = [] 
        
        self.installed_path = get_installed_path()
        self.is_modify_mode = bool(self.installed_path and os.path.exists(self.installed_path))
        
        self.setup_ui()
        
        if self.is_modify_mode:
            self.init_modify_mode()

    def setup_ui(self):
        title_text = "Pixelon Manager" if self.is_modify_mode else "Pixelon Server Installer"
        ctk.CTkLabel(self, text=title_text, font=("Roboto Medium", 24)).pack(pady=(20, 10))

        path_frame = ctk.CTkFrame(self)
        path_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(path_frame, text="Location:").pack(side="left", padx=10)
        self.entry_path = ctk.CTkEntry(path_frame, width=400)
        
        if self.is_modify_mode:
            self.entry_path.insert(0, self.installed_path)
            self.entry_path.configure(state="disabled")
        else:
            self.entry_path.insert(0, DEFAULT_INSTALL_PATH)
            
        self.entry_path.pack(side="left", padx=10)
        
        self.btn_browse = ctk.CTkButton(path_frame, text="Browse", width=80, command=self.browse_folder)
        self.btn_browse.pack(side="left")
        if self.is_modify_mode:
            self.btn_browse.configure(state="disabled")

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        if self.is_modify_mode:
            self.btn_install = ctk.CTkButton(bottom_frame, text="MODIFY / UPDATE", command=self.start_install, 
                                           height=50, fg_color="#3B8ED0", hover_color="#36719F", font=("Roboto Bold", 18))
            self.btn_install.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            self.btn_uninstall = ctk.CTkButton(bottom_frame, text="UNINSTALL", command=self.start_uninstall, 
                                             height=50, fg_color="#D9534F", hover_color="#C9302C", font=("Roboto Bold", 18))
            self.btn_uninstall.pack(side="right", fill="x", expand=True, padx=(10, 0))
        else:
            self.btn_install = ctk.CTkButton(bottom_frame, text="INSTALL", command=self.start_install, height=50, font=("Roboto Bold", 18))
            self.btn_install.pack(side="bottom", fill="x", pady=10)

        self.status_lbl = ctk.CTkLabel(bottom_frame, text="Ready.")
        self.status_lbl.pack(side="bottom", pady=5)

        self.progress = ctk.CTkProgressBar(bottom_frame)
        self.progress.pack(side="bottom", fill="x", pady=10)
        self.progress.set(0)

        if not self.is_modify_mode:
            self.chk_shortcut = ctk.CTkCheckBox(bottom_frame, text="Create Desktop Shortcut", onvalue=True, offvalue=False)
            self.chk_shortcut.select()
            self.chk_shortcut.pack(side="bottom", pady=10)
        else:
            self.chk_shortcut = None

        opt_frame = ctk.CTkFrame(self)
        opt_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(opt_frame, text="AI Engine Selection (Re-installable)", font=("Roboto Medium", 16)).pack(pady=5)
        
        # [RESTORED] System Scan Info Message
        rec = self.sys_info['recommended']
        if rec == 'none':
            info_text = "System Scan: CRITICAL - No supported hardware found (AVX required)."
            msg_color = "#FF5555" # Red
        else:
            info_text = f"System Auto-Detected: {rec.upper()} is Optimal!"
            msg_color = "#2CC985" # Green
            
        ctk.CTkLabel(opt_frame, text=info_text, text_color=msg_color, font=("Roboto", 14)).pack(pady=2)
        
        self.rb_cuda = ctk.CTkRadioButton(opt_frame, text="GPU: NVIDIA CUDA 12+", variable=self.selected_option, value="cuda")
        self.rb_vulkan = ctk.CTkRadioButton(opt_frame, text="GPU: Vulkan", variable=self.selected_option, value="vulkan")
        self.rb_cpu512 = ctk.CTkRadioButton(opt_frame, text="CPU: AVX512", variable=self.selected_option, value="cpu_avx512")
        self.rb_cpu2 = ctk.CTkRadioButton(opt_frame, text="CPU: AVX2", variable=self.selected_option, value="cpu_avx2")
        self.rb_cpu = ctk.CTkRadioButton(opt_frame, text="CPU: AVX", variable=self.selected_option, value="cpu_avx")

        self.rb_cuda.pack(anchor="w", padx=40, pady=2)
        self.rb_vulkan.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu512.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu2.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu.pack(anchor="w", padx=40, pady=2)

        ctk.CTkLabel(opt_frame, text="--- AI Models ---", text_color="gray").pack(anchor="w", padx=40, pady=(15, 5))
        
        self.model_scroll = ctk.CTkScrollableFrame(opt_frame, label_text="Select Models to Download")
        self.model_scroll.pack(fill="both", expand=True, padx=40, pady=5)

        for name, info in MODEL_OPTIONS.items():
            is_checked = info.get("default", False)
            var = ctk.BooleanVar(value=is_checked)
            self.model_vars[name] = var
            chk = ctk.CTkCheckBox(self.model_scroll, text=name, variable=var)
            chk.pack(anchor="w", pady=2)
            self.model_checkboxes.append({"name": name, "widget": chk, "filename": info['filename']})

        self.update_option_states()

    def update_option_states(self):
        if not self.sys_info['cuda']: self.rb_cuda.configure(state="disabled")
        if not self.sys_info['cpu_avx512']: self.rb_cpu512.configure(state="disabled")
        if not self.sys_info['cpu_avx2']: self.rb_cpu2.configure(state="disabled")
        if not self.sys_info['cpu_avx']: self.rb_cpu.configure(state="disabled")

    def init_modify_mode(self):
        models_dir = os.path.join(self.installed_path, "models")
        for item in self.model_checkboxes:
            model_path = os.path.join(models_dir, item['filename'])
            if os.path.exists(model_path):
                chk = item['widget']
                chk.select()
                chk.configure(state="disabled", text=f"{item['name']} (Installed)")
                self.model_vars[item['name']].set(False) 

    def toggle_inputs(self, state="disabled"):
        self.btn_install.configure(state=state)
        if self.is_modify_mode:
            self.btn_uninstall.configure(state=state)
        else:
            self.btn_browse.configure(state=state)
            self.entry_path.configure(state=state)
            if self.chk_shortcut:
                self.chk_shortcut.configure(state=state)
        
        if state == "disabled":
            self.rb_cuda.configure(state="disabled")
            self.rb_vulkan.configure(state="disabled")
            self.rb_cpu512.configure(state="disabled")
            self.rb_cpu2.configure(state="disabled")
            self.rb_cpu.configure(state="disabled")
        else:
            self.update_option_states()

        for item in self.model_checkboxes:
            if self.is_modify_mode and "(Installed)" in item['widget'].cget("text"):
                continue
            item['widget'].configure(state=state)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def start_install(self):
        self.toggle_inputs("disabled")
        threading.Thread(target=self.install_process, daemon=True).start()

    def start_uninstall(self):
        if messagebox.askyesno("Uninstall", "Are you sure you want to remove Pixelon Server?"):
            self.toggle_inputs("disabled")
            threading.Thread(target=self.uninstall_process, daemon=True).start()

    def install_process(self):
        target_dir = self.entry_path.get()
        mode = self.selected_option.get() 
        selected_models = []
        for name, var in self.model_vars.items():
            if var.get():
                info = MODEL_OPTIONS[name]
                if not os.path.exists(os.path.join(target_dir, "models", info['filename'])):
                    selected_models.append(name)

        try:
            self.update_status("Initializing..." if self.is_modify_mode else "Preparing Installation...")
            os.makedirs(target_dir, exist_ok=True)
            os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
            os.makedirs(os.path.join(target_dir, "models"), exist_ok=True)

            if getattr(sys, 'frozen', False):
                self_path = sys.executable
                maintenance_path = os.path.join(target_dir, MAINTENANCE_FILENAME)
                if os.path.abspath(self_path).lower() != os.path.abspath(maintenance_path).lower():
                    try:
                        shutil.copy2(self_path, maintenance_path)
                    except:
                        pass

            # [STEP 1] Server Core (Strictly Online)
            self.update_status("Checking for updates...")
            
            # GitHub API를 통해 최신 다운로드 URL 가져오기
            server_core_url = get_latest_release_url(GITHUB_OWNER, GITHUB_REPO, SERVER_ASSET_NAME)
            
            if not server_core_url:
                raise Exception(f"Could not find '{SERVER_ASSET_NAME}' in latest GitHub release.")

            self.update_status("Downloading Server Core (build.zip)...")
            build_zip_path = os.path.join(target_dir, "build.zip")
            
            # 다운로드 실행 (실패 시 Exception 발생으로 중단됨)
            self.download_file(server_core_url, build_zip_path, start_prog=0.0, end_prog=0.25)
            
            self.update_status("Extracting Server Core...")
            with zipfile.ZipFile(build_zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            os.remove(build_zip_path)
            self.update_progress(0.3)

            self.update_status(f"Installing AI Engine ({mode.upper()})...")
            engine_url = ENGINE_URLS.get(mode)
            engine_zip = os.path.join(target_dir, "engine.zip")
            self.download_file(engine_url, engine_zip, start_prog=0.3, end_prog=0.55)
            with zipfile.ZipFile(engine_zip, 'r') as zip_ref:
                zip_ref.extractall(os.path.join(target_dir, "bin"))
            os.remove(engine_zip)
            self.update_progress(0.6)
            
            model_count = len(selected_models)
            if model_count > 0:
                total_range = 0.35 
                chunk_per_model = total_range / model_count
                current_base_prog = 0.6

                for idx, model_name in enumerate(selected_models):
                    self.update_status(f"Downloading: {model_name}...")
                    info = MODEL_OPTIONS[model_name]
                    model_path = os.path.join(target_dir, "models", info["filename"])
                    start_p = current_base_prog
                    end_p = current_base_prog + chunk_per_model
                    self.download_file(info["url"], model_path, start_prog=start_p, end_prog=end_p)
                    current_base_prog = end_p
            else:
                self.update_status("No new models to download.")
                self.update_progress(0.95)

            if not self.is_modify_mode:
                if self.chk_shortcut and self.chk_shortcut.get():
                    launcher_path = os.path.join(target_dir, LAUNCHER_FILENAME)
                    self.create_shortcut(launcher_path, "Pixelon Server")
                
            register_uninstaller(target_dir)

            self.update_progress(1.0)
            self.update_status("Completed!")
            
            dst_launcher = os.path.join(target_dir, LAUNCHER_FILENAME)
            self.after(0, self.show_complete_message, target_dir, dst_launcher)

        except Exception as e:
            self.show_error(str(e))

    def uninstall_process(self):
        target_dir = self.installed_path
        if not target_dir or not os.path.exists(target_dir):
            self.show_error("Installation directory not found.")
            return

        try:
            self.update_status("Uninstalling...")
            self.update_progress(0.2)

            current_exe = os.path.abspath(sys.executable)
            
            for root, dirs, files in os.walk(target_dir, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    if os.path.abspath(file_path) != current_exe:
                        try:
                            os.remove(file_path)
                        except: pass
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except: pass
            
            self.update_progress(0.5)

            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            lnk_path = os.path.join(desktop, "Pixelon Server.lnk")
            if os.path.exists(lnk_path):
                os.remove(lnk_path)

            unregister_uninstaller()
            self.update_progress(0.9)

            batch_cmd = f'ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{target_dir}"'
            subprocess.Popen(batch_cmd, shell=True)

            self.update_progress(1.0)
            self.update_status("Uninstalled.")
            
            messagebox.showinfo("Uninstall", "Uninstallation Complete.\nThe remaining files will be removed automatically.")
            self.quit()

        except Exception as e:
            self.show_error(f"Uninstall failed: {e}")

    def show_complete_message(self, target_dir, dst_launcher):
        msg = "Modification Complete." if self.is_modify_mode else "Installation Complete.\nLaunch Pixelon Server now?"
        if messagebox.askyesno("Done", msg):
            if os.path.exists(dst_launcher):
                subprocess.Popen([dst_launcher], cwd=target_dir)
            self.quit()
        else:
            self.quit()

    def show_error(self, error_msg):
        self.after(0, lambda: messagebox.showerror("Error", f"Operation Failed:\n{error_msg}"))
        self.after(0, lambda: self.toggle_inputs("normal"))
        self.update_status("Failed.")

    def download_file(self, url, dest, start_prog, end_prog):
        try:
            response = requests.get(url, stream=True)
            total_length = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 1024 * 1024 
            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        downloaded += len(chunk)
                        f.write(chunk)
                        if total_length > 0:
                            file_progress = downloaded / total_length
                            overall_progress = start_prog + (file_progress * (end_prog - start_prog))
                            self.update_progress(overall_progress)
        except Exception as e:
            raise Exception(f"Download failed: {url}\n{str(e)}")

    def update_status(self, text):
        self.after(0, lambda: self.status_lbl.configure(text=text))

    def update_progress(self, val):
        self.after(0, lambda: self.progress.set(val))

    def create_shortcut(self, target, name):
        try:
            pythoncom.CoInitialize()
            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{name}.lnk")
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.TargetPath = target
            shortcut.WorkingDirectory = os.path.dirname(target)
            shortcut.IconLocation = target 
            shortcut.save()

            with open(path, "r+b") as f:
                f.seek(0x15)
                byte = f.read(1)
                if byte:
                    new_byte = bytes([byte[0] | 0x20])
                    f.seek(0x15)
                    f.write(new_byte)
            print(f"Shortcut created (Admin): {path}")
        except Exception as e:
            print(f"Shortcut failed: {e}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = PixelonInstaller()
    app.mainloop()