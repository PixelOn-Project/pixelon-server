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
    # 1. 사용자 입력 받기 (Interactive Mode)
    print("==========================================")
    print("   Pixelon Server Binary Downloader")
    print("==========================================")
    print("Select target version to install:")
    print("   1. CUDA (NVIDIA GPU)")
    print("   2. Vulkan (AMD/Intel/NVIDIA GPU)")
    print("   3. CPU (No GPU / AVX2)")
    print("==========================================")
    
    choice = input(">> Enter choice (1-3 or name): ").strip().lower()
    
    if choice in ['1', 'cuda']:
        target_mode = 'cuda'
    elif choice in ['2', 'vulkan']:
        target_mode = 'vulkan'
    elif choice in ['3', 'cpu']:
        target_mode = 'cpu'
    else:
        print(f">> [WARN] Invalid input '{choice}'. Defaulting to 'cuda'.")
        target_mode = 'cuda'

    print(f">> [SYSTEM] Selected Target: {target_mode.upper()}")

    # 2. 다운로드할 대상 필터링
    keys_to_download = []
    if target_mode == "cuda":
        # CUDA 모드는 실행 파일(cuda)과 라이브러리(cuda_dll)가 모두 필요함
        keys_to_download = ["cuda", "cuda_dll"]
    elif target_mode in TARGETS:
        keys_to_download = [target_mode]
    
    # 3. 기존 bin 폴더 초기화 (부분 삭제 대신 폴더가 없으면 생성)
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)

    structure = []

    # 4. 다운로드 및 압축 해제 (선택된 타겟만)
    for ver, target in TARGETS.items():
        if ver not in keys_to_download:
            continue

        # [Check] 이미 설치되어 있는지 확인
        # bin 폴더 안에 sd.exe가 있으면 이미 설치된 것으로 간주
        sd_exe_path = os.path.join(DEST_DIR, "sd.exe")
        if os.path.exists(sd_exe_path):
            structure.append(f'{DEST_DIR} (Skipped)')
            continue

        url = BASE_URL + target
        
        # 하위 폴더(ver)가 아닌 bin 폴더(DEST_DIR)에 바로 압축 해제
        if download_and_extract(url, DEST_DIR):
            structure.append(f'{DEST_DIR} ({ver})')

    # 5. 모델 다운로드 (항상 수행)
    for model_name, model_url in MODELS.items():
        model_dest = os.path.join(MODEL_DIR)
        model_file_path = os.path.join(model_dest, model_name)

        # [Check] 모델 파일이 이미 있는지 확인
        if os.path.exists(model_file_path):
            structure.append(f'{model_file_path} (Skipped)')
            continue

        # download_file 함수 내부에서 makedirs 하므로 생략 가능하나 안전을 위해 유지
        if download_file(model_url, model_dest, model_name):
            structure.append(f'{model_dest}/{model_name}')

    print("\n>> [SYSTEM] Binary fetch complete.")
    print(f"   Structure: {', '.join(structure)}")

if __name__ == "__main__":
    main()