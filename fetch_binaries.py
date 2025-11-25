import os
import requests
import zipfile
import io
import shutil

# ========================================================
# [Config] 다운로드 설정
# ========================================================
# 사용하려는 stable-diffusion.cpp 버전 (최신 릴리즈 태그 확인 필요)
VERSION_TAG = "master-377-2034588" # 예시 태그, 실제 최신 태그로 교체 필요
VERSION = "2034588"

# CUDA 버전 (일반적으로 avx2와 cuda12 버전을 많이 씀)
# 예: win-avx2 (CPU용), win-cuda12 (NVIDIA용)
TARGETS = {
    "cpu": f"sd-master-{VERSION}-bin-win-avx-x64.zip",
    "cuda": f"sd-master-{VERSION}-bin-win-cuda12-x64.zip",
    "vulkan": f"sd-master-{VERSION}-bin-win-vulkan-x64.zip"
}
BASE_URL = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{VERSION_TAG}/"

DEST_DIR = "bin"
def download_and_extract(url, extract_to):
    print(f">> [DOWNLOAD] Fetching {url}...")
    response = requests.get(url)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(extract_to)
        print(f">> [OK] Extracted to {extract_to}")
        return 1
    else:
        print(f">> [ERROR] Failed to download. Status: {response.status_code}")
        return 0

def main():
    if os.path.exists(DEST_DIR):
        shutil.rmtree(DEST_DIR)
    os.makedirs(DEST_DIR)

    structure = []

    for ver, target in TARGETS.items():
        url = BASE_URL + target
        if download_and_extract(url, os.path.join(DEST_DIR, ver)):
            structure.append(f'{DEST_DIR}/{ver}')
    
    print("\n>> [SYSTEM] Binary fetch complete.")
    print(f"   Structure: {', '.join(structure)}")

if __name__ == "__main__":
    main()