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

def main():
    # 1. 기존 bin 폴더 초기화
    if os.path.exists(DEST_DIR):
        shutil.rmtree(DEST_DIR)
    os.makedirs(DEST_DIR)

    structure = []

    # 2. 다운로드 및 압축 해제
    for ver, target in TARGETS.items():
        url = BASE_URL + target
        # 다운로드 경로: bin/cpu, bin/cuda, bin/cuda_dll 등
        if download_and_extract(url, os.path.join(DEST_DIR, ver)):
            structure.append(f'{DEST_DIR}/{ver}')

    # 3. [추가된 로직] cuda_dll -> cuda 병합 및 정리
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

        # 최종 출력 리스트에서 cuda_dll 제거 (보기 좋게)
        structure = [s for s in structure if "cuda_dll" not in s]

    print("\n>> [SYSTEM] Binary fetch complete.")
    print(f"   Structure: {', '.join(structure)}")

if __name__ == "__main__":
    main()