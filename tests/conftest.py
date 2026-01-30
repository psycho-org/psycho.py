"""
pytest 설정 및 공통 fixture
"""

import time
import pytest

# torch import를 안전하게 처리
try:
    import torch
    TORCH_AVAILABLE = True
except (ImportError, OSError) as e:
    TORCH_AVAILABLE = False
    torch = None
    print(f"경고: torch를 로드할 수 없습니다. {e}")
    print("테스트는 계속 실행되지만 torch 관련 기능은 건너뜁니다.")


def pytest_sessionstart(session):
    """테스트 세션 시작 시 실행 모드(CPU/GPU) 출력 + 리소스 출력 활성화."""
    import os
    os.environ["PSYCHO_PYTEST"] = "1"  # summary.summary에서 리소스 출력 허용
    print("")
    print("=" * 70)
    if TORCH_AVAILABLE and torch is not None:
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
                print(f"[실행 모드] GPU (CUDA)")
                print(f"[디바이스] {name}")
            except Exception:
                print("[실행 모드] GPU (CUDA)")
        else:
            print("[실행 모드] CPU")
    else:
        print("[실행 모드] (torch 미로드)")
    print("=" * 70)
    print("")


@pytest.fixture(autouse=True)
def timer_and_device_info(request):
    """각 테스트의 실행 시간과 device 정보를 출력하는 fixture"""
    # 테스트 시작 시간 기록
    start_time = time.time()
    
    # Device 정보 출력
    if TORCH_AVAILABLE and torch is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        cuda_info = ""
        if device == "cuda" and torch.cuda.is_available():
            try:
                cuda_info = f" ({torch.cuda.get_device_name(0)})"
            except:
                pass
    else:
        device = "unavailable"
        cuda_info = " (torch not loaded)"
    
    print(f"\n{'='*70}")
    print(f"[테스트 시작] {request.node.name}")
    print(f"  Device: {device}{cuda_info}")
    print(f"{'='*70}")
    
    yield
    
    # 테스트 종료 시간 기록 및 출력
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 시간 포맷팅
    if elapsed_time < 1:
        time_str = f"{elapsed_time*1000:.2f}ms"
    elif elapsed_time < 60:
        time_str = f"{elapsed_time:.3f}초"
    else:
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60
        time_str = f"{minutes}분 {seconds:.2f}초"
    
    print(f"\n{'='*70}")
    print(f"[테스트 완료] {request.node.name}")
    print(f"  소요 시간: {time_str}")
    print(f"{'='*70}\n")
