import requests
import uuid
import base64
import time
import threading
import os
import json

# 서버 주소 설정
SERVER_URL = "http://127.0.0.1:5000"

# 테스트용 출력 디렉토리
TEST_OUTPUT_DIR = "test_output"
if not os.path.exists(TEST_OUTPUT_DIR):
    os.makedirs(TEST_OUTPUT_DIR)

def generate_session_id():
    return str(uuid.uuid4())

def save_base64_image(b64_str, filename):
    """Base64 문자열을 이미지 파일로 저장"""
    file_path = os.path.join(TEST_OUTPUT_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(b64_str))
    print(f"[Client] Image saved to: {file_path}")

# ======================================================
# 시나리오 1: 스트리밍 이미지 생성 요청 (SSE)
# ======================================================
def test_streaming_generation():
    print("\n=== [Test 1] Streaming Image Generation ===")
    session_id = generate_session_id()
    count = 2 # 2장 생성 테스트
    
    # [Resize Test] 512에서 생성 후 256으로 리사이징 요청
    target_size = 256
    
    payload = {
        "session_id": session_id,
        "spec": {
            "p_prompt": "a beautiful landscape, mountains",
            "n_prompt": "blurry, low quality",
            "width": target_size,   # 리사이징 요청 (정사각형)
            "height": target_size,  # 리사이징 요청
            "count": count,
            "seed": -1, # 랜덤 시드
            #preset
        }
    }

    print(f"[Client] Sending Streaming Request (ID: {session_id}, Size: {target_size}x{target_size}, Count: {count})...")
    start_time = time.time()
    
    # [중요] stream=True 옵션 필수
    try:
        response = requests.post(f"{SERVER_URL}/api/generate", json=payload, stream=True)
        
        if response.status_code != 200:
            print(f"[Client] Error: Server returned {response.status_code}")
            return

        print("[Client] Connected to stream. Waiting for events...")

        # SSE 스트림 라인 단위로 읽기
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                
                # SSE 포맷은 "data: {json}" 형태임
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:].strip() # "data:" 제거
                    
                    try:
                        msg = json.loads(json_str)
                        msg_type = msg.get("type")

                        if msg_type == "image":
                            # 이미지 데이터 수신
                            idx = msg.get("current_index")
                            total = msg.get("total_count")
                            print(f"[Client] Received Image {idx}/{total}")
                            
                            filename = f"stream_{session_id}_{idx}.png"
                            save_base64_image(msg.get("image_base64"), filename)
                            
                        elif msg_type == "done":
                            # 완료 신호
                            status = msg.get("status")
                            print(f"[Client] Stream Finished. Status: {status}")
                            if status == "failed":
                                print(f"[Client] Failure Reason: {msg.get('error')}")
                            break # 루프 종료
                        
                        elif msg_type == "error":
                            print(f"[Client] Server Error: {msg.get('message')}")
                            break

                    except json.JSONDecodeError:
                        print(f"[Client] Failed to parse JSON: {json_str}")
                        
    except Exception as e:
        print(f"[Client] Connection Error: {e}")

    end_time = time.time()
    print(f"[Client] Test finished in {end_time - start_time:.2f} seconds.")


# ======================================================
# 시나리오 2 & 3: 상태 확인 및 중단 테스트
# ======================================================
def request_generation_thread(session_id):
    """별도 스레드에서 생성 요청을 보내는 함수 (중단 테스트용)"""
    payload = {
        "session_id": session_id,
        "spec": {
            "p_prompt": "complex detailed city, cyberpunk",
            "count": 5 # 중단할 시간을 벌기 위해 여러 장 요청
        }
    }
    print(f"[Client-Thread] Requesting generation for {session_id}...")
    try:
        # 여기도 stream=True로 연결만 해둠 (응답을 다 읽지는 않음)
        requests.post(f"{SERVER_URL}/api/generate", json=payload, stream=True)
    except Exception as e:
        print(f"[Client-Thread] Exception: {e}")

def test_status_and_stop():
    print("\n=== [Test 2 & 3] Status Check & Stop Generation ===")
    session_id = generate_session_id()

    # 1. 별도 스레드에서 생성 요청 시작
    t = threading.Thread(target=request_generation_thread, args=(session_id,))
    t.start()

    # 작업이 큐에 들어가고 실행될 시간을 잠시 줌
    time.sleep(2)

    # 2. 상태 확인 (Status API)
    print(f"[Client] Checking status for {session_id}...")
    status_resp = requests.get(f"{SERVER_URL}/api/status", params={"session_id": session_id})
    print(f"[Client] Status API Response: {status_resp.json()}")

    # 3. 작업 중단 (Stop API)
    print(f"[Client] Sending Stop request for {session_id}...")
    stop_payload = {"session_id": session_id}
    stop_resp = requests.post(f"{SERVER_URL}/api/stop", json=stop_payload)
    print(f"[Client] Stop API Response: {stop_resp.json()}")

    # 스레드 종료 대기
    t.join()

if __name__ == "__main__":
    # 서버가 켜져 있는지 확인
    try:
        requests.get(SERVER_URL)
    except requests.exceptions.ConnectionError:
        print("[Error] Server is not running. Please run 'app.py' first.")
        exit()

    # 테스트 실행
    # 1. 스트리밍 생성 테스트
    test_streaming_generation()
    
    # 2. 중단 테스트 (필요시 주석 해제)
    # test_status_and_stop()