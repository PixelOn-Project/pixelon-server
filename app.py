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
import random  # 난수 생성을 위한 random 모듈
from flask import Flask, request, jsonify, Response, stream_with_context
from threading import Lock
from PIL import Image  # 이미지 리사이징을 위해 Pillow 라이브러리
from flask_cors import CORS
from flask import Flask, send_from_directory

# ========================================================
# [Config] 경로 및 설정
# ========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, 'bin')
MODEL_DIR = os.path.join(BASE_DIR, 'models')
RESULT_DIR = os.path.join(BASE_DIR, 'results')
# 임시 고정 모델 (추후 preset에 따라 변경 가능)
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, 'sd_v-1-5.safetensors')

app = Flask(__name__, static_folder='static')
CORS(app)

# ========================================================
# [System] 전역 상태 관리 (In-Memory)
# ========================================================
# 작업 큐: 대기 중인 요청들을 담습니다.
job_queue = []
queue_lock = Lock()

# 현재 실행 중인 작업 정보
current_job = {
    "session_id": None,
    "process": None, # subprocess 객체 (kill용)
    "spec": None
}
current_job_lock = Lock()

# 결과 전달을 위한 스트리밍 큐 맵 (SessionID -> Queue)
result_queues = {} 

# ========================================================
# [System] 하드웨어 가속 감지 및 초기화
# ========================================================
def detect_executable():
    """
    우선순위: CUDA > Vulkan > CPU
    시스템 환경을 확인하여 최적의 sd.exe 경로를 반환합니다.
    """
    print(">> [INIT] Hardware Detection Started...")
    
    # 1. CUDA 확인 (nvidia-smi 호출 시도)
    cuda_path = os.path.join(BIN_DIR, 'cuda', 'sd.exe')
    if os.path.exists(cuda_path):
        try:
            subprocess.check_output('nvidia-smi', shell=True)
            print(">> [INIT] NVIDIA GPU Detected. Selected: CUDA")
            return cuda_path
        except Exception:
            print(">> [INIT] CUDA binary exists but nvidia-smi failed.")
    
    # 2. Vulkan 확인 (폴더 존재 여부로 판단)
    vulkan_path = os.path.join(BIN_DIR, 'vulkan', 'sd.exe')
    if os.path.exists(vulkan_path):
        print(">> [INIT] Selected: Vulkan (Fallback)")
        return vulkan_path

    # 3. CPU (최후의 수단)
    cpu_path = os.path.join(BIN_DIR, 'cpu', 'sd.exe')
    print(">> [INIT] Selected: CPU (Fallback)")
    return cpu_path

# 실행할 바이너리 경로 결정
SD_EXE_PATH = detect_executable()

def clean_results_dir():
    """서버 시작 시 결과 임시 폴더 초기화"""
    if os.path.exists(RESULT_DIR):
        try:
            shutil.rmtree(RESULT_DIR)
            print(">> [INIT] Cleaned 'results' directory.")
        except Exception as e:
            print(f">> [WARN] Failed to clean results: {e}")
    os.makedirs(RESULT_DIR, exist_ok=True)

# 초기화 실행
clean_results_dir()

