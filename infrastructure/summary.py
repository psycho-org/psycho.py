"""
LGAI EXAONE 모델을 사용한 텍스트 요약
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# 리소스 사용량 출력용 (psutil 없으면 GPU만 표시)
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def _get_resource_usage() -> str:
    """현재 프로세스의 리소스 사용량 문자열 반환 (GPU 메모리, RAM, CPU)."""
    lines = []
    process = psutil.Process() if _PSUTIL_AVAILABLE else None
    # GPU 메모리 (CUDA)
    if torch.cuda.is_available():
        try:
            alloc = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            lines.append(f"GPU 메모리: {alloc:.2f}GB 할당 / {reserved:.2f}GB 예약 / {total:.2f}GB 총량")
        except Exception:
            pass
    # 프로세스 RAM / CPU (psutil 있을 때만)
    if process is not None:
        try:
            rss_gb = process.memory_info().rss / 1024**3
            cpu_pct = process.cpu_percent(interval=0.1)
            lines.append(f"프로세스 RAM: {rss_gb:.2f}GB")
            lines.append(f"프로세스 CPU: {cpu_pct:.1f}%")
        except Exception:
            pass
    return " | ".join(lines) if lines else "(리소스 정보 없음)"


def print_resource_usage(label: str = "리소스") -> None:
    """리소스 사용량을 출력한다. pytest 실행 시에만 출력 (PSYCHO_PYTEST=1)."""
    import os
    if os.environ.get("PSYCHO_PYTEST") != "1":
        return
    usage = _get_resource_usage()
    print(f"[{label}] {usage}")


class SummaryAnalyzer:
    """EXAONE 모델을 사용한 텍스트 요약"""
    
    # 요약 길이 상수
    DEFAULT_MAX_LENGTH = 150  # 최대 요약 길이 (토큰 수)
    DEFAULT_MIN_LENGTH = 30  # 최소 요약 길이 (토큰 수)
    
    def __init__(
        self,
        model_name: str = "LGAI-EXAONE/EXAONE-4.0-1.2B",
        executor: ThreadPoolExecutor | None = None,
        max_workers: int = 4,
    ):
        """
        Args:
            model_name: 사용할 모델 이름
            executor: 커스텀 ThreadPoolExecutor (None이면 새로 생성)
            max_workers: 워커 스레드 개수 (executor가 None일 때만 사용)
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        # 비동기 처리를 위한 스레드 풀
        self.executor = executor or ThreadPoolExecutor(max_workers=max_workers)
        self.max_workers = max_workers
        
        print(f"[로딩] EXAONE 모델 로딩 중: {model_name}")
        try:
            # Hugging Face Hub 타임아웃 설정 (기본값 10초 -> 300초로 증가)
            # 환경 변수로만 설정 (from_pretrained의 timeout 파라미터는 일부 모델에서 지원 안 함)
            import os
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # Windows symlink 경고 제거
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            # pad_token이 없으면 eos_token을 사용
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
            )
            if self.device == "cpu":
                self.model.to(self.device)
            self.model.eval()
            
            # GPU 사용 확인 및 출력
            if self.device == "cuda":
                model_device = next(self.model.parameters()).device
                print(f"[완료] EXAONE 모델 로드 완료: {model_name}")
                print(f"   모델 위치: {model_device}")
                print(f"   메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB 총량")
            else:
                print(f"[완료] EXAONE 모델 로드 완료: {model_name} (CPU 모드)")
            print_resource_usage("모델 로드 직후")
        except Exception as e:
            print(f"[실패] 모델 로드 실패: {e}")
            raise
    
    def summarize(
        self,
        text: str,
        max_length: int | None = None,
        min_length: int | None = None,
    ) -> str:
        """
        텍스트를 요약합니다.
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이 (토큰 수), None이면 기본값 사용
            min_length: 최소 요약 길이 (토큰 수), None이면 기본값 사용
        
        Returns:
            요약된 텍스트
        """
        # 시간 측정 시작
        start_time = time.time()
        
        # 상수 값 사용
        max_length = max_length if max_length is not None else self.DEFAULT_MAX_LENGTH
        min_length = min_length if min_length is not None else self.DEFAULT_MIN_LENGTH
        # EXAONE 모델은 채팅 템플릿 형식을 사용해야 함
        prompt = f"다음 텍스트를 간결하게 요약해주세요:\n\n{text}"
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # 채팅 템플릿 적용 (텍스트로 먼저 생성)
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # 토크나이징
        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        )
        
        input_ids = inputs["input_ids"].to(self.device)
        input_length = input_ids.shape[1]
        
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids,
                max_new_tokens=max_length,  # 새로 생성할 토큰 수
                min_new_tokens=min_length,  # 최소 생성 토큰 수
                do_sample=True,
                temperature=0.5,  # non-reasoning 모드에서는 낮은 temperature 권장
                top_p=0.95,
                repetition_penalty=1.2,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        
        # 생성된 텍스트 디코딩 (입력 프롬프트 제외)
        generated_text = self.tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        )
        
        # 불필요한 문자 제거 및 정리
        generated_text = generated_text.strip()
        
        if generated_text.startswith("-") and all(c in "- " for c in generated_text[:20]):
            # 모델이 제대로 생성하지 못한 경우, 재시도 또는 기본 메시지 반환
            generated_text = "요약 생성에 실패했습니다. 텍스트가 너무 짧거나 모델이 요약을 생성하지 못했습니다."
        
        # 시간 측정 종료
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 요약 길이, 시간, 리소스 출력
        print(f"요약 길이: {len(generated_text)}자")
        print(f"[완료] 요약 완료: {elapsed_time:.2f}초 소요")
        print_resource_usage("요약 직후")
        
        return generated_text
    
    def _summarize_internal(
        self,
        text: str,
        max_length: int | None = None,
        min_length: int | None = None,
        silent: bool = False,
    ) -> tuple[str, float]:
        """
        내부 요약 메서드 (배치 처리용)
        
        Returns:
            (요약된 텍스트, 처리 시간)
        """
        start_time = time.time()
        
        max_length = max_length if max_length is not None else self.DEFAULT_MAX_LENGTH
        min_length = min_length if min_length is not None else self.DEFAULT_MIN_LENGTH
        
        prompt = f"다음 텍스트를 간결하게 요약해주세요:\n\n{text}"
        messages = [{"role": "user", "content": prompt}]
        
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        )
        
        input_ids = inputs["input_ids"].to(self.device)
        input_length = input_ids.shape[1]
        
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids,
                max_new_tokens=max_length,
                min_new_tokens=min_length,
                do_sample=True,
                temperature=0.5,
                top_p=0.95,
                repetition_penalty=1.2,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        
        generated_text = self.tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        )
        
        generated_text = generated_text.strip()
        
        if generated_text.startswith("-") and all(c in "- " for c in generated_text[:20]):
            generated_text = "요약 생성에 실패했습니다. 텍스트가 너무 짧거나 모델이 요약을 생성하지 못했습니다."
        
        elapsed_time = time.time() - start_time
        
        if not silent:
            print(f"요약 길이: {len(generated_text)}자")
            print(f"[완료] 요약 완료: {elapsed_time:.2f}초 소요")
        
        return generated_text, elapsed_time
    
    async def summarize_async(
        self,
        text: str,
        max_length: int | None = None,
        min_length: int | None = None,
    ) -> str:
        """
        텍스트를 비동기로 요약합니다.
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이 (토큰 수), None이면 기본값 사용
            min_length: 최소 요약 길이 (토큰 수), None이면 기본값 사용
        
        Returns:
            요약된 텍스트
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self.summarize,
            text,
            max_length,
            min_length,
        )
    
    def summarize_batch(
        self,
        texts: list[str],
        max_length: int | None = None,
        min_length: int | None = None,
        max_batch_size: int = 100,
    ) -> list[str]:
        """
        여러 텍스트를 한 번에 요약
        
        Args:
            texts: 요약할 텍스트 리스트
            max_length: 최대 요약 길이 (토큰 수), None이면 기본값 사용
            min_length: 최소 요약 길이 (토큰 수), None이면 기본값 사용
            max_batch_size: 최대 배치 크기 (텍스트 개수)
        
        Returns:
            요약된 텍스트 리스트
        
        Raises:
            ValueError: 텍스트 개수가 max_batch_size를 초과하는 경우
        """
        # 빈 입력에 대한 조기 반환 (ZeroDivisionError 방지)
        if not texts:
            return []
        
        if len(texts) > max_batch_size:
            raise ValueError(
                f"텍스트 개수는 최대 {max_batch_size}개까지 가능합니다. "
                f"현재 {len(texts)}개가 제공되었습니다."
            )
        
        # 배치 요약 시간 측정 시작
        batch_start_time = time.time()
        total_count = len(texts)
        
        results = []
        for idx, text in enumerate(texts, start=1):
            print(f"  [진행] {idx}/{total_count} ({idx*100//total_count}%)")
            
            # 배치 처리용 내부 메서드 사용 (출력 억제)
            result, item_elapsed_time = self._summarize_internal(
                text, max_length, min_length, silent=True
            )
            
            # 각 항목의 처리 시간과 요약 길이 출력
            print(f"     처리 시간: {item_elapsed_time:.2f}초 | 요약 길이: {len(result)}자")
            
            results.append(result)
        
        # 배치 요약 시간 측정 종료 및 출력
        batch_end_time = time.time()
        batch_elapsed_time = batch_end_time - batch_start_time
        print(f"[완료] 배치 요약 완료: {total_count}개 텍스트, 총 {batch_elapsed_time:.2f}초 소요 (평균 {batch_elapsed_time/total_count:.2f}초/개)")
        
        return results


# 싱글톤 인스턴스 저장소 (모델명별로 관리)
_summary_instances: dict[str, SummaryAnalyzer] = {}
_init_lock = threading.Lock()


def get_summary_analyzer(model_name: str = "LGAI-EXAONE/EXAONE-4.0-1.2B") -> SummaryAnalyzer:
    """
    전역 요약 분석기 인스턴스 반환 (thread-safe)
    
    같은 model_name에 대해서는 싱글톤으로 동작하지만,
    다른 model_name을 사용하면 여러 인스턴스를 생성할 수 있습니다.
    
    Args:
        model_name: 사용할 모델 이름 (기본값: "LGAI-EXAONE/EXAONE-4.0-1.2B")
    
    Returns:
        SummaryAnalyzer 인스턴스
    """
    global _summary_instances
    
    # Double-checked locking 패턴으로 race condition 방지
    if model_name not in _summary_instances:
        with _init_lock:
            # Lock 내에서 다시 확인 (다른 스레드가 이미 생성했을 수 있음)
            if model_name not in _summary_instances:
                _summary_instances[model_name] = SummaryAnalyzer(model_name=model_name)
    
    return _summary_instances[model_name]


if __name__ == "__main__":
    """Infrastructure 레이어 직접 테스트 (실제 실행 시 리소스/실행모드 출력 없음)"""
    print("=" * 60)
    print("Infrastructure 레이어 직접 테스트")
    print("=" * 60)
    
    analyzer = SummaryAnalyzer()
    
    test_text = """
    오늘 런칭 준비 회의 대신 메신저로 진행할게요. 이번 주 목표 정리부터!
