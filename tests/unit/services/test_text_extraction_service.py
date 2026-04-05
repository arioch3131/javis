from __future__ import annotations

import builtins
import hashlib
import io
import types
from types import SimpleNamespace

import pytest

from ai_content_classifier.services.preprocessing.text_extraction_service import (
    TextExtractionResult,
    TextExtractionService,
)


class _DummyCache:
    def __init__(self) -> None:
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        return True

    def clear(self):
        self.data.clear()

    def size(self):
        return len(self.data)


class _DummyRuntime:
    def __init__(self) -> None:
        self.cache = _DummyCache()

    def memory_cache(self, _namespace, default_ttl=600):
        _ = default_ttl
        return self.cache


@pytest.fixture
def service(monkeypatch):
    runtime = _DummyRuntime()
    monkeypatch.setattr(
        "ai_content_classifier.services.preprocessing.text_extraction_service.get_cache_runtime",
        lambda: runtime,
    )
    svc = TextExtractionService()
    svc.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        debug=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    return svc


def test_detect_file_format(service):
    assert service._detect_file_format("a.txt") == "text"
    assert service._detect_file_format("a.md") == "markdown"
    assert service._detect_file_format("a.csv") == "csv"
    assert service._detect_file_format("a.pdf") == "pdf"
    assert service._detect_file_format("a.docx") == "docx"
    assert service._detect_file_format("a.rtf") == "rtf"
    assert service._detect_file_format("a.odt") == "odt"
    assert service._detect_file_format("a.unknown") == "unknown"


def test_extract_plain_text_success_and_fallback_encoding(service, monkeypatch):
    service.config.encoding_fallbacks = ["utf-8", "latin-1"]

    calls = {"count": 0}
    real_open = builtins.open

    def fake_open(*args, **kwargs):
        calls["count"] += 1
        if kwargs.get("encoding") == "utf-8":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        return io.StringIO("hello world")

    monkeypatch.setattr("builtins.open", fake_open)
    text, method, pages, encoding, warnings = service._extract_plain_text("/tmp/a.txt")
    assert text == "hello world"
    assert method == "plain_text"
    assert pages == 1
    assert encoding == "latin-1"
    assert warnings == []
    assert calls["count"] == 2
    monkeypatch.setattr("builtins.open", real_open)


def test_extract_plain_text_failure_raises(service, monkeypatch):
    service.config.encoding_fallbacks = ["utf-8", "latin-1"]
    monkeypatch.setattr(
        "builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )
    with pytest.raises(Exception, match="Unable to read file"):
        service._extract_plain_text("/tmp/a.txt")


def test_extract_pdf_text_resolution_paths(service):
    service._available_extractors = {"pypdf": True, "pdfminer": True, "textract": True}

    service._extract_pdf_pypdf = lambda _p: ("pypdf text", 2)
    assert service._extract_pdf_text("/tmp/a.pdf")[1] == "pypdf"

    service._extract_pdf_pypdf = lambda _p: (" ", 2)
    service._extract_pdf_pdfminer = lambda _p: "pdfminer text"
    assert service._extract_pdf_text("/tmp/a.pdf")[1] == "pdfminer"

    service._extract_pdf_pdfminer = lambda _p: " "
    service._extract_with_textract = lambda _p: "textract text"
    assert service._extract_pdf_text("/tmp/a.pdf")[1] == "textract"


def test_extract_pdf_text_raises_when_no_method_available(service):
    service._available_extractors = {
        "pypdf": False,
        "pdfminer": False,
        "textract": False,
    }
    with pytest.raises(Exception, match="Noe method d'extraction PDF disponible"):
        service._extract_pdf_text("/tmp/a.pdf")


def test_extract_pdf_pypdf(service, monkeypatch):
    fake_page_ok = SimpleNamespace(extract_text=lambda: "page one")

    def _bad_extract():
        raise RuntimeError("page error")

    fake_page_bad = SimpleNamespace(extract_text=_bad_extract)
    fake_reader = SimpleNamespace(pages=[fake_page_ok, fake_page_bad])
    fake_pypdf = types.SimpleNamespace(PdfReader=lambda _f: fake_reader)
    monkeypatch.setitem(__import__("sys").modules, "pypdf", fake_pypdf)
    monkeypatch.setattr("builtins.open", lambda *a, **k: io.BytesIO(b"%PDF"))

    text, pages = service._extract_pdf_pypdf("/tmp/a.pdf")
    assert pages == 2
    assert "page one" in text


def test_extract_docx_text_paths(service, monkeypatch):
    service._available_extractors = {"docx": True, "textract": True}
    fake_doc = SimpleNamespace(
        paragraphs=[SimpleNamespace(text="p1"), SimpleNamespace(text="p2")],
        tables=[
            SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        cells=[SimpleNamespace(text="c1"), SimpleNamespace(text="c2")]
                    )
                ]
            )
        ],
    )
    fake_docx = types.SimpleNamespace(Document=lambda _p: fake_doc)
    monkeypatch.setitem(__import__("sys").modules, "docx", fake_docx)

    text, method, *_ = service._extract_docx_text("/tmp/a.docx")
    assert method == "python_docx"
    assert "p1" in text

    service._available_extractors = {"docx": False, "textract": True}
    service._extract_with_textract = lambda _p: "fallback"
    assert service._extract_docx_text("/tmp/a.docx")[1] == "textract_fallback"


