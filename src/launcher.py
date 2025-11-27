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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PyInstaller로 빌드된 상태인지 자동 감지
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # [배포 모드] 현재 실행 파일(Launcher.exe)과 같은 폴더에 Server.exe가 있음
    EXEC_DIR = os.path.dirname(sys.executable)
    SERVER_EXE = os.path.join(EXEC_DIR, "PixelOnServer.exe")
else:
    # [개발 모드] PixelOn Client 폴더의 상위에 dist가 있다고 가정
    SERVER_EXE = os.path.join(BASE_DIR, '..', 'dist', 'PixelOnServer', 'PixelOnServer.exe')

# 아이콘 경로 설정
ICON_PATH = os.path.join(BASE_DIR, "icon.ico") 

class PixelOnTrayApp:
    def __init__(self):
        self.server_process = None
        self.log_window = None
        self.is_running = True
        
        # [Fix] Tkinter Root 생성 (Main Loop 관리용, 숨김 상태)
        self.root = ctk.CTk()
        self.root.withdraw()

        # 서버 실행
        self.start_server()

        # 트레이 아이콘 설정 (실행은 run()에서)
        self.setup_tray()

    def run(self):
        """애플리케이션 실행 진입점"""
        # [Fix] Tray Icon을 별도 스레드에서 실행하여 Tkinter Mainloop 차단 방지
        threading.Thread(target=self.icon.run, daemon=True).start()
        
        # [Fix] 메인 스레드에서는 Tkinter Loop 실행
        self.root.mainloop()

    def start_server(self):
        """서버 프로세스 시작"""
        # 경로 정규화
        server_path = os.path.normpath(SERVER_EXE)
        
        if os.path.exists(server_path):
            # 윈도우에서 콘솔 창 숨기기 위한 설정
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
            # 서버 감시 스레드 시작
            threading.Thread(target=self.monitor_server, daemon=True).start()
        else:
            print(f"Server executable not found at: {server_path}")
            sys.exit(1)

    def monitor_server(self):
        """서버가 종료되면 런처도 종료"""
        while self.is_running:
            if self.server_process and self.server_process.poll() is not None:
                print("Server exited. Closing launcher...")
                # 메인 스레드에서 종료 처리
                self.root.after(0, self.quit_app)
                break
            time.sleep(1)

    def setup_tray(self):
        if os.path.exists(ICON_PATH):
            image = Image.open(ICON_PATH)
        else:
            image = Image.new('RGB', (64, 64), color=(73, 109, 137))

        menu = (
            item('Open Web UI', self.open_web),
            item('View Logs', self.show_logs),
            item('Exit', self.quit_app)
        )

        self.icon = pystray.Icon("PixelOn", image, "PixelOn Server", menu)

    def open_web(self):
        webbrowser.open("http://127.0.0.1:5000")

    def show_logs(self):
        """로그 확인용 GUI 창 띄우기 (Main Thread 위임)"""
        # [Fix] Tray 스레드에서 호출되므로 메인 스레드로 작업 위임
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
        
        # [Fix] Tkinter 종료 및 프로세스 종료
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
        
        # [Fix] 창 닫기 이벤트 핸들러 등록
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        threading.Thread(target=self.read_logs, daemon=True).start()

    def on_close(self):
        """창이 닫힐 때 플래그 해제 및 안전한 종료"""
        self.reading = False
        self.destroy()

    def read_logs(self):
        while self.reading and self.process:
            try:
                # 블로킹 읽기
                line = self.process.stdout.readline()
                if line:
                    if self.reading: # 닫힌 상태면 요청하지 않음
                        self.after(0, self.append_log, line)
                else:
                    if self.process.poll() is not None:
                        break
            except Exception:
                break
    
    def append_log(self, text):
        """메인 스레드에서 실행될 UI 업데이트 함수"""
        # [Fix] 위젯이 이미 파괴되었을 수 있으므로 try-except 처리
        try:
            self.textbox.insert("end", text)
            self.textbox.see("end")
        except Exception:
            pass

if __name__ == "__main__":
    app = PixelOnTrayApp()
    app.run()