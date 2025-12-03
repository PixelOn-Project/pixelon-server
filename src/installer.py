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

# [Config]
DEBUG = True
APP_NAME = "PixelOn"
DEFAULT_INSTALL_PATH = r"C:\Program Files\PixelOn"
LAUNCHER_FILENAME = "PixelOnLauncher.exe"
MAINTENANCE_FILENAME = "Maintenance.exe" 

# Registry Key Path (Add/Remove Programs)
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PixelOnServer"

# ==============================================================================
# [GitHub Config]
# ==============================================================================
GITHUB_OWNER = "PixelOn-Project"
GITHUB_REPO = "pixelon-server"
SERVER_ASSET_NAME = "build.zip"

# 1. 엔진(실행 바이너리) 다운로드 링크
MAJOR_VER = "master-377"
MINOR_VER = "2034588"

# (참고용) 고정 URL
SERVER_CORE_URL = "https://github.com/PixelOn-Project/pixelon-server/releases/download/v0.0/build.zip" 

ENGINE_URLS = {
    "cuda": f"https://github.com/PixelOn-Project/pixelon-server/releases/download/v0.0/sd_core.zip",
    "vulkan": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-vulkan-x64.zip",
    "cpu_avx512": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx512-x64.zip",
    "cpu_avx2": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx2-x64.zip",
    "cpu_avx": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx-x64.zip",
    "cpu_noavx": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-noavx-x64.zip",
}

# ==============================================================================
# [New Config] Preset & File Registry
# ==============================================================================

FILE_REGISTRY = {
    "cetusMix.safetensors": "https://civitai.com/api/download/models/105924?type=Model&format=SafeTensor&size=pruned&fp=fp16", 
    "QteaMix.safetensors": "https://civitai.com/api/download/models/94654?type=Model&format=SafeTensor&size=pruned&fp=fp16",
    "PX64NOCAP.safetensors": "https://drive.google.com/uc?export=download&id=1UZYLjoX2NHkL6w5-NJl9kUIoRdD2I11Y",
    "PixelWorld.safetensors": "https://drive.google.com/uc?export=download&id=1q_zrFaUBmAHuHT2Sg-0sAQeyfrmY2Bg_"
}

PRESET_OPTIONS = {
    "Normal Style (Default)": {
        "id": "normal",
        "files": ["cetusMix.safetensors", "PX64NOCAP.safetensors"],
        "default": True,
        "description": "Standard Pixel Art Style"
    },
    "SD Character Style": {
        "id": "sd_character",
        "files": ["QteaMix.safetensors", "PX64NOCAP.safetensors"],
        "default": False,
        "description": "Character focused Pixel Art"
    },
    "Background Style": {
        "id": "background",
        "files": ["cetusMix.safetensors", "PixelWorld.safetensors"],
        "default": False,
        "description": "Scenery and Backgrounds"
    }
}

# ==============================================================================

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
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Registry registration failed: {e}")

def unregister_uninstaller():
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    except:
        pass

class PixelOnInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PixelOn Setup")
        self.geometry("500x850")
        self.resizable(False, False)

        self.sys_info = check_system_capabilities()
        
        rec = self.sys_info['recommended']
        if 'cpu' in rec:
            initial_value = 'cpu'
        else:
            initial_value = rec
            
        self.selected_option = ctk.StringVar(value=initial_value)
        
        self.preset_vars = {} 
        self.preset_checkboxes = [] 
        
        self.installed_path = get_installed_path()
        self.is_modify_mode = bool(self.installed_path and os.path.exists(self.installed_path))
        
        self.setup_ui()
        
        if self.is_modify_mode:
            self.init_modify_mode()

    def setup_ui(self):
        title_text = "PixelOn Manager" if self.is_modify_mode else "PixelOn Installer"
        ctk.CTkLabel(self, text=title_text, font=("Segoe UI", 28, "bold")).pack(pady=(25, 15))

        path_frame = ctk.CTkFrame(self, fg_color="transparent")
        path_frame.pack(fill="x", padx=30, pady=5)
        
        ctk.CTkLabel(path_frame, text="Install Location:", font=("Segoe UI", 12)).pack(anchor="w", padx=5, pady=(0, 5))
        
        path_input_frame = ctk.CTkFrame(path_frame, fg_color="transparent")
        path_input_frame.pack(fill="x")

        self.entry_path = ctk.CTkEntry(path_input_frame, height=35)
        if self.is_modify_mode:
            self.entry_path.insert(0, self.installed_path)
            self.entry_path.configure(state="disabled")
        else:
            self.entry_path.insert(0, DEFAULT_INSTALL_PATH)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_browse = ctk.CTkButton(
            path_input_frame, text="Browse", width=70, height=35, 
            fg_color="transparent", border_width=2, border_color="#3B8ED0", 
            text_color=("gray10", "#DCE4EE"), hover_color=("gray70", "gray30"),
            command=self.browse_folder
        )
        self.btn_browse.pack(side="right")
        if self.is_modify_mode:
            self.btn_browse.configure(state="disabled")

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=30, pady=30)

        self.progress = ctk.CTkProgressBar(bottom_frame, height=12, corner_radius=6)
        self.progress.pack(side="bottom", fill="x", pady=(5, 0))
        self.progress.set(0)

        self.status_lbl = ctk.CTkLabel(bottom_frame, text="Ready to start.", text_color="gray")
        self.status_lbl.pack(side="bottom", pady=(2, 2))

        if not self.is_modify_mode:
            self.chk_shortcut = ctk.CTkCheckBox(bottom_frame, text="Create Desktop Shortcut", onvalue=True, offvalue=False)
            self.chk_shortcut.select()
            self.chk_shortcut.pack(side="bottom", anchor="w", pady=(0, 5))
        else:
            self.chk_shortcut = None

        btn_font = ("Segoe UI", 16, "bold")
        btn_height = 55 

        if self.is_modify_mode:
            self.btn_uninstall = ctk.CTkButton(
                bottom_frame, text="UNINSTALL", command=self.start_uninstall, 
                height=btn_height, corner_radius=12, font=btn_font,
                fg_color="#C0392B", hover_color="#922B21"
            )
            self.btn_uninstall.pack(side="bottom", fill="x", pady=(5, 0)) 
            
            self.btn_install = ctk.CTkButton(
                bottom_frame, text="UPDATE / MODIFY", command=self.start_install, 
                height=btn_height, corner_radius=12, font=btn_font,
                fg_color="#1F6AA5", hover_color="#144870"
            )
            self.btn_install.pack(side="bottom", fill="x", pady=(10, 5))
        else:
            self.btn_install = ctk.CTkButton(
                bottom_frame, text="INSTALL NOW", command=self.start_install, 
                height=btn_height, corner_radius=12, font=btn_font,
                fg_color="#2CC985", hover_color="#229966"
            )
            self.btn_install.pack(side="bottom", fill="x", pady=(5, 0))

        main_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"), corner_radius=20)
        main_frame.pack(side="top", fill="both", expand=True, padx=30, pady=20)

        ctk.CTkLabel(main_frame, text="AI Engine (Backend)", font=("Segoe UI", 16, "bold")).pack(pady=(20, 5))
        
        rec = self.sys_info['recommended']
        info_text = f"Auto-Detected: {rec.upper()} is Optimal"
        msg_color = "#2ECC71" 
        
        if rec == 'none':
            info_text = "Standard CPU mode selected."
            msg_color = "#F1C40F"
            
        ctk.CTkLabel(main_frame, text=info_text, text_color=msg_color, font=("Segoe UI", 13)).pack(pady=(0, 10))
        
        radio_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        radio_frame.pack(anchor="w", padx=20)

        self.rb_cuda = ctk.CTkRadioButton(radio_frame, text="GPU: NVIDIA CUDA 12+", variable=self.selected_option, value="cuda")
        self.rb_vulkan = ctk.CTkRadioButton(radio_frame, text="GPU: Vulkan", variable=self.selected_option, value="vulkan")
        self.rb_cpu = ctk.CTkRadioButton(radio_frame, text="CPU (Auto-Detect)", variable=self.selected_option, value="cpu")

        self.rb_cuda.pack(anchor="w", pady=4)
        self.rb_vulkan.pack(anchor="w", pady=4)
        self.rb_cpu.pack(anchor="w", pady=4)

        ctk.CTkLabel(main_frame, text="Style Presets", font=("Segoe UI", 16, "bold")).pack(pady=(25, 5))
        
        self.preset_frame = ctk.CTkFrame(main_frame, fg_color=("gray90", "gray17"), corner_radius=10)
        self.preset_frame.pack(fill="x", padx=20, pady=10)

        for name, info in PRESET_OPTIONS.items():
            is_checked = info.get("default", False)
            var = ctk.BooleanVar(value=is_checked)
            self.preset_vars[name] = var
            
            display_text = f"{name}\n{info['description']}"
            chk = ctk.CTkCheckBox(self.preset_frame, text=display_text, variable=var, font=("Segoe UI", 13))
            chk.pack(anchor="w", padx=15, pady=10)
            
            if info.get("id") == "normal":
                chk.configure(state="disabled")
            
            self.preset_checkboxes.append({"name": name, "id": info['id'], "widget": chk})

        self.update_option_states()

    def update_option_states(self):
        if not self.sys_info['cuda']: self.rb_cuda.configure(state="disabled")
        if not self.sys_info['vulkan'] and not self.sys_info['cuda']:
             self.rb_vulkan.configure(text="GPU: Vulkan (Not detected)")

    def init_modify_mode(self):
        models_dir = os.path.join(self.installed_path, "models")
        for item in self.preset_checkboxes:
            chk = item['widget'] 
            preset_info = PRESET_OPTIONS[item['name']]
            required_files = preset_info['files']
            
            all_exist = True
            for f in required_files:
                if not os.path.exists(os.path.join(models_dir, f)):
                    all_exist = False
                    break
            
            if all_exist:
                chk.select()
                chk.configure(state="disabled", text=f"{item['name']} (Installed)")
                self.preset_vars[item['name']].set(False) 
            else:
                if preset_info['id'] == "normal":
                     self.preset_vars[item['name']].set(True) 
                     chk.configure(state="disabled")

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
            self.rb_cpu.configure(state="disabled")
        else:
            self.update_option_states()

        for item in self.preset_checkboxes:
            if self.is_modify_mode and "(Installed)" in item['widget'].cget("text"):
                continue
            if PRESET_OPTIONS[item['name']]['id'] == "normal":
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
        if messagebox.askyesno("Uninstall", "Are you sure you want to remove PixelOn?"):
            self.toggle_inputs("disabled")
            threading.Thread(target=self.uninstall_process, daemon=True).start()

    def install_process(self):
        target_dir = self.entry_path.get()
        mode = self.selected_option.get() 
        
        files_to_download = set() 
        for name, var in self.preset_vars.items():
            if var.get(): 
                preset_info = PRESET_OPTIONS[name]
                for filename in preset_info['files']:
                    if not os.path.exists(os.path.join(target_dir, "models", filename)):
                        files_to_download.add(filename)
        
        download_list = list(files_to_download)

        try:
            self.update_status("Initializing..." if self.is_modify_mode else "Preparing Installation...")
            os.makedirs(target_dir, exist_ok=True)
            os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
            os.makedirs(os.path.join(target_dir, "models"), exist_ok=True)

            if getattr(sys, 'frozen', False):
                self_path = sys.executable
                maintenance_path = os.path.join(target_dir, MAINTENANCE_FILENAME)
                if os.path.abspath(self_path).lower() != os.path.abspath(maintenance_path).lower():
                    try: shutil.copy2(self_path, maintenance_path)
                    except: pass

            self.update_status("Checking for updates...")
            server_core_url = get_latest_release_url(GITHUB_OWNER, GITHUB_REPO, SERVER_ASSET_NAME)
            
            target_url = server_core_url if server_core_url else SERVER_CORE_URL

            self.update_status("Downloading Server Core...")
            build_zip_path = os.path.join(target_dir, "build.zip")
            self.download_file(target_url, build_zip_path, start_prog=0.0, end_prog=0.25)
            
            self.update_status("Extracting Server Core...")
            with zipfile.ZipFile(build_zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            os.remove(build_zip_path)
            self.update_progress(0.3)

            self.update_status(f"Installing AI Engine ({mode.upper()})...")
            
            engine_url = ""
            if mode == 'cpu':
                if self.sys_info.get('cpu_avx512'):
                    engine_url = ENGINE_URLS['cpu_avx512']
                elif self.sys_info.get('cpu_avx2'):
                    engine_url = ENGINE_URLS['cpu_avx2']
                elif self.sys_info.get('cpu_avx'):
                    engine_url = ENGINE_URLS['cpu_avx']
                else:
                    engine_url = ENGINE_URLS['cpu_noavx']
            else:
                engine_url = ENGINE_URLS.get(mode)

            engine_zip = os.path.join(target_dir, "engine.zip")
            self.download_file(engine_url, engine_zip, start_prog=0.3, end_prog=0.55)
            with zipfile.ZipFile(engine_zip, 'r') as zip_ref:
                zip_ref.extractall(os.path.join(target_dir, "bin"))
            os.remove(engine_zip)
            self.update_progress(0.6)
            
            file_count = len(download_list)
            if file_count > 0:
                total_range = 0.35 
                chunk_per_file = total_range / file_count
                current_base_prog = 0.6

                for idx, filename in enumerate(download_list):
                    self.update_status(f"Downloading File ({idx+1}/{file_count}): {filename}...")
                    url = FILE_REGISTRY.get(filename)
                    if not url:
                        print(f"Warning: URL for {filename} not found.")
                        continue

                    file_path = os.path.join(target_dir, "models", filename)
                    start_p = current_base_prog
                    end_p = current_base_prog + chunk_per_file
                    
                    self.download_file(url, file_path, start_prog=start_p, end_prog=end_p)
                    current_base_prog = end_p
            else:
                self.update_status("No new files to download.")
                self.update_progress(0.95)

            if not self.is_modify_mode:
                if self.chk_shortcut and self.chk_shortcut.get():
                    launcher_path = os.path.join(target_dir, LAUNCHER_FILENAME)
                    self.create_shortcut(launcher_path, "PixelOn")
                
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
                        try: os.remove(file_path)
                        except: pass
                for name in dirs:
                    try: os.rmdir(os.path.join(root, name))
                    except: pass
            
            self.update_progress(0.5)

            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            lnk_path = os.path.join(desktop, "PixelOn.lnk")
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
        msg = "Modification Complete." if self.is_modify_mode else "Installation Complete.\nLaunch PixelOn now?"
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
            session = requests.Session()
            response = session.get(url, stream=True)
            
            # [FIX] Google Drive Warning Bypass
            if "drive.google.com" in url:
                confirm_token = None
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        confirm_token = value
                        break
                
                if confirm_token:
                    # Construct URL with confirm token
                    if "?" in url:
                        confirm_url = f"{url}&confirm={confirm_token}"
                    else:
                        confirm_url = f"{url}?confirm={confirm_token}"
                    response = session.get(confirm_url, stream=True)

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
    app = PixelOnInstaller()
    app.mainloop()