def test_extract_rtf_text_paths(service, monkeypatch):
    service._available_extractors = {"striprtf": True, "textract": True}
    fake_striprtf_mod = types.SimpleNamespace(
        rtf_to_text=lambda s: s.replace("{", "").replace("}", "")
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "striprtf",
        types.SimpleNamespace(striprtf=fake_striprtf_mod),
    )
    monkeypatch.setitem(
        __import__("sys").modules, "striprtf.striprtf", fake_striprtf_mod
    )
    monkeypatch.setattr("builtins.open", lambda *a, **k: io.StringIO("{hello}"))
    assert service._extract_rtf_text("/tmp/a.rtf")[1] == "striprtf"

    service._available_extractors = {"striprtf": False, "textract": False}
    service._extract_plain_text = lambda _p: ("{\\b hi}", "plain_text", 1, "utf-8", [])
    text, method, *_ = service._extract_rtf_text("/tmp/a.rtf")
    assert method == "rtf_basic"
    assert "hi" in text


def test_legacy_doc_and_odt_paths(service):
    service._available_extractors = {"textract": True}
    service._extract_with_textract = lambda _p: "x"
    assert service._extract_legacy_doc("/tmp/a.doc")[1] == "textract"
    assert service._extract_odt_text("/tmp/a.odt")[1] == "textract"

    service._available_extractors = {"textract": False}
    with pytest.raises(Exception, match="Legacy DOC extraction requires textract"):
        service._extract_legacy_doc("/tmp/a.doc")
    with pytest.raises(Exception, match="ODT extraction requires textract"):
        service._extract_odt_text("/tmp/a.odt")


def test_extract_fallback_paths(service):
    service._available_extractors = {"textract": True}
    service._extract_with_textract = lambda _p: "fallback-text"
    assert service._extract_fallback("/tmp/a.bin")[1] == "textract_fallback"

    service._available_extractors = {"textract": False}
    service._extract_plain_text = lambda _p: (
        "bin\x00text",
        "plain_text",
        1,
        "utf-8",
        [],
    )
    text, method, *_ = service._extract_fallback("/tmp/a.bin")
    assert method == "raw_fallback"
    assert "bin" in text

    service._extract_plain_text = lambda _p: (_ for _ in ()).throw(
        RuntimeError("failed")
    )
    with pytest.raises(Exception, match="All extraction methods failed"):
        service._extract_fallback("/tmp/a.bin")


