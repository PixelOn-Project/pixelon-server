import os
import sys
import threading
import requests
import zipfile
import shutil
import ctypes
import winshell
import winreg  # Windows Registry access
from win32com.client import Dispatch
import customtkinter as ctk
from tkinter import messagebox, filedialog
import multiprocessing 
import subprocess
from hardware_scan import check_system_capabilities

# [Fix] 스레드 내 COM 객체 사용을 위해 필요 (pywin32 설치 시 포함됨)
import pythoncom 
from hardware_scan import check_system_capabilities

# [Config]
DEBUG = True
APP_NAME = "PixelOn Server"
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
    "cuda_dll": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/cudart-sd-bin-win-cu12-x64.zip",
    "cuda": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-cuda12-x64.zip",
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

# ==============================================================================
if DEBUG:
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

ctk.set_appearance_mode("Dark")
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

# [Registry Helpers]
def get_installed_path():
    """레지스트리에서 설치 경로를 확인합니다."""
    try:
        # HKLM(관리자) 확인
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_READ)
        path, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
        return path
    except:
        return None

def register_uninstaller(install_path):
    """제어판 '프로그램 추가/제거'에 등록합니다."""
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
        
        exe_path = os.path.join(install_path, MAINTENANCE_FILENAME)
        icon_path = os.path.join(install_path, LAUNCHER_FILENAME)
        
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_path)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "PixelOn")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Registry registration failed: {e}")

def unregister_uninstaller():
    """레지스트리 키를 삭제합니다."""
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    except:
        pass

class PixelOnInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PixelOn Server Setup")
        self.geometry("700x800")
        self.resizable(False, False)

        self.sys_info = check_system_capabilities()
        self.selected_option = ctk.StringVar(value=self.sys_info['recommended'])
        
        self.model_vars = {} 
        self.model_checkboxes = [] 
        
        # [Install Check] 설치 여부 확인
        self.installed_path = get_installed_path()
        self.is_modify_mode = bool(self.installed_path and os.path.exists(self.installed_path))
        
        self.setup_ui()
        
        # [Modify Mode] 설치된 상태라면 UI 초기화 후 로직 수행
        if self.is_modify_mode:
            self.init_modify_mode()

    def setup_ui(self):
        # 1. Header
        title_text = "PixelOn Manager" if self.is_modify_mode else "PixelOn Installer"
        ctk.CTkLabel(self, text=title_text, font=("Roboto Medium", 24)).pack(pady=(20, 10))

        # 2. Path
        path_frame = ctk.CTkFrame(self)
        path_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(path_frame, text="Location:").pack(side="left", padx=10)
        self.entry_path = ctk.CTkEntry(path_frame, width=400)
        
        # 초기 경로 설정
        if self.is_modify_mode:
            self.entry_path.insert(0, self.installed_path)
            self.entry_path.configure(state="disabled") # 수정 모드에선 경로 변경 불가
        else:
            self.entry_path.insert(0, DEFAULT_INSTALL_PATH)
            
        self.entry_path.pack(side="left", padx=10)
        
        self.btn_browse = ctk.CTkButton(path_frame, text="Browse", width=80, command=self.browse_folder)
        self.btn_browse.pack(side="left")
        if self.is_modify_mode:
            self.btn_browse.configure(state="disabled")

        # 3. Bottom Panel
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        if self.is_modify_mode:
            # 수정/삭제 버튼 2개 배치
            self.btn_install = ctk.CTkButton(bottom_frame, text="MODIFY / UPDATE", command=self.start_install, 
                                           height=50, fg_color="#3B8ED0", hover_color="#36719F", font=("Roboto Bold", 18))
            self.btn_install.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            self.btn_uninstall = ctk.CTkButton(bottom_frame, text="UNINSTALL", command=self.start_uninstall, 
                                             height=50, fg_color="#D9534F", hover_color="#C9302C", font=("Roboto Bold", 18))
            self.btn_uninstall.pack(side="right", fill="x", expand=True, padx=(10, 0))
        else:
            # 설치 버튼 1개 배치
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

        # 4. Options
        opt_frame = ctk.CTkFrame(self)
        opt_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(opt_frame, text="AI Engine Selection (Re-installable)", font=("Roboto Medium", 16)).pack(pady=5)
        
        # Hardware Radio Buttons
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

        # Model Checkboxes
        ctk.CTkLabel(opt_frame, text="--- AI Models ---", text_color="gray").pack(anchor="w", padx=40, pady=(15, 5))
        
        self.model_scroll = ctk.CTkScrollableFrame(opt_frame, label_text="Select Models to Download")
        self.model_scroll.pack(fill="both", expand=True, padx=40, pady=5)

        for name, info in MODEL_OPTIONS.items():
            is_checked = info.get("default", False)
            var = ctk.BooleanVar(value=is_checked)
            self.model_vars[name] = var
            chk = ctk.CTkCheckBox(self.model_scroll, text=name, variable=var)
            chk.pack(anchor="w", pady=2)
            
            # 위젯 참조 저장 (나중에 비활성화 제어를 위해)
            # 딕셔너리에 name을 키로 저장하여 쉽게 찾을 수 있게 함
            self.model_checkboxes.append({"name": name, "widget": chk, "filename": info['filename']})

        self.update_option_states()

    def update_option_states(self):
        if not self.sys_info['cuda']: self.rb_cuda.configure(state="disabled")
        if not self.sys_info['cpu_avx512']: self.rb_cpu512.configure(state="disabled")
        if not self.sys_info['cpu_avx2']: self.rb_cpu2.configure(state="disabled")
        if not self.sys_info['cpu_avx']: self.rb_cpu.configure(state="disabled")

    def init_modify_mode(self):
        """수정 모드 초기화: 이미 설치된 모델 체크박스 비활성화"""
        models_dir = os.path.join(self.installed_path, "models")
        
        for item in self.model_checkboxes:
            model_path = os.path.join(models_dir, item['filename'])
            if os.path.exists(model_path):
                # 이미 설치된 모델
                chk = item['widget']
                chk.select() # 체크 상태로 변경
                chk.configure(state="disabled", text=f"{item['name']} (Installed)")
                self.model_vars[item['name']].set(False) # 로직상 선택되지 않은 것으로 처리하여 다운로드 스킵 (또는 로직에서 체크)

    def toggle_inputs(self, state="disabled"):
        self.btn_install.configure(state=state)
        if self.is_modify_mode:
            self.btn_uninstall.configure(state=state)
        else:
            self.btn_browse.configure(state=state)
            self.entry_path.configure(state=state)
            self.chk_shortcut.configure(state=state)
        
        # 라디오 및 체크박스 제어
        # (단순화를 위해 Modify 중에는 전체 잠금)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def start_install(self):
        self.toggle_inputs("disabled")
        threading.Thread(target=self.install_process, daemon=True).start()

    def start_uninstall(self):
        if messagebox.askyesno("Uninstall", "Are you sure you want to remove PixelOn Server?"):
            self.toggle_inputs("disabled")
            threading.Thread(target=self.uninstall_process, daemon=True).start()

    def install_process(self):
        target_dir = self.entry_path.get()
        mode = self.selected_option.get() 
        
        # [Modify Logic] 설치된 파일은 제외하고 선택된 것만 (새로 체크한 것만 True임)
        # init_modify_mode에서 이미 설치된건 var를 False로 바꿨으면 여기서 필터링됨
        # 하지만 UI상 체크되어 보이게 하려면 var=True하고 disabled해야함. 
        # 따라서 여기서 파일 존재 여부를 다시 체크하는게 안전함.
        selected_models = []
        for name, var in self.model_vars.items():
            # 체크되어 있고
            if var.get():
                # 파일이 없으면 다운로드 대상
                info = MODEL_OPTIONS[name]
                if not os.path.exists(os.path.join(target_dir, "models", info['filename'])):
                    selected_models.append(name)

        try:
            self.update_status("Initializing..." if self.is_modify_mode else "Preparing Installation...")
            os.makedirs(target_dir, exist_ok=True)
            os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
            os.makedirs(os.path.join(target_dir, "models"), exist_ok=True)

            # [Self Copy] 인스톨러 자신을 Maintenance.exe로 복사
            if getattr(sys, 'frozen', False):
                self_path = sys.executable
                maintenance_path = os.path.join(target_dir, MAINTENANCE_FILENAME)
                # 현재 실행중인 파일과 타겟이 다를 때만 복사 (수정 모드 실행 시 충돌 방지)
                if os.path.abspath(self_path).lower() != os.path.abspath(maintenance_path).lower():
                    try:
                        shutil.copy2(self_path, maintenance_path)
                    except:
                        print("Failed to copy maintenance tool (might be running)")

            # [STEP 1] Server Core (수정 모드에서는 보통 코어 업데이트 여부를 묻거나 스킵 가능하지만, 여기선 항상 최신화)
            self.update_status("Updating Server Core...")
            server_core_url = get_latest_release_url(GITHUB_OWNER, GITHUB_REPO, SERVER_ASSET_NAME)
            if server_core_url:
                build_zip_path = os.path.join(target_dir, "build.zip")
                self.download_file(server_core_url, build_zip_path, start_prog=0.0, end_prog=0.25)
                with zipfile.ZipFile(build_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                os.remove(build_zip_path)
            self.update_progress(0.3)

            # [STEP 2] Engine (항상 덮어쓰기 - 모드 변경 가능성)
            self.update_status(f"Installing AI Engine ({mode.upper()})...")
            engine_url = ENGINE_URLS.get(mode)
            engine_zip = os.path.join(target_dir, "engine.zip")
            self.download_file(engine_url, engine_zip, start_prog=0.3, end_prog=0.55)
            with zipfile.ZipFile(engine_zip, 'r') as zip_ref:
                zip_ref.extractall(os.path.join(target_dir, "bin"))
            os.remove(engine_zip)

            if mode == "cuda":
                # CUDA 모드는 추가 DLL도 필요
                self.update_status("Installing CUDA Runtime Libraries...")
                cuda_dll_url = ENGINE_URLS.get("cuda_dll")
                cuda_zip = os.path.join(target_dir, "cuda_dll.zip")
                self.download_file(cuda_dll_url, cuda_zip, start_prog=0.55, end_prog=0.6)
                with zipfile.ZipFile(cuda_zip, 'r') as zip_ref:
                    zip_ref.extractall(os.path.join(target_dir, "bin"))
                os.remove(cuda_zip)

            self.update_progress(0.6)
            
            # [STEP 3] Models
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

            # [STEP 4] Register & Shortcut
            if not self.is_modify_mode:
                if self.chk_shortcut.get():
                    launcher_path = os.path.join(target_dir, LAUNCHER_FILENAME)
                    self.create_shortcut(launcher_path, "PixelOn Server")
                
            # [Registry] 항상 갱신
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

            # 1. 파일 삭제 (Maintenance.exe 제외)
            # 현재 실행 중인 파일(자신)은 삭제할 수 없으므로 건너뜀
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

            # 2. 바로가기 삭제
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            lnk_path = os.path.join(desktop, "PixelOn Server.lnk")
            if os.path.exists(lnk_path):
                os.remove(lnk_path)

            # 3. 레지스트리 삭제
            unregister_uninstaller()
            self.update_progress(0.9)

            # 4. Self-Delete Scheduling
            # CMD를 이용해 프로세스 종료 후 파일 및 폴더 삭제
            # ping으로 딜레이를 주고 rmdir /s /q 로 강제 삭제
            batch_cmd = f'ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{target_dir}"'
            subprocess.Popen(batch_cmd, shell=True)

            self.update_progress(1.0)
            self.update_status("Uninstalled.")
            
            messagebox.showinfo("Uninstall", "Uninstallation Complete.\nThe remaining files will be removed automatically.")
            self.quit()

        except Exception as e:
            self.show_error(f"Uninstall failed: {e}")

    def show_complete_message(self, target_dir, dst_launcher):
        msg = "Modification Complete." if self.is_modify_mode else "Installation Complete.\nLaunch PixelOn Server now?"
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
        """스레드 안전한 바로 가기 생성 (관리자 권한 포함)"""
        try:
            # [Fix] 스레드 내부에서 COM 객체 초기화 (필수)
            pythoncom.CoInitialize()
            
            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{name}.lnk")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.TargetPath = target
            shortcut.WorkingDirectory = os.path.dirname(target)
            shortcut.IconLocation = target 
            shortcut.save()

            # [Fix] 바로 가기 속성 수정: "관리자 권한으로 실행" 체크
            # .lnk 파일의 21번째 바이트(0x15)에 0x20 비트를 설정하면 관리자 권한이 부여됩니다.
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
    # 관리자 권한 확인 (PyInstaller --uac-admin 사용 시 이 부분 자동 처리됨)
    app = PixelOnInstaller()
    app.mainloop()