# ========================================================
# [Worker] 백그라운드 작업 처리자
# ========================================================
def worker_loop():
    """
    큐를 계속 감시하며 순차적으로 이미지를 생성하는 백그라운드 스레드
    """
    print(">> [SYSTEM] Worker thread started.")
    while True:
        job = None
        
        # 1. 큐에서 작업 꺼내기
        with queue_lock:
            if len(job_queue) > 0:
                job = job_queue.pop(0) # FIFO
        
        if not job:
            time.sleep(0.1) # 대기
            continue

        session_id = job['session_id']
        spec = job['spec']
        
        # 이미 취소된 요청인지 확인 (큐가 없으면 취소된 것)
        if session_id not in result_queues:
            print(f">> [WORKER] Job {session_id} was cancelled before start.")
            continue

        print(f">> [WORKER] Starting Job: {session_id}")
        
        # 스트리밍 큐 가져오기
        stream_q = result_queues[session_id]

        # 2. 현재 작업으로 등록 (취소 기능을 위해)
        with current_job_lock:
            current_job['session_id'] = session_id
            current_job['spec'] = spec

        # 3. 반복 생성 (Count 처리)
        is_job_failed = False
        error_msg = ""
        
        # count 값 읽기
        try:
            count = int(spec.get('count', 1))
            if count < 1: count = 1
            if count > 10: count = 10 
        except:
            count = 1

        # [RESIZE] 사용자 요청 크기 파악 (정사각형 고정)
        try:
            req_size = int(spec.get('width', 512))
            if req_size < 64: req_size = 64 # 최소 크기 안전장치
        except:
            req_size = 512

        # [SEED] 기본 시드 값 파악
        # 사용자가 -1을 보내거나 값을 안 보내면 랜덤으로 간주
        try:
            base_seed = int(spec.get('seed', -1))
        except:
            base_seed = -1

        print(f">> [WORKER] Generating {count} images (Gen: 512x512 -> Resize: {req_size}x{req_size}) for {session_id}")

        for i in range(count):
            # 중간에 취소되었는지 확인 (큐가 삭제되었으면 취소된 것)
            if session_id not in result_queues:
                 print(f">> [WORKER] Job {session_id} cancelled during loop.")
                 is_job_failed = True
                 error_msg = "Cancelled by user"
                 break

            # [SEED] 현재 루프의 시드 결정
            # -1이면 Python에서 랜덤 생성하여 sd.exe에 고정값으로 전달 (기록을 위해)
            # 고정값이면 i만큼 증가시켜 다양성 확보
            if base_seed == -1:
                # 32비트 정수 범위 내 랜덤
                current_seed = random.randint(0, 4294967295)
            else:
                current_seed = base_seed + i

            try:
                # 파일명 구분: {session_id}_0.png
                output_filename = f"{session_id}_{i}.png"
                output_path = os.path.join(RESULT_DIR, output_filename)
                
                # 파라미터 매핑
                prompt = spec.get('p_prompt', '')
                neg_prompt = spec.get('n_prompt', '')
                
                # [FIXED] 생성은 무조건 512x512로 고정
                gen_width = "512"
                gen_height = "512"
                
                # 상대 경로 변환
                exe_path_rel = os.path.relpath(SD_EXE_PATH)
                model_path_rel = os.path.relpath(DEFAULT_MODEL_PATH)
                output_path_rel = os.path.relpath(output_path)

                cmd = [
                    exe_path_rel,
                    '-m', model_path_rel,
                    '-p', prompt,
                    '-n', neg_prompt,
                    '-W', gen_width,  # 고정된 생성 크기
                    '-H', gen_height, # 고정된 생성 크기
                    '-s', str(current_seed), # [SEED] 결정된 시드 값 전달
                    '-o', output_path_rel,
                    '--threads', '8'
                ]

                # 프로세스 시작
                process = subprocess.Popen(
                    cmd,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                with current_job_lock:
                    current_job['process'] = process

                # 종료 대기
                stdout, _ = process.communicate()

                # 결과 처리
                if process.returncode == 0 and os.path.exists(output_path):
                    
                    # [RESIZE] 생성된 이미지를 사용자 요청 크기로 리사이징
                    try:
                        with Image.open(output_path) as img:
                            # 요청한 크기와 다를 경우 리사이징 수행
                            if img.size != (req_size, req_size):
                                resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
                                img_resized = img.resize((req_size, req_size), resample_filter)
                                img_resized.save(output_path)
                                print(f">> [WORKER] Resized image to {req_size}x{req_size}")
                    except Exception as e:
                        print(f">> [WORKER] Resize Error: {e}")

                    # 이미지 인코딩
                    with open(output_path, "rb") as image_file:
                        b64_string = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    # 큐에 전송 (generated_seed 포함)
                    payload = {
                        "type": "image",
                        "status": "generating",
                        "session_id": session_id,
                        "current_index": i + 1,
                        "total_count": count,
                        "image_base64": b64_string,
                        "generated_seed": current_seed, # [SEED] 실제 사용된 시드 반환
                        "spec": spec
                    }
                    stream_q.put(payload)
                    print(f">> [WORKER] Sent image {i+1}/{count} for {session_id} (Seed: {current_seed})")
                else:
                    is_job_failed = True
                    error_msg = "Process failed or was cancelled."
                    print(f">> [WORKER] Job {session_id} failed at index {i}.")
                    break 

            except Exception as e:
                is_job_failed = True
                error_msg = str(e)
                print(f">> [WORKER] Error in job {session_id}: {e}")
                break

        # 4. 최종 종료 신호 전송
        final_payload = {
            "type": "done",
            "session_id": session_id,
            "status": "failed" if is_job_failed else "success",
            "error": error_msg if is_job_failed else None
        }
        stream_q.put(final_payload)

        # 5. 작업 완료 후 정리
        with current_job_lock:
            current_job['session_id'] = None
            current_job['process'] = None
            current_job['spec'] = None
        
        # 큐 맵에서 삭제는 API 스레드가 수행

# 워커 스레드 시작
t = threading.Thread(target=worker_loop, daemon=True)
t.start()


# ========================================================
# [API] 1. 이미지 생성 (Streaming Response)
# ========================================================
@app.route('/api/generate', methods=['POST'])
def generate_image():
    """
    SSE(Server-Sent Events) 방식을 사용하여
    이미지가 생성될 때마다 즉시 데이터를 클라이언트로 전송합니다.
    """
    try:
        data = request.json
        session_id = data.get('session_id')
        spec = data.get('spec')

        if not session_id or not spec:
            return jsonify({"error": "Missing session_id or spec"}), 400

        print(f">> [API] Received Streaming Request: {session_id} (Count: {spec.get('count', 1)})")

        # 1. 스트리밍을 위한 전용 큐 생성
        msg_queue = queue.Queue()
        result_queues[session_id] = msg_queue

        # 2. 작업 큐에 추가
        with queue_lock:
            job_queue.append({
                "session_id": session_id,
                "spec": spec
            })

        # 3. 제너레이터 함수 정의
        def generate_stream():
            try:
                # 타임아웃 계산 (장당 5분)
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
                print(f">> [API] Client disconnected: {session_id}")
                pass
            finally:
                if session_id in result_queues:
                    del result_queues[session_id]

        # 4. 스트리밍 응답 반환
        return Response(stream_with_context(generate_stream()), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========================================================
# [API] 2. 이미지 생성 현황 확인
# ========================================================
@app.route('/api/status', methods=['GET'])
def check_status():
    target_id = request.args.get('session_id')
    
    if not target_id:
        return jsonify({"status": "no", "message": "No session_id provided"}), 400

    # 1. 현재 생성 중인지 확인
    with current_job_lock:
        if current_job['session_id'] == target_id:
            return jsonify({"status": "generating", "session_id": target_id})

    # 2. 대기 큐에 있는지 확인
    with queue_lock:
        for job in job_queue:
            if job['session_id'] == target_id:
                return jsonify({"status": "wait", "session_id": target_id})

    # 3. 아무것도 아님
    return jsonify({"status": "no", "session_id": target_id})


# ========================================================
# [API] 3. 이미지 생성 중단
# ========================================================
@app.route('/api/stop', methods=['POST'])
def stop_generation():
    data = request.json
    target_id = data.get('session_id')

    if not target_id:
        return jsonify({"error": "Missing session_id"}), 400

    print(f">> [API] Stop Request for: {target_id}")
    stopped_where = "none"

    # 1. 현재 실행 중인 작업이라면 Kill
    with current_job_lock:
        if current_job['session_id'] == target_id:
            if current_job['process']:
                print(f">> [API] Killing active process for {target_id}...")
                current_job['process'].terminate() 
                stopped_where = "generating"

    # 2. 대기 큐에 있다면 제거
    with queue_lock:
        initial_len = len(job_queue)
        job_queue[:] = [job for job in job_queue if job['session_id'] != target_id]
        if len(job_queue) < initial_len:
            stopped_where = "queue"
            print(f">> [API] Removed {target_id} from queue.")

    # 3. 스트리밍 중이던 연결에 종료 신호 보내기
    if target_id in result_queues:
        cancel_msg = {
            "type": "done",
            "status": "cancelled", 
            "session_id": target_id,
            "message": "User requested stop."
        }
        result_queues[target_id].put(cancel_msg)

    if stopped_where == "none":
        return jsonify({"result": "fail", "message": "Session ID not found in queue or active jobs."})
    else:
        return jsonify({"result": "success", "stopped_at": stopped_where})

@app.route('/')
def index():
    # 메인 페이지에서 바로 Piskel 에디터를 보여줄 경우
    return send_from_directory(os.path.join(app.static_folder, 'editor', 'prod'), 'index.html')

# Piskel 내부에서 로딩하는 js, css, 이미지 등을 위한 경로 처리
@app.route('/<path:filename>')
def serve_editor_files(filename):
    return send_from_directory(os.path.join(app.static_folder, 'editor', 'prod'), filename)


if __name__ == '__main__':
    print(f">> [SYSTEM] Server ready. Using: {os.path.basename(SD_EXE_PATH)}")
    app.run(host='0.0.0.0', port=5000, threaded=True)