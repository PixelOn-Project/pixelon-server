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
# 런처는 설치된 폴더(bin의 상위)에 위치한다고 가정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_EXE = os.path.join(BASE_DIR, 'dist','PixelonServer',"PixelonServer.exe") # 빌드된 서버 파일명
ICON_PATH = os.path.join(BASE_DIR, "icon.ico") # 아이콘 파일 (없으면 기본값)

class PixelonTrayApp:
    def __init__(self):
        self.server_process = None
        self.log_window = None
        self.is_running = True
        
        # 서버 실행
        self.start_server()

        # 트레이 아이콘 설정
        self.setup_tray()

    def start_server(self):
        """서버 프로세스 시작"""
        if os.path.exists(SERVER_EXE):
            # 윈도우에서 콘솔 창 숨기기 위한 설정
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.server_process = subprocess.Popen(
                [SERVER_EXE],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                cwd=BASE_DIR
            )
            # 서버 감시 스레드 시작
            threading.Thread(target=self.monitor_server, daemon=True).start()
        else:
            # 서버 파일이 없으면 런처도 종료 (또는 에러 메시지)
            print("Server executable not found.")
            sys.exit(1)

    def monitor_server(self):
        """서버가 종료되면 런처도 종료"""
        while self.is_running:
            if self.server_process.poll() is not None:
                print("Server exited. Closing launcher...")
                self.quit_app()
                break
            time.sleep(1)

    def setup_tray(self):
        # 아이콘 로드 (파일 없으면 컬러 사각형으로 대체)
        if os.path.exists(ICON_PATH):
            image = Image.open(ICON_PATH)
        else:
            image = Image.new('RGB', (64, 64), color=(73, 109, 137))

        menu = (
            item('Open Web UI', self.open_web),
            item('View Logs', self.show_logs),
            item('Exit', self.quit_app)
        )

        self.icon = pystray.Icon("Pixelon", image, "Pixelon Server", menu)
        self.icon.run()

    def open_web(self):
        webbrowser.open("http://127.0.0.1:5000")

    def show_logs(self):
        """로그 확인용 GUI 창 띄우기 (CustomTkinter)"""
        if self.log_window is None or not self.log_window.winfo_exists():
            self.log_window = LogWindow(self.server_process)
        else:
            self.log_window.focus()

    def quit_app(self, icon=None, item=None):
        self.is_running = False
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate() # 서버 강제 종료
        
        if self.icon:
            self.icon.stop()
        sys.exit(0)

class LogWindow(ctk.CTkToplevel):
    def __init__(self, process):
        super().__init__()
        self.title("Pixelon Server Logs")
        self.geometry("600x400")
        
        self.textbox = ctk.CTkTextbox(self, width=580, height=380)
        self.textbox.pack(padx=10, pady=10)
        
        # 로그 읽기 스레드
        self.process = process
        self.reading = True
        threading.Thread(target=self.read_logs, daemon=True).start()

    def read_logs(self):
        # 이미 실행된 로그는 가져오기 어렵지만, 
        # Popen에서 stdout을 파이프로 연결했으므로 계속 읽을 수 있음
        while self.reading and self.process:
            line = self.process.stdout.readline()
            if line:
                self.textbox.insert("end", line)
                self.textbox.see("end")
            else:
                if self.process.poll() is not None:
                    break

if __name__ == "__main__":
    app = PixelonTrayApp()