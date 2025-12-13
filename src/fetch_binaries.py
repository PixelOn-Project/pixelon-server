import os
import requests
import zipfile
import io
import shutil

# ========================================================
# [Config] 다운로드 설정 (installer.py와 동기화됨)
# ========================================================
MAJOR_VER = "master-377"
MINOR_VER = "2034588"

# 엔진 다운로드 링크 (installer.py의 ENGINE_URLS 참고)
TARGETS = {
    "cuda": f"https://github.com/PixelOn-Project/pixelon-server/releases/download/v0.0/sd_core.zip",
    "vulkan": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-vulkan-x64.zip",
    "cpu_avx512": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx512-x64.zip",
    "cpu_avx2": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx2-x64.zip",
    "cpu_avx": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-avx-x64.zip",
    "cpu_noavx": f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{MAJOR_VER}-{MINOR_VER}/sd-master-{MINOR_VER}-bin-win-noavx-x64.zip",
}

DEST_DIR = "bin"
MODEL_DIR = "models"

# 모델 다운로드 링크 (installer.py의 FILE_REGISTRY 참고)
MODELS = {
    "cetusMix.safetensors": "https://civitai.com/api/download/models/105924?type=Model&format=SafeTensor&size=pruned&fp=fp16", 
    "QteaMix.safetensors": "https://civitai.com/api/download/models/94654?type=Model&format=SafeTensor&size=pruned&fp=fp16",
    "PX64NOCAP.safetensors": "https://drive.google.com/uc?export=download&id=1UZYLjoX2NHkL6w5-NJl9kUIoRdD2I11Y",
    "PixelWorld.safetensors": "https://drive.google.com/uc?export=download&id=1q_zrFaUBmAHuHT2Sg-0sAQeyfrmY2Bg_",
    "PixelArtRedmond15V.safetensors": "https://huggingface.co/artificialguybr/pixelartredmond-1-5v-pixel-art-loras-for-sd-1-5/resolve/main/PixelArtRedmond15V-PixelArt-PIXARFK.safetensors?download=true"
}


def download_and_extract(url, extract_to):
    print(f">> [DOWNLOAD] Fetching {url}...")
    try:
        # [Google Drive Support added for consistency]
        session = requests.Session()
        response = session.get(url, stream=True)
        
        if "drive.google.com" in url:
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_token = value
                    break
            if not confirm_token:
                for key, value in session.cookies.items():
                    if key.startswith('download_warning'):
                        confirm_token = value
                        break
            if confirm_token:
                separator = "&" if "?" in url else "?"
                confirm_url = f"{url}{separator}confirm={confirm_token}"
                response = session.get(confirm_url, stream=True)

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
    
    save_to = os.path.join(dest, name)
    print(f">> [INFO] Target Path: {save_to}")

    if dest:
        os.makedirs(dest, exist_ok=True)

    try:
        session = requests.Session()
        response = session.get(url, stream=True)
        
        # [FIX] Google Drive Warning Bypass (installer.py와 동일 로직)
        if "drive.google.com" in url:
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_token = value
                    break
            if not confirm_token:
                for key, value in session.cookies.items():
                    if key.startswith('download_warning'):
                        confirm_token = value
                        break
            if confirm_token:
                separator = "&" if "?" in url else "?"
                confirm_url = f"{url}{separator}confirm={confirm_token}"
                response = session.get(confirm_url, stream=True)

        if response.status_code == 200:
            with open(save_to, 'wb') as f:
                # Chunk size increased to 1MB for better performance
                for chunk in response.iter_content(chunk_size=1024 * 1024):
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
    print("   3. CPU AVX2 (Standard CPU)")
    print("   4. CPU AVX512 (High Performance CPU)")
    print("   5. CPU AVX (Older CPU)")
    print("   6. CPU No-AVX (Legacy CPU)")
    print("==========================================")
    
    choice = input(">> Enter choice (1-6 or name): ").strip().lower()
    
    target_mode = None
    
    if choice in ['1', 'cuda']: target_mode = 'cuda'
    elif choice in ['2', 'vulkan']: target_mode = 'vulkan'
    elif choice in ['3', 'cpu', 'avx2']: target_mode = 'cpu_avx2'
    elif choice in ['4', 'avx512']: target_mode = 'cpu_avx512'
    elif choice in ['5', 'avx']: target_mode = 'cpu_avx'
    elif choice in ['6', 'noavx']: target_mode = 'cpu_noavx'
    else:
        print(f">> [WARN] Invalid input '{choice}'. Defaulting to 'cuda'.")
        target_mode = 'cuda'

    print(f">> [SYSTEM] Selected Target: {target_mode.upper()}")

    # 2. 기존 bin 폴더 초기화
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)

    structure = []

    # 3. 엔진 다운로드 및 압축 해제
    if target_mode in TARGETS:
        url = TARGETS[target_mode]
        
        # [Check] 이미 설치되어 있는지 확인
        sd_exe_path = os.path.join(DEST_DIR, "sd.exe")
        do_download = True
        if os.path.exists(sd_exe_path):
            skip = input(f">> [CHECK] 'sd.exe' already exists in '{DEST_DIR}'. Skip downloading engine? (Y/n): ").strip().lower()
            if skip not in ['n', 'no']:
                print(f">> [SKIP] Skipping download for {target_mode}...")
                structure.append(f'{DEST_DIR} (Skipped)')
                do_download = False

        if do_download:
            # bin 폴더(DEST_DIR)에 바로 압축 해제
            if download_and_extract(url, DEST_DIR):
                structure.append(f'{DEST_DIR} ({target_mode})')
    else:
        print(f">> [ERROR] Target mode '{target_mode}' not defined in TARGETS.")

    # 4. 모델 다운로드 (항상 수행)
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)

    print("\n>> [MODELS] Checking models...")
    for model_name, model_url in MODELS.items():
        model_dest = MODEL_DIR
        model_file_path = os.path.join(model_dest, model_name)

        # [Check] 모델 파일이 이미 있는지 확인
        if os.path.exists(model_file_path):
            skip = input(f">> [CHECK] Model '{model_name}' already exists. Skip download? (Y/n): ").strip().lower()
            if skip not in ['n', 'no']:
                print(f">> [SKIP] Skipping model {model_name}...")
                structure.append(f'{model_file_path} (Skipped)')
                continue

        if download_file(model_url, model_dest, model_name):
            structure.append(f'{model_dest}/{model_name}')

    print("\n>> [SYSTEM] Binary fetch complete.")
    print(f"   Structure: {', '.join(structure)}")

if __name__ == "__main__":
    main()