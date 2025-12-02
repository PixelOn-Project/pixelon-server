import os
import sys
import shutil
import subprocess
import threading
import time
import base64
import json
import uuid
import glob
import queue
import random
import webbrowser  # 브라우저 자동 실행용
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
from threading import Lock
from PIL import Image

# ========================================================
# [Config] 경로 및 설정
# ========================================================
# PyInstaller 실행 환경 고려
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BIN_DIR = os.path.join(BASE_DIR, 'bin')
MODEL_DIR = os.path.join(BASE_DIR, 'models')
RESULT_DIR = os.path.join(BASE_DIR, 'results')
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, 'sd_v-1-5.safetensors')

# [보안] 로컬 호스트만 허용
HOST = '127.0.0.1' 
PORT = 5000
SERVER_URL = f"http://{HOST}:{PORT}"

# 자동 종료 설정 (초 단위)
HEARTBEAT_TIMEOUT = 5  # 5초 동안 신호 없으면 종료
STARTUP_GRACE_PERIOD = 10 # 서버 시작 후 10초간은 종료 안 함

app = Flask(__name__, static_folder='static')
CORS(app) # CORS 허용 (로컬 파일 접근 문제 해결)

# ========================================================
# [System] 전역 상태 관리
# ========================================================
job_queue = []
queue_lock = Lock()

current_job = {
    "session_id": None,
    "process": None,
    "spec": None
}
current_job_lock = Lock()
result_queues = {} 

# [자동 종료] 마지막 하트비트 시간 기록
last_heartbeat_time = time.time()

# ========================================================
# [System] 하드웨어 가속 감지
# ========================================================
def detect_executable():
    # print(">> [INIT] Hardware Detection Started...")
    # cuda_path = os.path.join(BIN_DIR, 'cuda', 'sd.exe')
    # if os.path.exists(cuda_path):
    #     try:
    #         subprocess.check_output('nvidia-smi', shell=True)
    #         print(">> [INIT] NVIDIA GPU Detected. Selected: CUDA")
    #         return cuda_path
    #     except Exception:
    #         pass
    
    # vulkan_path = os.path.join(BIN_DIR, 'vulkan', 'sd.exe')
    # if os.path.exists(vulkan_path):
    #     print(">> [INIT] Selected: Vulkan (Fallback)")
    #     return vulkan_path

    # cpu_path = os.path.join(BIN_DIR, 'cpu', 'sd.exe')
    # print(">> [INIT] Selected: CPU (Fallback)")
    return os.path.join(BIN_DIR, 'sd.exe')

SD_EXE_PATH = detect_executable()

def clean_results_dir():
    if os.path.exists(RESULT_DIR):
        try:
            shutil.rmtree(RESULT_DIR)
        except Exception:
            pass
    os.makedirs(RESULT_DIR, exist_ok=True)

clean_results_dir()

# ========================================================
# [System] 자동 종료 모니터링 스레드
# ========================================================
def shutdown_monitor():
    """클라이언트 연결이 끊기면 서버를 종료하는 감시자"""
    print(">> [SYSTEM] Shutdown monitor started.")
    start_time = time.time()
    
    while True:
        time.sleep(1)
        
        # 시작 직후 유예 기간 (브라우저 켜지는 시간 고려)
        if time.time() - start_time < STARTUP_GRACE_PERIOD:
            continue

        # 마지막 신호로부터 타임아웃 지났는지 확인
        if time.time() - last_heartbeat_time > HEARTBEAT_TIMEOUT:
            print(">> [SYSTEM] No heartbeat detected. Shutting down server...")
            
            # 현재 작업 중인 프로세스가 있다면 정리
            with current_job_lock:
                if current_job['process']:
                    try:
                        current_job['process'].terminate()
                    except:
                        pass
            
            # Flask 서버 강제 종료
            os._exit(0)

