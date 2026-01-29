"""
pytest 설정 및 공통 fixture
"""

import time
import pytest
import torch


@pytest.fixture(autouse=True)
def timer_and_device_info(request):
    """각 테스트의 실행 시간과 device 정보를 출력하는 fixture"""
    # 테스트 시작 시간 기록
    start_time = time.time()
    
    # Device 정보 출력
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cuda_info = ""
    if device == "cuda" and torch.cuda.is_available():
        try:
            cuda_info = f" ({torch.cuda.get_device_name(0)})"
        except:
            pass
    
    print(f"\n{'='*70}")
    print(f"▶ 테스트 시작: {request.node.name}")
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
    print(f"✓ 테스트 완료: {request.node.name}")
    print(f"  소요 시간: {time_str}")
    print(f"{'='*70}\n")
