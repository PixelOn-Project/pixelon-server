import os
import sys
import webbrowser
from threading import Timer
from flask import Flask, send_from_directory, jsonify, request

# ========================================================
# [Config] 서버 설정
# ========================================================
PORT = 5000
HOST = '127.0.0.1'
DEBUG_MODE = False  # 배포 시 False, 개발 중엔 True

# ========================================================
# [System] 경로 핸들링 함수 (PyInstaller 대응)
# ========================================================
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ========================================================
# [Init] Flask 앱 초기화
# ========================================================
# static 폴더의 절대 경로를 설정합니다.
static_root = resource_path('static')
editor_root = os.path.join(static_root, 'editor/prod')

app = Flask(__name__, static_folder=static_root)

print(f">> [SYSTEM] Server Root: {static_root}")
print(f">> [SYSTEM] Editor Root: {editor_root}")

# ========================================================
# [Router] 페이지 및 정적 파일 라우팅
# ========================================================

@app.route('/')
def index():
    """
    메인 페이지 접속 시 Piskel 에디터(index.html)를 반환
    """
    print(">> [REQUEST] Client connected to Editor")
    return send_from_directory(editor_root, 'index.html')

@app.route('/<path:filename>')
def serve_editor_assets(filename):
    """
    HTML에서 요청하는 JS, CSS, Image 파일들을 editor 폴더에서 찾아 반환
    예: /piskel-packaged.js -> static/editor/piskel-packaged.js
    """
    return send_from_directory(editor_root, filename)

# ========================================================
# [API] 추가 기능 (Python Backend Logic)
# ========================================================

@app.route('/api/status', methods=['GET'])
def system_check():
    """ 서버 상태 확인용 API """
    return jsonify({
        "status": "online",
        "service": "Pixelon Local Server",
        "version": "1.0.0"
    })

# TODO: 여기에 추후 '이미지 저장'이나 '파일 처리' 기능을 추가합니다.
@app.route('/api/save', methods=['POST'])
def save_project():
    # data = request.json
    # print(">> [DATA] Received save request")
    return jsonify({"result": "success", "message": "Not implemented yet"})


# ========================================================
# [Main] 서버 실행 진입점
# ========================================================

def open_browser():
    """ 서버 실행 후 1.5초 뒤에 브라우저 자동 실행 """
    url = f"http://{HOST}:{PORT}"
    print(f">> [ACTION] Launching Browser: {url}")
    webbrowser.open_new(url)

if __name__ == '__main__':
    print("==========================================")
    print(f"   PIXELON SERVER | Local Env")
    print("==========================================")

    # 배포 모드(EXE)일 때만 브라우저 자동 실행
    if not DEBUG_MODE:
        Timer(1.5, open_browser).start()

    app.run(host=HOST, port=PORT, debug=DEBUG_MODE)