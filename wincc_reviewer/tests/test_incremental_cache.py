"""
Phase 2 SHA256 해시 기반 점진적 검사 캐시(Incremental Cache) 단위 테스트.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.pipeline import Pipeline, PipelineConfig


class TestIncrementalCache:
    """점진적 리뷰 캐시 저장 및 로드, 변경 감지 테스트."""

    def test_cache_miss_and_save_on_first_run(self, tmp_path: Path):
        sample_dir = tmp_path / "scripts"
        sample_dir.mkdir(parents=True)
        file1 = sample_dir / "test1.ctl"
        file1.write_text("main() {\n    delay(0.1);\n}\n", encoding="utf-8")

        cfg = PipelineConfig(input_path=sample_dir, output_dir=tmp_path / "out", use_cache=True)
        pipeline = Pipeline(cfg)

        # 첫 번째 실행: 캐시 파일 없음 -> 검사 수행 (cache miss = 1, cache hit = 0) 및 캐시 저장
        report1 = pipeline.run()
        assert report1.metrics.file_count == 1
        assert report1.metrics.cache_misses.get("files") == 1
        assert report1.metrics.cache_hits.get("files") == 0

        cache_path = pipeline._get_cache_file_path()
        assert cache_path.exists()

        with open(cache_path, encoding="utf-8") as f:
            cache_data = json.load(f)

        str_path = str(file1.resolve())
        assert str_path in cache_data
        assert len(cache_data[str_path]["sha256"]) == 64  # SHA256 length

    def test_cache_hit_on_second_run_with_unchanged_file(self, tmp_path: Path):
        sample_dir = tmp_path / "scripts"
        sample_dir.mkdir(parents=True)
        file1 = sample_dir / "test_hit.ctl"
        file1.write_text("main() {\n    int a = 100;\n}\n", encoding="utf-8")

        cfg = PipelineConfig(input_path=sample_dir, output_dir=tmp_path / "out", use_cache=True)
        pipeline = Pipeline(cfg)

        # 1차 실행 -> cache miss 1건, cache hit 0건
        report1 = pipeline.run()
        assert report1.metrics.cache_misses.get("files") == 1
        assert report1.metrics.cache_hits.get("files") == 0

        # 2차 실행 (파일 변경 없음) -> 해시 일치로 cache hit 1건, cache miss 0건 검증
        report2 = pipeline.run()
        assert report2.metrics.cache_hits.get("files") == 1
        assert report2.metrics.cache_misses.get("files") == 0

    def test_cache_invalidation_when_file_content_changes(self, tmp_path: Path):
        sample_dir = tmp_path / "scripts"
        sample_dir.mkdir(parents=True)
        file1 = sample_dir / "test_change.ctl"
        file1.write_text("main() {\n    int a = 1;\n}\n", encoding="utf-8")

        cfg = PipelineConfig(input_path=sample_dir, output_dir=tmp_path / "out", use_cache=True)
        pipeline = Pipeline(cfg)

        # 1차 실행 -> cache miss 1건
        report1 = pipeline.run()
        assert report1.metrics.cache_misses.get("files") == 1

        # 파일 수정 -> SHA256 해시 변경
        file1.write_text("main() {\n    int a = 2; // modified\n}\n", encoding="utf-8")

        # 2차 실행 -> 해시 불일치로 캐시 미스 발생 (cache miss 1건, cache hit 0건)
        report2 = pipeline.run()
        assert report2.metrics.cache_misses.get("files") == 1
        assert report2.metrics.cache_hits.get("files") == 0
