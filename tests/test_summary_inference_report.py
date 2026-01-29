"""
모델 추론 결과 리포트용 테스트.
- 어떤 입력(문자열)을 넣었을 때 어떤 요약(출력)이 나오는지 기록한다.
- 테스트 실행 시 입력/출력이 출력되고, 리포트 파일로도 저장된다.
"""

import json
import os
from datetime import datetime

import pytest

try:
    from model.summary.summary import get_summary_analyzer
except OSError as e:
    if "DLL" in str(e) or "1114" in str(e) or "c10.dll" in str(e).lower():
        pytest.skip(
            "PyTorch DLL could not be loaded (WinError 1114). "
            "Install Visual C++ Redistributable or reinstall torch.",
            allow_module_level=True,
        )
    raise

# 리포트용 입력 케이스: (케이스 ID, 설명, 입력 텍스트)
INFERENCE_REPORT_CASES = [
    (
        "short",
        "짧은 문장",
        "오늘 날씨가 좋습니다. 공원에서 산책을 했어요.",
    ),
    (
        "meeting_short",
        "회의록 요약 (짧음)",
        """오늘 런칭 준비 회의를 메신저로 진행했습니다.
현재 남은 이슈는 결제 오류, 온보딩 문구 확정, CS 매뉴얼 초안입니다.
런칭일을 다음 주 화요일로 정했고, 결제 오류는 금요일 18시까지 해결 여부를 보고하기로 했습니다.""",
    ),
    (
        "meeting_medium",
        "회의록 요약 (중간)",
        """오늘 런칭 준비 회의 대신 메신저로 진행할게요. 이번 주 목표 정리부터!
현재 남은 이슈는 결제 오류, 온보딩 문구 확정, CS 매뉴얼 초안입니다.
마케팅 쪽은 런칭 채널/예산 확정이 필요해요. 광고 시작일도.
개발팀은 금요일 배포 가능할 것 같고, 단 결제 오류 원인 로그가 더 필요합니다.
런칭일을 다음 주 화요일로 고정할까요? 아니면 안정화 위해 미룰까요.
저는 화요일 고정 찬성. 일정 계속 밀리면 마케팅 타이밍 놓칠 듯.
그럼 런칭일은 다음 주 화요일로 하고, 결제 오류는 금요일 밤까지 해결 여부 보고해서 GO/NO GO 체크하죠.
마케팅 예산안: 인스타 150만, 구글 150만, 리타겟팅 100만 = 총 400만.
CS 매뉴얼은 목요일 17시 마감. 환불 정책은 결제 후 7일 이내 전액으로 단순화하기로 했습니다.""",
    ),
    (
        "tech",
        "기술 설명",
        """Python은 1991년 귀도 반 로섬이 개발한 고급 프로그래밍 언어입니다.
간결하고 읽기 쉬운 문법이 특징이며, 웹 개발, 데이터 분석, 인공지능, 자동화 등에 널리 사용됩니다.
FastAPI는 Python 웹 프레임워크로, 높은 성능과 자동 API 문서 생성 기능으로 인기가 높습니다.""",
    ),
    (
        "news_style",
        "뉴스/보도 스타일",
        """삼성전자가 오늘 2024년 1분기 실적을 발표했다. 매출은 전년 대비 12% 증가한 71조원을 기록했으며,
반도체 부문이 호조를 보인 것이 주요 원인으로 분석된다. 회사 관계자는 "올해 하반기 메모리 수요 회복이 예상된다"고 밝혔다.""",
    ),
]


def _get_report_path():
    """리포트 파일 저장 경로 (프로젝트 루트 기준)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "inference_report.json")


def _write_report(results: list[dict], report_path: str, analyzer) -> None:
    """추론 결과 리스트를 JSON 리포트로 저장. 모델/디바이스 정보 포함."""
    payload = {
        "generated_at": datetime.now().isoformat(),
        "model": getattr(analyzer, "model_name", "unknown"),
        "device": getattr(analyzer, "device", "unknown"),
        "cases": results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n[리포트 저장] {report_path}")


class TestSummaryInferenceReport:
    """입력/출력 기록용 추론 리포트 테스트. 모델별 추론 결과 리포트 작성용."""

    @pytest.fixture(scope="class")
    def analyzer(self):
        """클래스에서 한 번만 분석기 생성."""
        return get_summary_analyzer()

    def test_inference_report_all_cases(self, analyzer):
        """
        모든 리포트 케이스에 대해 요약을 실행하고,
        입력/출력을 출력한 뒤 inference_report.json 으로 저장한다.
        """
        report_path = _get_report_path()
        results = []

        for case_id, description, input_text in INFERENCE_REPORT_CASES:
            summary = analyzer.summarize(input_text.strip())

            result = {
                "case_id": case_id,
                "description": description,
                "input": input_text.strip(),
                "input_length": len(input_text.strip()),
                "output": summary,
                "output_length": len(summary),
            }
            results.append(result)

            # 테스트 출력: 입력/출력 구분해서 출력
            print("\n" + "=" * 70)
            print(f"[리포트 케이스] {case_id} - {description}")
            print("=" * 70)
            print("[INPUT]")
            print(input_text.strip())
            print("-" * 70)
            print("[OUTPUT (요약)]")
            print(summary)
            print("=" * 70)

            assert isinstance(summary, str), "요약 결과는 문자열이어야 함"
            assert len(summary) > 0, "요약 결과는 비어있지 않아야 함"

        _write_report(results, report_path, analyzer)
