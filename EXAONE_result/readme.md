
# CPU 모드 테스트 (결과 파일 상단에 [실행 모드] CPU)uv pip uninstall torch torchvision torchaudiouv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpupytest tests/test_summary.py -v --tb=short | Tee-Object -FilePath cpu_results.txt

# GPU 모드 테스트 (결과 파일 상단에 [실행 모드] GPU)uv pip uninstall torch torchvision torchaudiouv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126pytest tests/test_summary.py -v --tb=short | Tee-Object -FilePath gpu_results.txt

  pytest tests/test_summary_inference_report.py -v -s