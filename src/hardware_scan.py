import os
import ctypes
import cpuinfo # pip install py-cpuinfo
import wmi     # pip install wmi

def get_cuda_driver_version():
    """
    nvidia-smi 없이 nvcuda.dll을 로드하여 드라이버 버전을 확인합니다.
    return: (Major, Minor) tuple or None
    """
    try:
        cuda = ctypes.windll.LoadLibrary("nvcuda.dll")
        version = ctypes.c_int()
        result = cuda.cuDriverGetVersion(ctypes.byref(version))
        
        if result == 0: 
            v = version.value
            major = v // 1000
            minor = (v % 1000) // 10
            return (major, minor)
    except Exception:
        pass
    return None

def check_system_capabilities():
    """
    시스템의 AI 구동 능력을 점수화하여 반환합니다.
    return: dict { 'cuda', 'vulkan', 'cpu_avx', 'cpu_avx2', 'cpu_avx512', 'recommended' }
    """
    print(">> [SCAN] Starting hardware scan...")
    
    result = {
        'cuda': False,
        'vulkan': False,
        'cpu_avx': False,
        'cpu_avx2': False,
        'cpu_avx512': False,
        'recommended': 'none'
    }

    # 1. CUDA 드라이버 확인
    cuda_ver = get_cuda_driver_version()
    if cuda_ver:
        major, minor = cuda_ver
        if major >= 11: 
            result['cuda'] = True

    # 2. Vulkan 확인 (WMI)
    try:
        w = wmi.WMI()
        for gpu in w.Win32_VideoController():
            name = gpu.Name.lower()
            if any(vendor in name for vendor in ['nvidia', 'amd', 'radeon', 'arc', 'geforce']):
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