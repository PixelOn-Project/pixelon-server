import os
import ctypes
import cpuinfo # pip install py-cpuinfo
import wmi     # pip install wmi

def check_cuda_requirements():
    """
    nvcuda.dll을 사용하여 하드웨어 호환성을 검증합니다.
    
    조건:
    1. Compute Capability 7.5 이상 (RTX 20 시리즈 이상, Turing 아키텍처)
    2. VRAM 4GB 이상
    
    Returns:
        (bool, str): (호환 여부, 메시지)
    """
    try:
        # 1. nvcuda.dll 로드
        cuda = ctypes.windll.LoadLibrary("nvcuda.dll")
        
        # 2. CUDA 드라이버 초기화 (반드시 필요)
        # cuInit(0) -> 성공 시 0 반환
        result = cuda.cuInit(0)
        if result != 0:
            return False, "CUDA 드라이버 초기화 실패 (Driver Error Code: {})".format(result)

        # 3. 장치 개수 확인
        device_count = ctypes.c_int()
        cuda.cuDeviceGetCount(ctypes.byref(device_count))
        
        if device_count.value == 0:
            return False, "CUDA를 지원하는 GPU가 없습니다."

        # 상수 정의 (CUDA Driver API Enum)
        CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR = 75
        CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR = 76
        
        # 장치 순회 (여러 GPU가 있을 경우를 대비)
        for i in range(device_count.value):
            device = ctypes.c_int()
            # i번째 장치 핸들 얻기
            cuda.cuDeviceGet(ctypes.byref(device), i)
            
            # --- 아키텍처(CC) 확인 ---
            cc_major = ctypes.c_int()
            cc_minor = ctypes.c_int()
            cuda.cuDeviceGetAttribute(ctypes.byref(cc_major), CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR, device)
            cuda.cuDeviceGetAttribute(ctypes.byref(cc_minor), CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR, device)
            
            major = cc_major.value
            minor = cc_minor.value
            
            # --- VRAM 확인 ---
            # cuDeviceTotalMem_v2는 64비트 메모리 주소를 반환 (bytes 단위)
            mem_bytes = ctypes.c_size_t()
            try:
                cuda.cuDeviceTotalMem_v2(ctypes.byref(mem_bytes), device)
            except AttributeError:
                # 구형 드라이버 호환성 (v2가 없을 경우)
                cuda.cuDeviceTotalMem(ctypes.byref(mem_bytes), device)
            
            vram_gb = mem_bytes.value / (1024**3)
            
            print(f"GPU {i}: CC {major}.{minor}, VRAM {vram_gb:.2f} GB")

            # 검증 로직
            # 조건 1: CC 7.5 이상 (RTX 2000번대 이상)
            is_arch_valid = (major > 7) or (major == 7 and minor >= 5)
            
            # 조건 2: VRAM 4GB 이상 (오차 감안하여 3.9GB 정도로 여유를 둠)
            is_vram_valid = vram_gb >= 3.9
            
            if is_arch_valid and is_vram_valid:
                return True, f"설치 가능: GPU {i} (CC {major}.{minor}, VRAM {vram_gb:.2f} GB)"

        return False, "조건을 만족하는 GPU가 없습니다. (최소사양: RTX 20 시리즈 이상, VRAM 4GB 이상)"

    except OSError:
        return False, "NVIDIA 드라이버가 설치되어 있지 않습니다 (nvcuda.dll 로드 실패)."
    except Exception as e:
        return False, f"검증 중 오류 발생: {e}"

