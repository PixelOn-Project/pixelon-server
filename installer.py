import os
import sys
import threading
import requests
import zipfile
import shutil
import ctypes
import winshell
from win32com.client import Dispatch
import customtkinter as ctk
from tkinter import messagebox, filedialog
from hardware_scan import check_system_capabilities
import subprocess

# [Config]
DEFAULT_INSTALL_PATH = r"C:\Program Files\Pixelon"
LAUNCHER_FILENAME = "PixelonLauncher.exe"

# https://en.wikipedia.org/wiki/Configuration_file
# 1. 엔진(실행 바이너리) 다운로드 링크
MAJOR_VER = "master-377"
MINOR_VER = "2034588"

SERVER_CORE_URL = "https://example.com/path/to/your/build.zip" 

ENGINE_URLS = {
    "cuda_dll": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/cudart-sd-bin-win-cu12-x64.zip",
    "cuda": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-cuda12-x64.zip",
    "vulkan": "https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-vulkan-x64.zip",
    "cpu_avx512": "https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx512-x64.zip",
    "cpu_avx2": "https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx2-x64.zip",
    "cpu_avx": "https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx-x64.zip",
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
    """GitHub API를 통해 최신 릴리즈의 에셋 다운로드 URL을 가져옵니다."""
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        # 타임아웃 5초 설정
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # assets 목록에서 이름이 일치하는 파일 찾기
            for asset in data.get('assets', []):
                if asset['name'] == asset_name:
                    return asset['browser_download_url']
            print(f"[ERROR] Asset '{asset_name}' not found in latest release.")
        else:
            print(f"[ERROR] GitHub API Error: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest release: {e}")
    
    return None

class PixelonInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pixelon Server Setup")
        self.geometry("700x800") # UI가 잘리지 않도록 높이 넉넉하게 수정
        self.resizable(False, False)

        self.sys_info = check_system_capabilities()
        self.selected_option = ctk.StringVar(value=self.sys_info['recommended'])
        
        # 모델 체크박스 상태 저장용
        self.model_vars = {} 
        
        self.setup_ui()

    def setup_ui(self):
        # 1. 헤더 (Top)
        ctk.CTkLabel(self, text="Pixelon Server Installer", font=("Roboto Medium", 24)).pack(pady=(20, 10))

        # 2. 경로 설정 (Top)
        path_frame = ctk.CTkFrame(self)
        path_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(path_frame, text="Install Location:").pack(side="left", padx=10)
        self.entry_path = ctk.CTkEntry(path_frame, width=400)
        self.entry_path.insert(0, DEFAULT_INSTALL_PATH)
        self.entry_path.pack(side="left", padx=10)
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self.browse_folder).pack(side="left")

        # 3. 하단 컨트롤 패널 (Bottom - 고정 위치 확보)
        # side="bottom"으로 먼저 배치하여 화면 하단 영역을 확실하게 점유합니다.
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        # 하단부터 위로 쌓아올림 (Button -> Status -> Progress -> Checkbox)
        self.btn_install = ctk.CTkButton(bottom_frame, text="INSTALL", command=self.start_install, height=50, font=("Roboto Bold", 18))
        self.btn_install.pack(side="bottom", fill="x", pady=10)

        self.status_lbl = ctk.CTkLabel(bottom_frame, text="Ready to install.")
        self.status_lbl.pack(side="bottom", pady=5)

        self.progress = ctk.CTkProgressBar(bottom_frame)
        self.progress.pack(side="bottom", fill="x", pady=10)
        self.progress.set(0)

        self.chk_shortcut = ctk.CTkCheckBox(bottom_frame, text="Create Desktop Shortcut", onvalue=True, offvalue=False)
        self.chk_shortcut.select()
        self.chk_shortcut.pack(side="bottom", pady=10)

        # 4. 옵션 선택 영역 (Middle - 남은 공간 채움)
        # expand=True로 남은 세로 공간을 모두 차지하게 합니다.
        opt_frame = ctk.CTkFrame(self)
        opt_frame.pack(side="top", fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(opt_frame, text="Hardware Acceleration Selection", font=("Roboto Medium", 16)).pack(pady=5)
        
        # 안내 메시지
        info_text = "System Scan Complete.\n"
        rec = self.sys_info['recommended']
        if rec == 'none':
            info_text += "CRITICAL: No supported hardware found (AVX required)."
            msg_color = "red"
        else:
            info_text += f"Auto-selected best performance mode: {rec.upper()}"
            msg_color = "#2CC985"
        
        ctk.CTkLabel(opt_frame, text=info_text, text_color=msg_color).pack(pady=5)

        # 라디오 버튼 그룹
        self.rb_cuda = ctk.CTkRadioButton(opt_frame, text="GPU: NVIDIA CUDA 12+ (Fastest)", variable=self.selected_option, value="cuda")
        self.rb_vulkan = ctk.CTkRadioButton(opt_frame, text="GPU: Vulkan (Universal GPU)", variable=self.selected_option, value="vulkan")
        
        ctk.CTkLabel(opt_frame, text="--- CPU Fallback Options ---", text_color="gray").pack(anchor="w", padx=40, pady=(5, 0))
        
        self.rb_cpu512 = ctk.CTkRadioButton(opt_frame, text="CPU: AVX512 (High Performance)", variable=self.selected_option, value="cpu_avx512")
        self.rb_cpu2 = ctk.CTkRadioButton(opt_frame, text="CPU: AVX2 (Standard)", variable=self.selected_option, value="cpu_avx2")
        self.rb_cpu = ctk.CTkRadioButton(opt_frame, text="CPU: AVX (Legacy)", variable=self.selected_option, value="cpu_avx")

        self.rb_cuda.pack(anchor="w", padx=40, pady=2)
        self.rb_vulkan.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu512.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu2.pack(anchor="w", padx=40, pady=2)
        self.rb_cpu.pack(anchor="w", padx=40, pady=2)

        # 모델 선택 (체크박스)
        ctk.CTkLabel(opt_frame, text="--- AI Models (Multiple Selection) ---", text_color="gray").pack(anchor="w", padx=40, pady=(15, 5))
        
        self.model_scroll = ctk.CTkScrollableFrame(opt_frame, label_text="Select Models to Download")
        self.model_scroll.pack(fill="both", expand=True, padx=40, pady=5)

        for name, info in MODEL_OPTIONS.items():
            is_checked = info.get("default", False)
            var = ctk.BooleanVar(value=is_checked)
            self.model_vars[name] = var
            chk = ctk.CTkCheckBox(self.model_scroll, text=name, variable=var)
            chk.pack(anchor="w", pady=2)

        self.update_option_states()

    def update_option_states(self):
        if not self.sys_info['cuda']:
            self.rb_cuda.configure(state="disabled", text_color="gray")
        if not self.sys_info['vulkan'] and not self.sys_info['cuda']:
             self.rb_vulkan.configure(text="GPU: Vulkan (Not detected)")
        if not self.sys_info['cpu_avx512']:
            self.rb_cpu512.configure(state="disabled", text_color="gray", text="CPU: AVX512 (Not Supported)")
        if not self.sys_info['cpu_avx2']:
            self.rb_cpu2.configure(state="disabled", text_color="gray", text="CPU: AVX2 (Not Supported)")
        if not self.sys_info['cpu_avx']:
            self.rb_cpu.configure(state="disabled", text_color="gray", text="CPU: AVX (Not Supported)")

        if self.sys_info['recommended'] == 'none':
            self.btn_install.configure(state="disabled", text="Installation Impossible (No AVX)")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def start_install(self):
        self.btn_install.configure(state="disabled")
        threading.Thread(target=self.install_process, daemon=True).start()
        if not self.sys_info['cpu_avx512']:
            self.rb_cpu512.configure(state="disabled", text_color="gray", text="CPU: AVX512 (Not Supported)")
        if not self.sys_info['cpu_avx2']:
            self.rb_cpu2.configure(state="disabled", text_color="gray", text="CPU: AVX2 (Not Supported)")
        if not self.sys_info['cpu_avx']:
            self.rb_cpu.configure(state="disabled", text_color="gray", text="CPU: AVX (Not Supported)")

        if self.sys_info['recommended'] == 'none':
            self.btn_install.configure(state="disabled", text="Installation Impossible (No AVX)")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)

    def start_install(self):
        self.btn_install.configure(state="disabled")
        threading.Thread(target=self.install_process, daemon=True).start()

    def install_process(self):
        target_dir = self.entry_path.get()
        mode = self.selected_option.get() 
        selected_models = [name for name, var in self.model_vars.items() if var.get()]
        
        try:
            self.update_status("Initializing directories...")
            os.makedirs(target_dir, exist_ok=True)
            os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)
            os.makedirs(os.path.join(target_dir, "models"), exist_ok=True)

            # ==========================================================
            # [STEP 1] 서버 코어 파일 다운로드 (build.zip) - 0.0 ~ 0.3
            # ==========================================================
            # self.update_status("Downloading Server Core (build.zip)...")
            # build_zip_path = os.path.join(target_dir, "build.zip")
            
            # # 다운로드 (0.0 -> 0.3)
            # self.download_file(SERVER_CORE_URL, build_zip_path, start_prog=0.0, end_prog=0.25)
            
            # self.update_status("Extracting Server Core...")
            # with zipfile.ZipFile(build_zip_path, 'r') as zip_ref:
            #     # build.zip 안의 내용(_internal, exe들)을 target_dir 루트에 풉니다.
            #     zip_ref.extractall(target_dir)
            # os.remove(build_zip_path)
            self.update_progress(0.3)

            # ==========================================================
            # [STEP 2] 엔진(SD Backend) 다운로드 - 0.3 ~ 0.6
            # ==========================================================
            self.update_status(f"Downloading AI Engine ({mode.upper()})...")
            engine_url = ENGINE_URLS.get(mode)
            engine_zip = os.path.join(target_dir, "engine.zip")
            
            # 다운로드 (0.3 -> 0.55)
            self.download_file(engine_url, engine_zip, start_prog=0.3, end_prog=0.55)
            
            self.update_status("Extracting AI Engine...")
            with zipfile.ZipFile(engine_zip, 'r') as zip_ref:
                # 엔진 파일들은 'bin' 폴더에 풉니다.
                zip_ref.extractall(os.path.join(target_dir, "bin"))
            os.remove(engine_zip)

            extra = os.path.join(target_dir, "extra.zip")
            if mode == 'cuda':
                # CUDA는 별도 DLL 필요 시 추가 다운로드 로직 삽입
                self.download_file(ENGINE_URLS.get('cuda_dll'), extra, start_prog=0.5, end_prog=0.55)

                self.update_status("Extracting cuda files...")
                with zipfile.ZipFile(extra, 'r') as zip_ref:
                    zip_ref.extractall(os.path.join(target_dir, "bin"))
            self.update_progress(0.6)
            os.remove(extra)

            # ==========================================================
            # [STEP 3] 모델 다운로드 (다중) - 0.6 ~ 0.95
            # ==========================================================
            model_count = len(selected_models)
            if model_count > 0:
                total_range = 0.35 # 0.6 ~ 0.95 = 0.35
                chunk_per_model = total_range / model_count
                current_base_prog = 0.6

                for idx, model_name in enumerate(selected_models):
                    self.update_status(f"Downloading Model ({idx+1}/{model_count}): {model_name}...")
                    
                    info = MODEL_OPTIONS[model_name]
                    model_path = os.path.join(target_dir, "models", info["filename"])
                    
                    start_p = current_base_prog
                    end_p = current_base_prog + chunk_per_model
                    
                    self.download_file(info["url"], model_path, start_prog=start_p, end_prog=end_p)
                    current_base_prog = end_p
            else:
                self.update_status("No models selected (Skipping)...")
                self.update_progress(0.95)

            # ==========================================================
            # [STEP 4] 마무리
            # ==========================================================
            if self.chk_shortcut.get():
                self.update_status("Creating shortcuts...")
                # 설치된 런처(PixelonLauncher.exe)의 바로가기 생성
                launcher_path = os.path.join(target_dir, LAUNCHER_FILENAME)
                self.create_shortcut(launcher_path, "Pixelon Server")

            self.update_progress(1.0)
            self.update_status("Installation Complete!")
            
            # 완료 후 실행 여부 확인
            dst_launcher = os.path.join(target_dir, LAUNCHER_FILENAME)
            self.after(0, self.show_complete_message, target_dir, dst_launcher)

        except Exception as e:
            self.show_error(str(e))

    def show_complete_message(self, target_dir, dst_launcher):
        if messagebox.askyesno("Complete", "Installation finished successfully.\nLaunch Pixelon Server now?"):
            if os.path.exists(dst_launcher):
                subprocess.Popen([dst_launcher], cwd=target_dir)
            else:
                messagebox.showerror("Error", "Launcher not found. Please check installation.")
            self.quit()
        else:
            self.quit()

    def show_error(self, error_msg):
        self.after(0, lambda: messagebox.showerror("Error", f"Installation Failed:\n{error_msg}"))
        self.after(0, lambda: self.btn_install.configure(state="normal"))
        self.update_status("Failed.")

    def download_file(self, url, dest, start_prog, end_prog):
        try:
            response = requests.get(url, stream=True)
            total_length = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024*16): # 8MB
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
            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{name}.lnk")
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.TargetPath = target
            shortcut.WorkingDirectory = os.path.dirname(target)
            shortcut.IconLocation = target
            shortcut.save()
        except Exception as e:
            print(f"Shortcut creation failed: {e}")

if __name__ == "__main__":
    app = PixelonInstaller()
    app.mainloop()