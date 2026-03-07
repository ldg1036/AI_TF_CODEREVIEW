"""
CtrlppCheck 자동 업데이트 모듈

GitHub 저장소에서 최신 버전을 확인하고 업데이트하는 기능을 제공합니다.
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import threading
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


@dataclass
class VersionInfo:
    """버전 정보 데이터 클래스"""
    version: str
    release_date: str
    release_notes: str
    download_url: Optional[str] = None


class CtrlppCheckUpdater:
    """CtrlppCheck 업데이트 관리 클래스"""
    
    GITHUB_API = "https://api.github.com/repos/siemens/CtrlppCheck/releases/latest"
    GITHUB_RELEASES = "https://github.com/siemens/CtrlppCheck/releases"
    
    def __init__(self, install_dir: str = None):
        """
        초기화
        
        Args:
            install_dir: CtrlppCheck 설치 디렉토리 (기본값: 현재 파일 기준 상대 경로)
        """
        if install_dir is None:
            # 기본 설치 경로
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            install_dir = os.path.join(base_dir, "tools", "CtrlppCheck")
        
        self.install_dir = install_dir
        self.version_file = os.path.join(install_dir, "version.txt")
        self.download_dir = os.path.join(install_dir, "download")
        self.extract_dir = os.path.join(install_dir, "extract")
        
        # 네트워크 타임아웃 설정
        self.timeout = 30
        
    def get_current_version(self) -> str:
        """
        현재 설치된 버전 확인
        
        Returns:
            현재 버전 문자열 (예: v1.0.2)
        """
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass
        return "v0.0.0"
    
    def save_version(self, version: str) -> bool:
        """
        버전 정보 저장
        
        Args:
            version: 저장할 버전 문자열
            
        Returns:
            성공 여부
        """
        try:
            os.makedirs(os.path.dirname(self.version_file), exist_ok=True)
            with open(self.version_file, 'w', encoding='utf-8') as f:
                f.write(version)
            return True
        except Exception as e:
            print(f"버전 저장 실패: {e}")
            return False
    
    def check_latest_version(self) -> Optional[VersionInfo]:
        """
        GitHub에서 최신 릴리스 버전 확인
        
        Returns:
            VersionInfo 객체 또는 None (실패 시)
        """
        if not REQUESTS_AVAILABLE:
            print("requests 모듈이 설치되지 않았습니다.")
            print("pip install requests")
            return None
        
        try:
            response = requests.get(
                self.GITHUB_API,
                timeout=self.timeout,
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Windows용 다운로드 URL 찾기
            download_url = None
            for asset in data.get('assets', []):
                name = asset.get('name', '').lower()
                if 'win' in name or 'windows' in name:
                    download_url = asset.get('browser_download_url')
                    break
            
            return VersionInfo(
                version=data.get('tag_name', 'unknown'),
                release_date=data.get('published_at', 'unknown'),
                release_notes=data.get('body', '릴리스 노트 없음'),
                download_url=download_url
            )
            
        except requests.exceptions.Timeout:
            print("GitHub API 요청 시간 초과")
            return None
        except requests.exceptions.RequestException as e:
            print(f"GitHub API 요청 실패: {e}")
            return None
        except json.JSONDecodeError:
            print("GitHub API 응답 파싱 실패")
            return None
    
    def compare_versions(self, current: str, latest: str) -> int:
        """
        버전 비교
        
        Args:
            current: 현재 버전
            latest: 최신 버전
            
        Returns:
            -1: 최신 버전이 더 높음
             0: 동일
             1: 현재 버전이 더 높음
        """
        def parse_version(v: str) -> Tuple[int, ...]:
            # v1.0.2 -> (1, 0, 2)
            v = v.lstrip('vV')
            try:
                return tuple(int(x) for x in v.split('.'))
            except ValueError:
                return (0,)
        
        current_parts = parse_version(current)
        latest_parts = parse_version(latest)
        
        if current_parts < latest_parts:
            return -1
        elif current_parts > latest_parts:
            return 1
        return 0
    
    def download_update(self, download_url: str, progress_callback=None) -> Optional[str]:
        """
        업데이트 다운로드
        
        Args:
            download_url: 다운로드 URL
            progress_callback: 진행률 콜백 함수 (0-100)
            
        Returns:
            다운로드된 파일 경로 또는 None
        """
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            
            # 파일명 추출
            filename = download_url.split('/')[-1]
            filepath = os.path.join(self.download_dir, filename)
            
            # 다운로드
            response = requests.get(download_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress)
            
            return filepath
            
        except Exception as e:
            print(f"다운로드 실패: {e}")
            return None
    
    def install_update(self, zip_path: str) -> bool:
        """
        업데이트 설치
        
        Args:
            zip_path: 다운로드된 zip 파일 경로
            
        Returns:
            설치 성공 여부
        """
        try:
            # 기존 버전 백업
            backup_dir = f"{self.extract_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(self.extract_dir):
                shutil.copytree(self.extract_dir, backup_dir)
            
            # 압축 해제
            temp_extract = tempfile.mkdtemp(prefix="ctrlppcheck_")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
            
            # 새 버전 설치
            if os.path.exists(self.extract_dir):
                shutil.rmtree(self.extract_dir)
            
            # 압축 해제된 내용물 찾기 (보통 하위 디렉토리에 있음)
            extracted_items = os.listdir(temp_extract)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract, extracted_items[0])):
                # 단일 디렉토리인 경우
                shutil.move(os.path.join(temp_extract, extracted_items[0]), self.extract_dir)
            else:
                # 직접 이동
                shutil.move(temp_extract, self.extract_dir)
            
            # 임시 정리
            if os.path.exists(temp_extract):
                shutil.rmtree(temp_extract, ignore_errors=True)
            
            return True
            
        except Exception as e:
            print(f"설치 실패: {e}")
            # 롤백 시도
            if 'backup_dir' in locals() and os.path.exists(backup_dir):
                if os.path.exists(self.extract_dir):
                    shutil.rmtree(self.extract_dir)
                shutil.move(backup_dir, self.extract_dir)
            return False
    
    def get_exe_path(self) -> str:
        """
        ctrlppcheck.exe 경로 반환
        
        Returns:
            exe 파일 경로
        """
        return os.path.join(self.extract_dir, "WinCCOA_QualityChecks", "bin", "ctrlppcheck", "ctrlppcheck.exe")


class UpdateDialog:
    """업데이트 알림 대화상자 클래스"""
    
    def __init__(self, current_version: str, latest_info: VersionInfo, updater: CtrlppCheckUpdater):
        self.current_version = current_version
        self.latest_info = latest_info
        self.updater = updater
        self.result = None  # 'update', 'later', 'skip'
        self.root = None
        
    def show(self) -> str:
        """
        대화상자 표시
        
        Returns:
            'update', 'later', 'skip' 중 하나
        """
        if not TKINTER_AVAILABLE:
            # CLI 모드
            return self._show_cli()
        
        return self._show_gui()
    
    def _show_gui(self) -> str:
        """GUI 대화상자 표시"""
        self.root = tk.Tk()
        self.root.title("🔔 CtrlppCheck 업데이트 알림")
        self.root.geometry("450x400")
        self.root.resizable(False, False)
        
        # 아이콘 설정 (있는 경우)
        try:
            self.root.iconbitmap(default='')  # 기본 아이콘
        except Exception:
            pass
        
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 제목
        title_label = ttk.Label(
            main_frame,
            text="🆕 새 버전이 있습니다!",
            font=("맑은 고딕", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # 버전 정보 프레임
        version_frame = ttk.LabelFrame(main_frame, text="버전 정보", padding="10")
        version_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            version_frame,
            text=f"현재 버전: {self.current_version}",
            font=("맑은 고딕", 10)
        ).pack(anchor=tk.W)
        
        ttk.Label(
            version_frame,
            text=f"최신 버전: {self.latest_info.version}",
            font=("맑은 고딕", 10, "bold"),
            foreground="blue"
        ).pack(anchor=tk.W)
        
        ttk.Label(
            version_frame,
            text=f"릴리스 날짜: {self.latest_info.release_date[:10] if self.latest_info.release_date else 'N/A'}",
            font=("맑은 고딕", 9)
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # 릴리스 노트 프레임
        notes_frame = ttk.LabelFrame(main_frame, text="변경 사항", padding="10")
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 릴리스 노트 텍스트
        notes_text = scrolledtext.ScrolledText(
            notes_frame,
            height=8,
            wrap=tk.WORD,
            font=("맑은 고딕", 9)
        )
        notes_text.pack(fill=tk.BOTH, expand=True)
        notes_text.insert(tk.END, self.latest_info.release_notes or "릴리스 노트 없음")
        notes_text.config(state=tk.DISABLED)
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 버튼 스타일
        style = ttk.Style()
        style.configure('Accent.TButton', font=("맑은 고딕", 10, "bold"))
        
        ttk.Button(
            button_frame,
            text="📥 업데이트",
            style='Accent.TButton',
            command=self._on_update,
            width=12
        ).pack(side=tk.LEFT, padx=5, expand=True)
        
        ttk.Button(
            button_frame,
            text="⏰ 나중에",
            command=self._on_later,
            width=12
        ).pack(side=tk.LEFT, padx=5, expand=True)
        
        ttk.Button(
            button_frame,
            text="⏭️ 건너뛰기",
            command=self._on_skip,
            width=12
        ).pack(side=tk.LEFT, padx=5, expand=True)
        
        # 창 중앙 배치
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # 모달로 표시
        self.root.transient()
        self.root.grab_set()
        
        self.root.mainloop()
        
        return self.result
    
    def _on_update(self):
        """업데이트 버튼 클릭"""
        self.result = 'update'
        self.root.destroy()
    
    def _on_later(self):
        """나중에 버튼 클릭"""
        self.result = 'later'
        self.root.destroy()
    
    def _on_skip(self):
        """건너뛰기 버튼 클릭"""
        self.result = 'skip'
        self.root.destroy()
    
    def _show_cli(self) -> str:
        """CLI 모드 대화상자"""
        print("\n" + "=" * 50)
        print("🔔 CtrlppCheck 업데이트 알림")
        print("=" * 50)
        print(f"\n현재 버전: {self.current_version}")
        print(f"최신 버전: {self.latest_info.version}")
        print(f"\n변경 사항:")
        print("-" * 40)
        print(self.latest_info.release_notes or "릴리스 노트 없음")
        print("-" * 40)
        print("\n업데이트하시겠습니까?")
        print("  1. 업데이트")
        print("  2. 나중에")
        print("  3. 건너뛰기")
        
        while True:
            choice = input("\n선택 (1/2/3): ").strip()
            if choice == '1':
                return 'update'
            elif choice == '2':
                return 'later'
            elif choice == '3':
                return 'skip'
            print("잘못된 입력입니다. 1, 2, 3 중 하나를 선택하세요.")


class UpdateProgressDialog:
    """업데이트 진행 대화상자"""
    
    def __init__(self, parent=None):
        self.root = None
        self.progress_var = None
        self.status_var = None
        self.parent = parent
        
    def show(self):
        """대화상자 표시"""
        if not TKINTER_AVAILABLE:
            return
        
        self.root = tk.Toplevel(self.parent)
        self.root.title("CtrlppCheck 업데이트")
        self.root.geometry("400x150")
        self.root.resizable(False, False)
        self.root.transient(self.parent)
        self.root.grab_set()
        
        # 진행률 표시
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            main_frame,
            text="업데이트 진행 중...",
            font=("맑은 고딕", 11)
        ).pack(pady=(0, 10))
        
        self.status_var = tk.StringVar(value="다운로드 준비 중...")
        ttk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("맑은 고딕", 9)
        ).pack(pady=(0, 10))
        
        self.progress_var = tk.DoubleVar(value=0)
        progress = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100,
            length=350,
            mode='determinate'
        )
        progress.pack(pady=(0, 10))
        
        # 창 중앙 배치
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self.root.update()
    
    def update_progress(self, value: int, status: str = None):
        """진행률 업데이트"""
        if self.root:
            self.progress_var.set(value)
            if status:
                self.status_var.set(status)
            self.root.update()
    
    def close(self):
        """대화상자 닫기"""
        if self.root:
            self.root.destroy()
            self.root = None


def check_and_update(auto_check: bool = False) -> Tuple[bool, str]:
    """
    업데이트 확인 및 수행
    
    Args:
        auto_check: 자동 체크 모드 (사용자 개입 없이 체크만)
        
    Returns:
        (업데이트 수행 여부, 메시지)
    """
    updater = CtrlppCheckUpdater()
    
    # 현재 버전 확인
    current_version = updater.get_current_version()
    print(f"현재 버전: {current_version}")
    
    # 최신 버전 확인
    print("GitHub에서 최신 버전 확인 중...")
    latest_info = updater.check_latest_version()
    
    if latest_info is None:
        return False, "GitHub에서 버전 정보를 가져올 수 없습니다."
    
    print(f"최신 버전: {latest_info.version}")
    
    # 버전 비교
    comparison = updater.compare_versions(current_version, latest_info.version)
    
    if comparison >= 0:
        # 이미 최신 버전
        if not auto_check:
            if TKINTER_AVAILABLE:
                messagebox.showinfo(
                    "CtrlppCheck",
                    f"이미 최신 버전입니다.\n\n현재 버전: {current_version}"
                )
            else:
                print("이미 최신 버전입니다.")
        return False, "이미 최신 버전입니다."
    
    # 업데이트 필요
    if auto_check:
        # 자동 체크 모드에서는 알림만
        return True, f"새 버전 {latest_info.version}이(가) 있습니다."
    
    # 사용자 확인
    dialog = UpdateDialog(current_version, latest_info, updater)
    result = dialog.show()
    
    if result != 'update':
        return False, "업데이트가 취소되었습니다."
    
    # 다운로드 URL 확인
    if not latest_info.download_url:
        # 브라우저로 릴리스 페이지 열기
        if TKINTER_AVAILABLE:
            messagebox.showwarning(
                "CtrlppCheck",
                f"자동 다운로드를 지원하지 않는 버전입니다.\n"
                f"GitHub 릴리스 페이지에서 수동으로 다운로드하세요.\n\n{updater.GITHUB_RELEASES}"
            )
        else:
            print(f"자동 다운로드 불가. 수동 다운로드: {updater.GITHUB_RELEASES}")
        
        # 브라우저 열기
        import webbrowser
        webbrowser.open(updater.GITHUB_RELEASES)
        return False, "수동 다운로드 필요"
    
    # 진행 대화상자 표시
    progress_dialog = UpdateProgressDialog()
    progress_dialog.show()
    
    try:
        # 다운로드
        progress_dialog.update_progress(0, "다운로드 중...")
        
        def progress_callback(value):
            progress_dialog.update_progress(value, f"다운로드 중... {value}%")
        
        zip_path = updater.download_update(latest_info.download_url, progress_callback)
        
        if not zip_path:
            progress_dialog.close()
            return False, "다운로드 실패"
        
        # 설치
        progress_dialog.update_progress(90, "설치 중...")
        
        if updater.install_update(zip_path):
            # 버전 저장
            updater.save_version(latest_info.version)
            
            progress_dialog.update_progress(100, "완료!")
            progress_dialog.close()
            
            if TKINTER_AVAILABLE:
                messagebox.showinfo(
                    "CtrlppCheck",
                    f"업데이트 완료!\n\n"
                    f"버전: {current_version} → {latest_info.version}"
                )
            
            return True, f"업데이트 완료: {latest_info.version}"
        else:
            progress_dialog.close()
            return False, "설치 실패"
            
    except Exception as e:
        progress_dialog.close()
        return False, f"업데이트 오류: {e}"


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CtrlppCheck 업데이트 관리자')
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='업데이트 확인만 수행'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='사용자 확인 없이 업데이트'
    )
    parser.add_argument(
        '--cli',
        action='store_true',
        help='CLI 모드 (GUI 없음)'
    )
    
    args = parser.parse_args()
    
    if args.cli:
        global TKINTER_AVAILABLE
        TKINTER_AVAILABLE = False
    
    if args.check:
        # 체크만
        success, message = check_and_update(auto_check=True)
        print(f"\n{message}")
        sys.exit(0 if not success else 1)  # 업데이트 있으면 exit code 1
    else:
        # 업데이트 수행
        success, message = check_and_update(auto_check=args.force)
        print(f"\n{message}")
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