def check_romc_requirements():
    """
    AMD ROMc 호환성 검증 (WMI 기반)
    """
    try:
        w = wmi.WMI()
        supported_arch = [
            # GFX906
            'radeon vii', 'mi50', 
            # GFX1030 (RDNA2 High-end)
            'rx 6800', 'rx 6900', 'rx 6950',
            # GFX1100, 1101, 1102 (RDNA3)
            'rx 7900', 'rx 7800', 'rx 7700', 'rx 7600',
            # Future/Integrated (GFX1150/1151 - Ryzen 8000/9000 AI series might be supported later, but stick to dGPU for now)
        ]
        
        for gpu in w.Win32_VideoController():
            name = gpu.Name.lower()
            # 1. AMD 제조사 확인
            if 'amd' in name or 'radeon' in name:
                # 2. VRAM 확인 (4GB 이상 권장)
                vram_gb = 0
                try:
                    vram_gb = int(gpu.AdapterRAM) / (1024**3)
                except:
                    pass # VRAM 정보를 못 가져오는 경우 패스
                
                # 3. 아키텍처 매칭
                # 단순 포함 여부 확인 (엄격한 GFX ID 확인은 복잡하므로 모델명 매칭 사용)
                is_supported = any(arch in name for arch in supported_arch)
                
                if is_supported and vram_gb >= 3.9:
                    return True, f"설치 가능: {gpu.Name} (VRAM {vram_gb:.2f} GB)"
                elif is_supported:
                     return True, f"아키텍처 호환 (VRAM 부족 주의): {gpu.Name}"
                     
        return False, "지원되는 AMD GPU를 찾을 수 없습니다. (RX 6000/7000 시리즈 또는 Radeon VII 필요)"
    
    except Exception as e:
        return False, f"AMD 검증 중 오류: {e}"

def check_system_capabilities():
    """
    시스템의 AI 구동 능력을 점수화하여 반환합니다.
    return: dict { 'cuda', 'vulkan', 'cpu_avx', 'cpu_avx2', 'cpu_avx512', 'recommended' }
    """
    print(">> [SCAN] Starting hardware scan...")
    
    result = {
        'cuda': False,
        'romc': False,
        'vulkan': False,
        'cpu_avx': False,
        'cpu_avx2': False,
        'cpu_avx512': False,
        'recommended': 'none'
    }

    # 1. CUDA 드라이버 확인
    cuda_result = check_cuda_requirements()
    check, msg = cuda_result    
    result['cuda'] = check

    # [삽입] 1.5 AMD ROMc 확인
    romc_check, romc_msg = check_romc_requirements()
    result['romc'] = romc_check
    if romc_check:
        print(f">> [SCAN] AMD ROMc Compatible: {romc_msg}")

    # 2. Vulkan 확인 (WMI)
    try:
        w = wmi.WMI()
        for gpu in w.Win32_VideoController():
            name = gpu.Name.lower()
            if any(vendor in name for vendor in ['nvidia', 'amd', 'radeon', 'arc', 'geforce', 'intel']):
                result['vulkan'] = True
    except:
        pass

    # 3. CPU AVX 지원 확인
    try:
        info = cpuinfo.get_cpu_info()
        flags = info.get('flags', [])
        flags = [f.lower() for f in flags]

        if 'avx' in flags: result['cpu_avx'] = True
        if 'avx2' in flags: result['cpu_avx2'] = True
        if 'avx512f' in flags: result['cpu_avx512'] = True
        
        print(f">> [SCAN] CPU Flags: AVX={result['cpu_avx']}, AVX2={result['cpu_avx2']}, AVX512={result['cpu_avx512']}")
    except:
        pass

    # 4. 추천 옵션 결정 Logic (우선순위: CUDA > Vulkan > AVX512 > AVX2 > AVX)
    if result['cuda']:
        result['recommended'] = 'cuda'
    elif result['vulkan']:
        result['recommended'] = 'vulkan'
    elif result['cpu_avx512']:
        result['recommended'] = 'cpu_avx512'
    elif result['cpu_avx2']:
        result['recommended'] = 'cpu_avx2'
    elif result['cpu_avx']:
        result['recommended'] = 'cpu_avx'
    else:
        result['recommended'] = 'none' # 설치 불가

    print(f">> [SCAN] Recommended Mode: {result['recommended'].upper()}")
    return result