def test_extract_by_format_success_empty_and_exception(service):
    start = 0.0
    service._post_process_text = lambda text, _max: text[:4]
    service._extract_plain_text = lambda _p: ("abcdef", "plain_text", 1, "utf-8", [])
    res = service._extract_by_format("/tmp/a.txt", "text", 4, start)
    assert res.success is True
    assert res.final_length == 4

    service._extract_plain_text = lambda _p: ("", "plain_text", 1, "utf-8", [])
    res2 = service._extract_by_format("/tmp/a.txt", "text", 4, start)
    assert res2.success is False

    service._extract_plain_text = lambda _p: (_ for _ in ()).throw(RuntimeError("x"))
    res3 = service._extract_by_format("/tmp/a.txt", "text", 4, start)
    assert res3.success is False
    assert "Erreur" in (res3.error_message or "")


def test_post_process_cleaners_and_cache_key(service, monkeypatch):
    service.config.clean_whitespace = True
    service.config.preserve_line_breaks = True
    service.config.strip_binary_artifacts = True
    out = service._post_process_text("a   b\n\n\nc\x00", max_length=10)
    assert "a b" in out

    service.config.preserve_line_breaks = False
    out2 = service._post_process_text("a   \n b", max_length=10)
    assert "\n" not in out2

    assert service._clean_rtf_artifacts("{\\b test}") is not None
    assert service._clean_binary_artifacts("abc\x00def").startswith("abc")

    monkeypatch.setattr("os.path.getmtime", lambda _p: 123.0)
    key = service._generate_cache_key("/tmp/a.txt", 50)
    assert key == hashlib.md5("/tmp/a.txt_50_123.0".encode()).hexdigest()

    monkeypatch.setattr(
        "os.path.getmtime", lambda _p: (_ for _ in ()).throw(OSError("x"))
    )
    assert isinstance(service._generate_cache_key("/tmp/a.txt", 50), str)


def test_extract_text_for_llm_cache_hit_success_and_error(service):
    cached = TextExtractionResult(
        success=True, text="cached", extraction_method="cache"
    )
    service._extraction_cache.set("k", cached)
    service._generate_cache_key = lambda _p, _m: "k"
    got = service.extract_text_for_llm("/tmp/a.txt")
    assert got.text == "cached"
    assert service._stats["cache_hits"] >= 1

    service._generate_cache_key = lambda _p, _m: "k2"
    service._detect_file_format = lambda _p: "text"
    service._extract_by_format = lambda *_a: TextExtractionResult(
        success=True, text="ok", processing_time=0.1
    )
    got2 = service.extract_text_for_llm("/tmp/a.txt")
    assert got2.success is True

    service._extract_by_format = lambda *_a: (_ for _ in ()).throw(RuntimeError("boom"))
    service._generate_cache_key = lambda _p, _m: "k3"
    got3 = service.extract_text_for_llm("/tmp/a.txt")
    assert got3.success is False
    assert "Erreur extraction texte" in (got3.error_message or "")


def test_public_stats_formats_and_clear(service):
    service._available_extractors = {
        "pypdf": True,
        "pdfminer": False,
        "docx": True,
        "striprtf": True,
        "textract": True,
    }
    service._update_stats(
        TextExtractionResult(success=True, processing_time=1.0), "pdf"
    )
    service._update_stats(
        TextExtractionResult(success=False, processing_time=1.0), "txt"
    )

    formats = service.get_supported_formats()
    assert "pdf" in formats
    assert "docx" in formats
    assert "rtf" in formats
    assert "txt" in formats

    service._cache_result("x", TextExtractionResult(success=True))
    assert service._extraction_cache.size() == 1
    stats = service.get_stats()
    assert stats["extractions_performed"] == 2
    assert "supported_formats" in stats

    service.clear_cache()
    assert service._extraction_cache.size() == 0
