import os
import sys
import subprocess
import threading
import time
import webbrowser
import customtkinter as ctk
from PIL import Image
import pystray
import queue
from pystray import MenuItem as item
import socket

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
SPLASH_IMAGE_PATH = os.path.join(RESOURCE_DIR, "start.png")

# -----------------------------------------------------------
# [Custom Widget] 로딩 스피너 (Canvas 이용)
# -----------------------------------------------------------
class LoadingSpinner(ctk.CTkCanvas):
    def __init__(self, master, size=30, color="black", bg_color=None, **kwargs):
        super().__init__(master, width=size, height=size, highlightthickness=0, bg=bg_color, **kwargs)
        self.size = size
        self.color = color
        self.angle = 0
        self.is_spinning = True
        self.arc = self.create_arc(2, 2, size-2, size-2, start=0, extent=100, 
                                   style="arc", outline=self.color, width=3)
        self.animate()

    def animate(self):
        if not self.is_spinning:
            return
        self.angle = (self.angle - 10) % 360
        self.itemconfigure(self.arc, start=self.angle)
        self.after(20, self.animate)

    def stop(self):
        self.is_spinning = False

# -----------------------------------------------------------
# [Window] 스플래시 스크린 (로딩 창)
# -----------------------------------------------------------
class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # 창 설정: 640x480 고정, 타이틀바 제거
        self.geometry("320x240")
        self.overrideredirect(True) 
        self.attributes('-topmost', True) # 항상 위에 표시
        
        # 화면 중앙 배치 계산
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 320) // 2
        y = (screen_height - 240) // 2
        self.geometry(f"320x240+{x}+{y}")

        # 배경 이미지 로드 및 설정
        try:
            pil_image = Image.open(SPLASH_IMAGE_PATH)
            # CTkImage로 변환 (고정 크기)
            self.bg_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(320, 240))
            self.bg_label = ctk.CTkLabel(self, text="", image=self.bg_image)
            self.bg_label.pack(fill="both", expand=True)
        except Exception as e:
            print(f"Error loading splash image: {e}")
            self.configure(fg_color="black") # 이미지 없으면 검은색 배경

        # 우측 하단 컨테이너 (Canvas 위에 위젯 배치가 까다로우므로 place 사용)
        # 위치: 우측 하단에서 약간 여백을 둠
        padding_x = 20
        padding_y = 20
        
        # 1. 로딩 서클 (우측 하단)
        self.spinner = LoadingSpinner(self, size=40, color="black", bg_color="white") 
        # 주의: bg_color는 이미지와 색이 맞지 않을 수 있으므로, 
        # 투명 처리가 완벽하지 않다면 이미지의 해당 부분 색상을 따르거나 레이아웃 조정 필요.
        # 여기서는 Spinner 자체 배경을 투명하게 하기 위해 CTkCanvas의 특성상 
        # 완벽한 투명은 어려우므로 '검정' 혹은 이미지의 주요 색상으로 설정 권장.
        # * start.png가 단색 배경이 아니라면 spinner 디자인을 바꿔야 할 수도 있음.
        #   여기서는 이미지가 로드된 라벨 위에 place로 얹습니다.
        
        self.spinner.place(relx=1.0, rely=1.0, x=-padding_x, y=-padding_y, anchor="se")

        # 2. 텍스트 라벨 (로딩 서클 왼쪽)
        self.status_label = ctk.CTkLabel(
            self, 
            text="starting server...", 
            font=("Arial", 14), 
            text_color="black",
            bg_color="transparent" # 배경 투명
        )
        self.status_label.place(relx=1.0, rely=1.0, x=-(padding_x + 50), y=-(padding_y + 8), anchor="e")

    def update_status(self, text):
        # 텍스트가 너무 길면 잘라서 표시
        if len(text) > 30:
            text = text[:27] + "..."
        self.status_label.configure(text=text)

    def close(self):
        self.spinner.stop()
        self.destroy()

