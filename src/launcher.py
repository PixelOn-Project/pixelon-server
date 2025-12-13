import os
import sys
import subprocess
import threading
import time
import webbrowser
import customtkinter as ctk
from PIL import Image
import pystray
from pystray import MenuItem as item

# [Config]
# 1. 실행 파일이 있는 실제 경로 (서버 실행 파일 찾기용)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 리소스 파일이 있는 경로 (아이콘 찾기용)
# PyInstaller --onefile 빌드 시 데이터는 sys._MEIPASS 임시 폴더에 풀립니다.
if getattr(sys, 'frozen', False):
    RESOURCE_DIR = sys._MEIPASS
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

# 서버 실행 파일 경로
if getattr(sys, 'frozen', False):
    # [배포 모드] Launcher와 Server가 같은 폴더에 설치됨
    SERVER_EXE = os.path.join(BASE_DIR, "PixelOnServer.exe")
else:
    # [개발 모드]
    SERVER_EXE = os.path.join(BASE_DIR, '..', 'dist', 'PixelOnServer', 'PixelOnServer.exe')

# 아이콘 경로 (리소스 폴더 기준)
ICON_PATH = os.path.join(RESOURCE_DIR, "icon.ico") 

class PixelOnTrayApp:
    def __init__(self):
        self.server_process = None
        self.log_window = None
        self.is_running = True
        
        # Tkinter Root 생성
        self.root = ctk.CTk()
        self.root.withdraw()

        # 서버 실행
        self.start_server()

        # 트레이 아이콘 설정
        self.setup_tray()

    def run(self):
        """애플리케이션 실행 진입점"""
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.mainloop()

    def start_server(self):
        """서버 프로세스 시작"""
        server_path = os.path.normpath(SERVER_EXE)
        
        if os.path.exists(server_path):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            server_dir = os.path.dirname(server_path)
            
            self.server_process = subprocess.Popen(
                [server_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                cwd=server_dir 
            )
            threading.Thread(target=self.monitor_server, daemon=True).start()
        else:
            print(f"Server executable not found at: {server_path}")
            # 개발 중이거나 파일이 없을 때 알림
            # sys.exit(1)

    def monitor_server(self):
        while self.is_running:
            if self.server_process and self.server_process.poll() is not None:
                print("Server exited. Closing launcher...")
                self.root.after(0, self.quit_app)
                break
            time.sleep(1)

    def setup_tray(self):
        if os.path.exists(ICON_PATH):
            image = Image.open(ICON_PATH)
        else:
            # 아이콘 파일이 없으면 기본 이미지 생성 (디버깅용)
            image = Image.new('RGB', (64, 64), color=(73, 109, 137))
            print(f"Icon not found at {ICON_PATH}, using default.")

        menu = (
            item('Open Web UI', self.open_web),
            item('View Logs', self.show_logs),
            item('Exit', self.quit_app)
        )

        self.icon = pystray.Icon("PixelOn", image, "PixelOn Server", menu)

    def open_web(self):
        webbrowser.open("http://127.0.0.1:5000")

    def show_logs(self):
        self.root.after(0, self._show_logs_impl)

    def _show_logs_impl(self):
        if self.log_window is None or not self.log_window.winfo_exists():
            self.log_window = LogWindow(self.server_process)
        else:
            self.log_window.focus()

    def quit_app(self, icon=None, item=None):
        self.is_running = False
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate() 
        
        if hasattr(self, 'icon') and self.icon:
            self.icon.stop()
        
        self.root.quit()
        sys.exit(0)

class LogWindow(ctk.CTkToplevel):
    def __init__(self, process):
        super().__init__()
        self.title("PixelOn Server Logs")
        self.geometry("600x400")
        
        self.textbox = ctk.CTkTextbox(self, width=580, height=380)
        self.textbox.pack(padx=10, pady=10)
        
        self.process = process
        self.reading = True
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        threading.Thread(target=self.read_logs, daemon=True).start()

    def on_close(self):
        self.reading = False
        self.destroy()

    def read_logs(self):
        if not self.process: return
        while self.reading and self.process:
            try:
                line = self.process.stdout.readline()
                if line:
                    if self.reading:
                        self.after(0, self.append_log, line)
                else:
                    if self.process.poll() is not None:
                        break
            except Exception:
                break
    
    def append_log(self, text):
        try:
            self.textbox.insert("end", text)
            self.textbox.see("end")
        except Exception:
            pass

if __name__ == "__main__":
    app = PixelOnTrayApp()
    app.run()