# ========================================================
# [Worker] 백그라운드 작업 처리자
# ========================================================
def worker_loop():
    print(">> [SYSTEM] Worker thread started.")
    while True:
        job = None
        with queue_lock:
            if len(job_queue) > 0:
                job = job_queue.pop(0)
        
        if not job:
            time.sleep(0.1)
            continue

        session_id = job['session_id']
        spec = job['spec']
        
        if session_id not in result_queues:
            continue

        stream_q = result_queues[session_id]

        with current_job_lock:
            current_job['session_id'] = session_id
            current_job['spec'] = spec

        is_job_failed = False
        error_msg = ""
        
        try:
            count = int(spec.get('count', 1))
            if count < 1: count = 1
            if count > 10: count = 10 
        except:
            count = 1

        try:
            req_size = int(spec.get('width', 512))
            if req_size < 64: req_size = 64
        except:
            req_size = 512

        try:
            base_seed = int(spec.get('seed', -1))
        except:
            base_seed = -1

        print(f">> [WORKER] Generating {count} images for {session_id}")

        for i in range(count):
            if session_id not in result_queues:
                 is_job_failed = True
                 error_msg = "Cancelled by user"
                 break

            if base_seed == -1:
                current_seed = random.randint(0, 4294967295)
            else:
                current_seed = base_seed + i

            try:
                output_filename = f"{session_id}_{i}.png"
                output_path = os.path.join(RESULT_DIR, output_filename)
                
                prompt = spec.get('p_prompt', '')
                neg_prompt = spec.get('n_prompt', '')
                
                exe_path_rel = os.path.relpath(SD_EXE_PATH, BASE_DIR)
                model_path_rel = os.path.relpath(DEFAULT_MODEL_PATH, BASE_DIR)
                output_path_rel = os.path.relpath(output_path, BASE_DIR)

                cmd = [
                    exe_path_rel,
                    '-m', model_path_rel,
                    '-p', prompt,
                    '-n', neg_prompt,
                    '-W', "512",
                    '-H', "512",
                    '-s', str(current_seed),
                    '-o', output_path_rel,
                    '--threads', '8'
                ]

                startupinfo = None
                creationflags = 0
                if sys.platform == 'win32':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW

                process = subprocess.Popen(
                    cmd,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
                
                with current_job_lock:
                    current_job['process'] = process

                stdout, _ = process.communicate()

                if process.returncode == 0 and os.path.exists(output_path):
                    try:
                        with Image.open(output_path) as img:
                            if img.size != (req_size, req_size):
                                resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                                img_resized = img.resize((req_size, req_size), resample_filter)
                                img_resized.save(output_path)
                    except Exception as e:
                        print(f">> [WORKER] Resize Error: {e}")

                    with open(output_path, "rb") as image_file:
                        b64_string = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    payload = {
                        "type": "image",
                        "status": "generating",
                        "session_id": session_id,
                        "current_index": i + 1,
                        "total_count": count,
                        "image_base64": b64_string,
                        "generated_seed": current_seed,
                        "spec": spec
                    }
                    stream_q.put(payload)
                else:
                    is_job_failed = True
                    error_msg = "Process failed or was cancelled."
                    break 

            except Exception as e:
                is_job_failed = True
                error_msg = str(e)
                break

        final_payload = {
            "type": "done",
            "session_id": session_id,
            "status": "failed" if is_job_failed else "success",
            "error": error_msg if is_job_failed else None
        }
        stream_q.put(final_payload)

        with current_job_lock:
            current_job['session_id'] = None
            current_job['process'] = None
            current_job['spec'] = None
        
t = threading.Thread(target=worker_loop, daemon=True)
t.start()

# ========================================================
# [API] Heartbeat (생존 신고)
# ========================================================
@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """클라이언트가 1~2초마다 호출해야 함"""
    global last_heartbeat_time
    last_heartbeat_time = time.time() # 시간 갱신
    return jsonify({"status": "alive"})

# ========================================================
# [API] 기존 API 들
# ========================================================
@app.route('/api/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        session_id = data.get('session_id')
        spec = data.get('spec')

        if not session_id or not spec:
            return jsonify({"error": "Missing session_id or spec"}), 400

        msg_queue = queue.Queue()
        result_queues[session_id] = msg_queue

        with queue_lock:
            job_queue.append({"session_id": session_id, "spec": spec})

        def generate_stream():
            try:
                count = int(spec.get('count', 1))
                timeout_sec = 300 * count
                start_time = time.time()

                while True:
                    try:
                        msg = msg_queue.get(timeout=1.0)
                    except queue.Empty:
                        if time.time() - start_time > timeout_sec:
                            err_data = json.dumps({"type": "error", "message": "Timeout"})
                            yield f"data: {err_data}\n\n"
                            break
                        continue
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("type") == "done" or msg.get("status") == "cancelled":
                        break
            except GeneratorExit:
                pass
            finally:
                if session_id in result_queues:
                    del result_queues[session_id]

        return Response(stream_with_context(generate_stream()), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def check_status():
    target_id = request.args.get('session_id')
    with current_job_lock:
        if current_job['session_id'] == target_id:
            return jsonify({"status": "generating", "session_id": target_id})
    with queue_lock:
        for job in job_queue:
            if job['session_id'] == target_id:
                return jsonify({"status": "wait", "session_id": target_id})
    return jsonify({"status": "no", "session_id": target_id})

@app.route('/api/stop', methods=['POST'])
def stop_generation():
    data = request.json
    target_id = data.get('session_id')
    stopped_where = "none"

    with current_job_lock:
        if current_job['session_id'] == target_id:
            if current_job['process']:
                current_job['process'].terminate() 
                stopped_where = "generating"

    with queue_lock:
        initial_len = len(job_queue)
        job_queue[:] = [job for job in job_queue if job['session_id'] != target_id]
        if len(job_queue) < initial_len:
            stopped_where = "queue"

    if target_id in result_queues:
        cancel_msg = {"type": "done", "status": "cancelled", "session_id": target_id}
        result_queues[target_id].put(cancel_msg)

    if stopped_where == "none":
        return jsonify({"result": "fail"})
    else:
        return jsonify({"result": "success", "stopped_at": stopped_where})
    
@app.route('/')
def index():
    # 메인 페이지에서 바로 Piskel 에디터를 보여줄 경우
    return send_from_directory(os.path.join(app.static_folder, 'editor', 'prod'), 'index.html')

@app.route('/tutorial')
def tutorial ():
    # 메인 페이지에서 바로 Piskel 에디터를 보여줄 경우
    return send_from_directory(os.path.join(app.static_folder, 'tutorial'), 'tutorial.html')

# Piskel 내부에서 로딩하는 js, css, 이미지 등을 위한 경로 처리
@app.route('/<path:filename>')
def serve_editor_files(filename):
    return send_from_directory(os.path.join(app.static_folder, 'editor', 'prod'), filename)


# ========================================================
# [Main] 실행 진입점
# ========================================================
def open_browser():
    """서버 실행 후 브라우저 자동 실행"""
    print(">> [SYSTEM] Opening default browser...")
    webbrowser.open_new(SERVER_URL) # 로컬호스트 주소 열기

if __name__ == '__main__':
    print(f">> [SYSTEM] Server starting on {SERVER_URL}")
    print(f">> [SYSTEM] Localhost ONLY mode activated.")
    
    # 1. 자동 종료 모니터 스레드 시작
    monitor_thread = threading.Thread(target=shutdown_monitor, daemon=True)
    monitor_thread.start() 

    # 2. 브라우저 자동 실행 (1.5초 지연)
    threading.Timer(1.5, open_browser).start()

    # 3. 서버 시작 (host='127.0.0.1'로 로컬만 허용)
    app.run(host=HOST, port=PORT, threaded=True)