class PixelOnTrayApp:
    def __init__(self):
        # [1] 중복 실행 방지 로직 (가장 먼저 실행)
        self.instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 로컬호스트의 특정 포트에 바인딩 시도
            self.instance_socket.bind(('127.0.0.1', LOCK_PORT))
        except socket.error:
            # 바인딩 실패 = 이미 다른 인스턴스가 실행 중
            print("PixelOn is already running.")
            self.open_web_direct() # 웹페이지만 띄움
            sys.exit(0)            # 현재 실행된 중복 프로세스 종료

        self.server_process = None
        self.log_window = None
        self.is_running = True
        self.log_queue = queue.Queue(10000)
        
        # Tkinter Root 생성
        self.root = ctk.CTk()
        self.root.withdraw() 

        # 스플래시 스크린 표시
        self.splash = SplashScreen(self.root)
        
        # 서버 실행
        self.start_server()

        # 트레이 아이콘 설정
        self.setup_tray()

    def run(self):
        """애플리케이션 실행 진입점"""
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.mainloop()

    def enqueue_output(self):
        """파이프가 막히지 않도록 계속 읽어서 큐에 담고, 특정 로그 감지 시 스플래시 종료"""
        # 서버 프로세스가 살아있는 동안 계속 읽기
        for line in iter(self.server_process.stdout.readline, ''):
            clean_line = line.strip()
            
            if clean_line:
                self.log_queue.put(clean_line)
                
                # 스플래시 스크린에 현재 진행 상황 텍스트 업데이트
                if self.splash and self.splash.winfo_exists():
                    self.root.after(0, lambda t=clean_line: self.splash.update_status(t))

                # 서버 준비 완료 메시지 감지
                if "CTRL+C" in line:
                    print("Server Ready Detected! Closing Splash.")
                    # 스레드 안전을 위해 메인 루프(after)를 통해 close 호출
                    self.root.after(0, self.close_splash)
        
        self.server_process.stdout.close()

    def close_splash(self):
        """스플래시 스크린을 닫고 리소스 정리"""
        if self.splash:
            if self.splash.winfo_exists():
                self.splash.close()
                # 창 띄우기
                self.open_web()
            self.splash = None
            # 메인 윈도우(root)는 계속 숨김 상태 유지 (트레이 앱이므로)

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
                bufsize=1,
                cwd=server_dir 
            )
            threading.Thread(target=self.monitor_server, daemon=True).start()
            threading.Thread(target=self.enqueue_output, daemon=True).start()
        else:
            print(f"Server executable not found at: {server_path}")
            # 개발용 더미 로그 (파일 없을 때 테스트용)
            if self.splash:
                self.splash.update_status(f"Err: No EXE at {server_path}")

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
            self.log_window = LogWindow(self.log_queue) 
        else:
            self.log_window.focus()

    def quit_app(self, icon=None, item=None):
        """안전한 종료 처리"""
        self.is_running = False
        
        if hasattr(self, 'icon') and self.icon:
            self.icon.stop()

        if self.server_process:
            if self.server_process.poll() is None:
                print("Terminating server process...")
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print("Server did not exit. Killing process...")
                    self.server_process.kill()
        
        self.root.quit()
        sys.exit(0)

class LogWindow(ctk.CTkToplevel):
    def __init__(self, log_queue):
        super().__init__()
        self.title("PixelOn Server Logs")
        self.geometry("600x400")
        
        # 텍스트 박스 설정
        self.textbox = ctk.CTkTextbox(self, width=580, height=380)
        self.textbox.pack(padx=10, pady=10)
        
        self.log_queue = log_queue
        
        # 창이 닫힐 때 이벤트 처리 (필수는 아니지만 명시적 처리)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 로그 업데이트 시작
        self.update_logs()

    def on_close(self):
        self.destroy()

    def update_logs(self):
        """주기적으로 큐에서 데이터를 꺼내 화면에 표시"""
        try:
            # 큐에 쌓인 데이터가 있다면 한 번에 처리 (최대 100줄씩 끊어서 UI 멈춤 방지)
            count = 0
            while not self.log_queue.empty() and count < 100:
                line = self.log_queue.get_nowait()
                self.textbox.insert("end", line)
                count += 1
            
            if count > 0:
                self.textbox.see("end") # 스크롤 자동 이동
        except queue.Empty:
            pass
        
        # 창이 존재하면 100ms 뒤에 다시 호출
        if self.winfo_exists():
            self.after(100, self.update_logs)

if __name__ == "__main__":
    def check_port_and_run(port=5000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind("127.0.0.1", port)
        except OSError as e:
            if e.errno == 98 or e.errno == 10048: # 98: Linux, 10048: Windows (Address already in use)
                # 포트가 이미 사용 중인 경우 브라우저 열기 후 종료
                webbrowser.open("http://127.0.0.1:5000")
                sys.exit(1)
            else:
                raise e
        # 바인딩 성공 시 소켓을 닫고 실제 서버 로직 실행 (혹은 이 소켓을 그대로 서버에 전달)
        sock.close()

    check_port_and_run()

    app = PixelOnTrayApp()
    app.run()