OK. 현재 남은 이슈는 결제 오류, 온보딩 문구 확정, CS 매뉴얼 초안입니다.
마케팅 쪽은 런칭 채널/예산 확정이 필요해요. 광고 시작일도.
개발팀은 금요일 배포 가능할 것 같고, 단 결제 오류 원인 로그가 더 필요합니다.
런칭일을 다음 주 화요일로 고정할까요? 아니면 안정화 위해 미룰까요.
저는 화요일 고정 찬성. 일정 계속 밀리면 마케팅 타이밍 놓칠 듯.
반대는 아니지만 결제 오류가 남아있어서 리스크 있어요. 하루만 더 봐도 좋고.
광고는 월요일부터 집행하려고 세팅 중이라 런칭이 화요일이면 맞출 수 있어요.
그럼 런칭일은 다음 주 화요일로 하고, 결제 오류는 금요일 밤까지 해결 여부 보고해서 GO/NO GO 체크하죠.
알겠습니다. 제가 결제 오류 담당하고 금요일 18시까지 상황 공유할게요.
온보딩 문구는 3분 만에 시작 vs 1분 만에 시작 중 뭐가 좋을까요?
1분은 과장처럼 보일 수 있어요. 법무 리스크도.
온보딩 헤드라인은 3분 만에 시작으로 확정할게요.
그럼 온보딩 화면 1~3번 카피도 오늘 중으로 정리해서 올리겠습니다.
앱 내 튜토리얼을 스킵 불가로 하면 전환률 좋아질까요?
스킵 불가는 사용자 불만 많을 듯. 제안은 거절하고 스킵 가능 유지하죠.
동의. 대신 첫 화면에 스킵 가능을 작게 표시하면 이탈 줄 수도.
그럼 스킵 가능 + 첫 화면에 안내 문구 추가로 진행할게요.
네 결정. 준호가 카피 포함해서 반영해주세요.
마케팅 예산안 공유합니다. 인스타 200만, 구글 150만, 리타겟팅 50만 = 총 400만.
예산 400만이면 괜찮은데, 리타겟팅 50만은 너무 적지 않나요?
맞아요. 대신 인스타를 150만으로 줄이고 리타겟팅을 100만으로 늘리면 효율이 좋아요.
인스타 줄이면 신규 유입이 줄 수 있어서 걱정.
이번 런칭은 재방문도 중요하니까 리타겟팅 강화 동의. 인스타 150만 / 구글 150만 / 리타겟팅 100만.
오케이, 오늘 안에 매체별 집행 플랜 업데이트하겠습니다.
결제 오류 관련, iOS 17에서 특정 카드 결제시 콜백 누락 로그 확인했어요.
그럼 iOS만 임시로 결제수단 제한하는 건 어때요?
제한하면 민원 폭주할 수도. 대안 없나요?
결제 SDK 버전 올리면 해결 가능할 듯. 근데 QA 하루 더 필요.
런칭일 고정이라 QA 하루 더는 부담. SDK 업데이트 진행하되, QA는 금요일 집중 + 주말 핫픽스 준비로 가죠.
좋습니다. 제가 오늘 SDK 업데이트 브랜치 파서 밤까지 PR 올릴게요.
CS 매뉴얼 초안은 누가 보나요? 지금 상태로는 답변 톤이 너무 딱딱해요.
제가 초안 작성했는데, 톤 가이드는 마케팅이 더 잘 알 듯.
CS 매뉴얼은 준호가 내용, 소라가 톤/표현 수정. 마감은 목요일 17시.
가능해요. 대신 FAQ 1~2개는 정책 확인 필요. 환불 규정 애매합니다.
환불은 사용 전 7일 이내 전액으로 하는거 어떨까요?
결제 파트에서 부분환불 로직 아직 없어서 7일 전액은 가능. 사용 여부 판단은 어려울 듯.
그럼 결제 후 7일 이내, 사용 이력 없으면 전액은 구현 난이도 있어요.
맞네요. 환불 정책은 결제 후 7일 이내 전액으로 단순화. 추후 고도화.
그럼 약관/공지 문구도 그 기준으로 업데이트할게요.
서버 비용 관련, 지금 AWS 인스턴스를 한 단계 올리면 월 30만 추가됩니다.
런칭 초기 트래픽 예상치면 지금도 버틸 것 같은데요.
다운되면 더 큰 손해. 다만 예산도 고려해야.
오토스케일링 최소/최대 조정으로 비용 증가를 10~15만 수준으로 줄일 수 있어요.
좋아요. 인스턴스 업그레이드 대신 오토스케일링 조정으로 대응, 태훈이 오늘 설정 변경.
런칭 공지문은 블로그/인스타/카카오채널 3종으로 가고, 보도자료는 이번엔 생략하자.
보도자료 생략은 아쉽지만 리소스 없으니 동의.
보도자료는 이번 런칭에서 제외, 대신 블로그 글 퀄리티 높이기. 소라가 초안, 준호가 제품 파트 검수.
금요일 18시 결제 오류 해결 여부 공유, 목요일 17시 CS 매뉴얼 완료, 화요일 런칭.
네. 추가 이슈 없으면 이 플랜으로 진행합니다. 다들 진행상황은 이 스레드에 계속 업데이트해주세요.
    """
    
    print(f"\n원문: {test_text.strip()[:200]}...")
    print("-" * 60)
    
    summary = analyzer.summarize(test_text.strip())
    
    print(f"요약: {summary}")
    print("=" * 60)
