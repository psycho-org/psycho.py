"""
summary.py의 SummaryAnalyzer 테스트 케이스
"""

import pytest

try:
    from infrastructure.summary import SummaryAnalyzer, get_summary_analyzer
except OSError as e:
    if "DLL" in str(e) or "1114" in str(e) or "c10.dll" in str(e).lower():
        pytest.skip(
            "PyTorch DLL could not be loaded (WinError 1114). "
            "Install Visual C++ Redistributable (https://aka.ms/vs/17/release/vc_redist.x64.exe) "
            "or reinstall torch: uv pip uninstall torch && uv pip install torch --index-url https://download.pytorch.org/whl/cpu",
            allow_module_level=True,
        )
    raise


class TestSummaryAnalyzer:
    """SummaryAnalyzer 클래스 테스트"""
    
    def test_init(self):
        """SummaryAnalyzer 초기화 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        assert analyzer is not None
        assert analyzer.model is not None
        assert analyzer.tokenizer is not None
        assert analyzer.device in ["cuda", "cpu"]
        assert analyzer.DEFAULT_MAX_LENGTH == 150
        assert analyzer.DEFAULT_MIN_LENGTH == 30
    
    def test_init_with_custom_model(self):
        """커스텀 모델명으로 초기화 테스트"""
        # 실제 모델이 없을 수 있으므로 기본 모델로 테스트
        analyzer = SummaryAnalyzer(model_name="LGAI-EXAONE/EXAONE-4.0-1.2B")
        print(f"  → Analyzer Device: {analyzer.device}")
        print(f"  → Model Name: {analyzer.model_name}")
        assert analyzer.model_name == "LGAI-EXAONE/EXAONE-4.0-1.2B"
    
    def test_summarize_basic(self):
        """기본 요약 기능 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        test_text = """
        오늘 런칭 준비 회의 대신 메신저로 진행할게요. 이번 주 목표 정리부터!
        현재 남은 이슈는 결제 오류, 온보딩 문구 확정, CS 매뉴얼 초안입니다.
        마케팅 쪽은 런칭 채널/예산 확정이 필요해요. 광고 시작일도.
        개발팀은 금요일 배포 가능할 것 같고, 단 결제 오류 원인 로그가 더 필요합니다.
        런칭일을 다음 주 화요일로 고정할까요? 아니면 안정화 위해 미룰까요.
        """
        
        summary = analyzer.summarize(test_text.strip())
        
        assert summary is not None
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_summarize_with_custom_length(self):
        """커스텀 길이로 요약 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        test_text = """
        Python은 1991년 귀도 반 로섬이 개발한 고급 프로그래밍 언어입니다.
        간결하고 읽기 쉬운 문법이 특징이며, 다양한 분야에서 활용됩니다.
        웹 개발, 데이터 분석, 인공지능, 자동화 등에 널리 사용됩니다.
        """
        
        # 짧은 요약
        short_summary = analyzer.summarize(test_text.strip(), max_length=50, min_length=10)
        assert len(short_summary) > 0
        
        # 긴 요약
        long_summary = analyzer.summarize(test_text.strip(), max_length=200, min_length=50)
        assert len(long_summary) > 0
    
    def test_summarize_empty_text(self):
        """빈 텍스트 요약 테스트"""
        analyzer = SummaryAnalyzer()
        
        # 빈 텍스트는 모델이 처리하지만, 결과가 예상과 다를 수 있음
        summary = analyzer.summarize("")
        assert isinstance(summary, str)
    
    def test_summarize_short_text(self):
        """짧은 텍스트 요약 테스트"""
        analyzer = SummaryAnalyzer()
        
        short_text = "오늘 날씨가 좋습니다."
        summary = analyzer.summarize(short_text)
        assert isinstance(summary, str)
    
    @pytest.mark.asyncio
    async def test_summarize_async(self):
        """비동기 요약 기능 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        test_text = """
        FastAPI는 Python 웹 프레임워크입니다.
        높은 성능과 쉬운 사용법으로 인기가 높습니다.
        자동 API 문서 생성 기능도 제공합니다.
        """
        
        summary = await analyzer.summarize_async(test_text.strip())
        
        assert summary is not None
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    @pytest.mark.asyncio
    async def test_summarize_async_with_custom_length(self):
        """커스텀 길이로 비동기 요약 테스트"""
        analyzer = SummaryAnalyzer()
        
        test_text = """
        테스트 주도 개발(Test-Driven Development, TDD)은 소프트웨어 개발 방법론입니다.
        먼저 테스트를 작성하고, 그 다음 코드를 작성하여 테스트를 통과시킵니다.
        이를 통해 코드 품질과 유지보수성을 향상시킬 수 있습니다.
        """
        
        summary = await analyzer.summarize_async(
            test_text.strip(),
            max_length=100,
            min_length=20
        )
        
        assert summary is not None
        assert isinstance(summary, str)
    
    def test_summarize_batch(self):
        """배치 요약 기능 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        texts = [
            "첫 번째 텍스트입니다. 이것은 테스트용 텍스트입니다.",
            "두 번째 텍스트입니다. 이것도 테스트용 텍스트입니다.",
            "세 번째 텍스트입니다. 마지막 테스트용 텍스트입니다.",
        ]
        
        summaries = analyzer.summarize_batch(texts)
        
        assert summaries is not None
        assert isinstance(summaries, list)
        assert len(summaries) == len(texts)
        assert all(isinstance(s, str) for s in summaries)
        assert all(len(s) > 0 for s in summaries)
    
    def test_summarize_batch_with_custom_length(self):
        """커스텀 길이로 배치 요약 테스트"""
        analyzer = SummaryAnalyzer()
        
        texts = [
            "Python은 간결한 문법을 가진 프로그래밍 언어입니다.",
            "FastAPI는 현대적인 Python 웹 프레임워크입니다.",
            "pytest는 Python 테스트 프레임워크입니다.",
        ]
        
        summaries = analyzer.summarize_batch(
            texts,
            max_length=100,
            min_length=20
        )
        
        assert len(summaries) == len(texts)
        assert all(isinstance(s, str) for s in summaries)
    
    def test_summarize_batch_max_size_exceeded(self):
        """배치 크기 초과 시 에러 테스트"""
        analyzer = SummaryAnalyzer()
        
        # max_batch_size를 초과하는 텍스트 리스트 생성
        texts = [f"텍스트 {i}" for i in range(101)]  # 기본 max_batch_size는 100
        
        with pytest.raises(ValueError, match="텍스트 개수는 최대"):
            analyzer.summarize_batch(texts)
    
    def test_summarize_batch_custom_max_size(self):
        """커스텀 max_batch_size 테스트"""
        analyzer = SummaryAnalyzer()
        
        texts = [f"텍스트 {i}" for i in range(50)]
        
        # max_batch_size를 50으로 설정하면 정상 동작
        summaries = analyzer.summarize_batch(texts, max_batch_size=50)
        assert len(summaries) == 50


class TestGetSummaryAnalyzer:
    """get_summary_analyzer 함수 테스트"""
    
    def test_get_summary_analyzer_singleton(self):
        """싱글톤 패턴 테스트"""
        analyzer1 = get_summary_analyzer()
        analyzer2 = get_summary_analyzer()
        
        # 같은 인스턴스여야 함
        assert analyzer1 is analyzer2
        assert isinstance(analyzer1, SummaryAnalyzer)
    
    def test_get_summary_analyzer_functionality(self):
        """get_summary_analyzer로 얻은 인스턴스 기능 테스트"""
        analyzer = get_summary_analyzer()
        
        test_text = "이것은 테스트 텍스트입니다."
        summary = analyzer.summarize(test_text)
        
        assert summary is not None
        assert isinstance(summary, str)


class TestSummaryAnalyzerIntegration:
    """통합 테스트"""
    
    def test_full_workflow(self):
        """전체 워크플로우 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        # 1. 단일 텍스트 요약
        text1 = "첫 번째 문서입니다."
        summary1 = analyzer.summarize(text1)
        assert isinstance(summary1, str)
        
        # 2. 배치 요약
        texts = [text1, "두 번째 문서입니다.", "세 번째 문서입니다."]
        summaries = analyzer.summarize_batch(texts)
        assert len(summaries) == 3
    
    @pytest.mark.asyncio
    async def test_async_workflow(self):
        """비동기 워크플로우 테스트"""
        analyzer = SummaryAnalyzer()
        print(f"  → Analyzer Device: {analyzer.device}")
        
        # 비동기 요약
        text = "비동기로 요약할 텍스트입니다."
        summary = await analyzer.summarize_async(text)
        assert isinstance(summary, str)
        assert len(summary) > 0
