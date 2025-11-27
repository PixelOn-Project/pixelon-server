import os
import requests
import zipfile
import io
import shutil

# ========================================================
# [Config] 다운로드 설정
# ========================================================
VERSION_TAG = "master-377-2034588" 
VERSION = "2034588"

TARGETS = {
    "cpu": f"sd-master-{VERSION}-bin-win-avx-x64.zip",
    "cuda": f"sd-master-{VERSION}-bin-win-cuda12-x64.zip",
    "cuda_dll": f"cudart-sd-bin-win-cu12-x64.zip",
    "vulkan": f"sd-master-{VERSION}-bin-win-vulkan-x64.zip"
}
BASE_URL = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{VERSION_TAG}/"
DEST_DIR = "bin"
MODEL_DIR = "models"

MODELS = {
    "sd_v-1-5.safetensors": "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors",
}

def download_and_extract(url, extract_to):
    print(f">> [DOWNLOAD] Fetching {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(extract_to)
            print(f">> [OK] Extracted to {extract_to}")
            return 1
        else:
            print(f">> [ERROR] Failed to download. Status: {response.status_code}")
            return 0
    except Exception as e:
        print(f">> [ERROR] Exception occurred: {e}")
        return 0

def download_file(url, dest, name):
    """
    url: 다운로드할 파일의 URL
    dest: 저장할 폴더 경로 (예: 'bin/models')
    name: 저장할 파일 이름 (예: 'sd_v1-5.safetensors')
    """
    print(f">> [DOWNLOAD] Fetching {url}...")
    
    # 1. 전체 저장 경로 생성 (폴더 + 파일명)
    save_to = os.path.join(dest, name)
    print(f">> [INFO] Target Path: {save_to}")

    # 2. 저장할 폴더가 없으면 생성
    if dest:
        os.makedirs(dest, exist_ok=True)

    try:
        # 3. 요청 보내기 (stream=True: 대용량 파일 메모리 최적화)
        with requests.get(url, stream=True) as response:
            if response.status_code == 200:
                # 4. 파일 저장 (wb: Write Binary 모드)
                with open(save_to, 'wb') as f:
                    # 8KB씩 조각내어 파일에 쓰기
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f">> [OK] Download complete: {save_to}")
                return 1
            else:
                print(f">> [ERROR] Failed to download. Status: {response.status_code}")
                return 0
                
    except Exception as e:
        print(f">> [ERROR] Exception occurred: {e}")
        return 0

def main():
    structure = []

    # ========================================================
    # 1. 바이너리 (bin 폴더) 체크 및 다운로드
    # ========================================================
    # 폴더가 없거나(False), 있어도 내용물이 비어있으면(not listdir) 다운로드 진행
    if not os.path.exists(DEST_DIR) or not os.listdir(DEST_DIR):
        print(f">> [SYSTEM] '{DEST_DIR}' is empty or missing. Starting download...")

        # 기존 bin 폴더가 있다면(비어있지만) 안전하게 초기화 후 재생성
        if os.path.exists(DEST_DIR):
            shutil.rmtree(DEST_DIR)
        os.makedirs(DEST_DIR)

        # 다운로드 및 압축 해제
        for ver, target in TARGETS.items():
            url = BASE_URL + target
            # 다운로드 경로: bin/cpu, bin/cuda, bin/cuda_dll 등
            if download_and_extract(url, os.path.join(DEST_DIR, ver)):
                structure.append(f'{DEST_DIR}/{ver}')

        # cuda_dll -> cuda 병합 및 정리
        cuda_path = os.path.join(DEST_DIR, "cuda")
        dll_path = os.path.join(DEST_DIR, "cuda_dll")

        # 두 폴더가 모두 존재할 때만 병합 진행
        if os.path.exists(cuda_path) and os.path.exists(dll_path):
            print(f"\n>> [MERGE] Moving files from '{dll_path}' to '{cuda_path}'...")
            
            items = os.listdir(dll_path)
            for item in items:
                src = os.path.join(dll_path, item)
                dst = os.path.join(cuda_path, item)

                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
            shutil.rmtree(dll_path)
            print(f">> [MERGE] Cleanup '{dll_path}' complete.")

            # 최종 출력 리스트에서 cuda_dll 제거
            structure = [s for s in structure if "cuda_dll" not in s]
    else:
        print(f">> [SKIP] '{DEST_DIR}' folder already exists and is not empty.")
        # 이미 존재하므로 현재 구조를 읽어서 리스트에 추가 (출력용)
        for item in os.listdir(DEST_DIR):
             if os.path.isdir(os.path.join(DEST_DIR, item)):
                 structure.append(f'{DEST_DIR}/{item}')

    # ========================================================
    # 2. 모델 (models 폴더) 체크 및 다운로드
    # ========================================================
    # 폴더가 없거나, 있어도 내용물이 비어있으면 다운로드 진행
    if not os.path.exists(MODEL_DIR) or not os.listdir(MODEL_DIR):
        print(f"\n>> [SYSTEM] '{MODEL_DIR}' is empty or missing. Starting download...")
        
        for model_name, model_url in MODELS.items():
            model_dest = os.path.join(MODEL_DIR)
            os.makedirs(model_dest, exist_ok=True)
            if download_file(model_url, model_dest, model_name):
                structure.append(f'{model_dest}/{model_name}')
    else:
        print(f">> [SKIP] '{MODEL_DIR}' folder already exists and is not empty.")
        for item in os.listdir(MODEL_DIR):
            structure.append(f'{MODEL_DIR}/{item}')

    print("\n>> [SYSTEM] Process complete.")
    print(f"   Structure: {', '.join(structure)}")

if __name__ == "__main__":
    main()