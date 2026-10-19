# -*- coding: utf-8 -*-
"""纯离线单元测试：不依赖网络/数据库/大模型，CI 可直接跑。

执行方式（项目根目录）：
    python -m pytest tests/test_units.py -v
"""
import os

import pytest

from app.config import DATA_DIR, LOG_DIR, PROJECT_ROOT
from app.gateway.security import is_local_origin
from app.gateway.mcp_store import safe_temp_upload
from app.services.embedding_service import cosine_similarity, text_splitter


# ---------------- 余弦相似度 ----------------
class TestCosineSimilarity:
    def test_identical_vectors_is_one(self):
        assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_is_zero(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0, abs=1e-6)

    def test_empty_vector_returns_zero(self):
        assert cosine_similarity([], [1, 2]) == 0.0
        assert cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_dim_mismatch_returns_zero(self):
        assert cosine_similarity([1, 2, 3], [1, 2]) == 0.0


# ---------------- CORS 白名单 ----------------
class TestCorsOrigin:
    @pytest.mark.parametrize("origin", [
        "http://localhost:3100",
        "http://127.0.0.1:8501",
        "http://localhost",
    ])
    def test_local_origin_allowed(self, origin):
        assert is_local_origin(origin) is True

    @pytest.mark.parametrize("origin", [
        "",
        "http://evil.com",
        "https://localhost:3100",          # https 不放行
        "http://localhost.evil.com",       # 伪装后缀
        "http://192.168.1.10:3100",        # 内网其它主机
    ])
    def test_non_local_origin_rejected(self, origin):
        assert is_local_origin(origin) is False


# ---------------- 上传安全 ----------------
class TestSafeTempUpload:
    def test_reject_dangerous_ext(self):
        with pytest.raises(ValueError):
            safe_temp_upload("../evil.exe")

    def test_allow_pdf_and_randomize_name(self):
        path = safe_temp_upload("简历.pdf")
        try:
            assert os.path.exists(path)
            assert path.lower().endswith(".pdf")
            assert os.path.dirname(path) == DATA_DIR
            # 随机文件名，不得保留用户提供的原始名字（防路径穿越）
            assert "简历" not in os.path.basename(path)
        finally:
            if os.path.exists(path):
                os.remove(path)


# ---------------- 分片器 ----------------
class TestTextSplitter:
    def test_long_text_split_to_multiple_chunks(self):
        text = "这是一段中文简历内容。" * 100
        chunks = text_splitter.split_text(text)
        assert len(chunks) >= 2
        assert all(len(c) > 0 for c in chunks)


# ---------------- 配置路径 ----------------
class TestConfigPaths:
    def test_project_paths_are_absolute(self):
        assert os.path.isabs(PROJECT_ROOT)
        assert os.path.basename(DATA_DIR) == "data"
        assert os.path.basename(LOG_DIR) == "logs"
