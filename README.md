# Javis

> 🇫🇷 [Version française](README.fr.md)

Automatic classification and organization of content (documents, images, etc.) using local AI models via Ollama, with a PyQt6 interface.

## Documentation

- Architecture (EN): `docs/ARCHITECTURE_V1.md`
- Architecture (FR): `docs/ARCHITECTURE_V1.fr.md`
- Functionalities (EN): `docs/FUNCTIONALITIES_V1.md`
- Functionalities (FR): `docs/FUNCTIONALITIES_V1.fr.md`

## Project Status

This is a personal project maintained in spare time.  
Issues and Pull Requests are welcome, but response/review times may be slow and are not guaranteed.

## Support Policy

- No SLA, no guaranteed support, and no guaranteed response time.
- Maintenance is best-effort and opportunistic.
- Community contributions are welcome, but merge/review timing depends on availability.

## Disclaimer

- This software is provided "as is", without warranty of any kind, express or implied.
- You use this project at your own risk.
- The author is not liable for any direct, indirect, incidental, or consequential damages, including data loss, business interruption, or security issues.

---

## Prerequisites

### Ubuntu 24.04

#### PyQt6 system packages

```bash
sudo apt update
sudo apt install -y python3-pyqt6
sudo apt install -y qt6-qpa-plugins libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1
```

#### Optional Qt modules

```bash
sudo apt install -y python3-pyqt6.qtsvg python3-pyqt6.qtwebengine
```

#### Verify installation

```bash
python3 -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```

#### Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Application

```bash
git clone https://github.com/arioch3131/ai-content-classifier.git
cd ai-content-classifier
pip install .
python main.py
```

---

### Windows

#### Ollama

Download and install from https://ollama.com/download/windows

#### Application

Download the latest installer from the
[Releases page](https://github.com/arioch3131/ai-content-classifier/releases)
and run `Javis_setup.exe`.

No Python required for the installer build.

---

## Recommended AI Models

Pull models with `ollama pull <model>`.

### Images (vision)

| Model | Size | Min RAM | Min VRAM | Notes |
|---|---|---|---|---|
| `moondream` | ~1.5 GB | 4 GB | 2 GB | Ultra light, basic classification |
| `llava:7b` | ~4 GB | 8 GB | 6 GB | Recommended, good balance |
| `llava:13b` | ~8 GB | 16 GB | 10 GB | Best accuracy |

### Documents (text)

| Model | Size | Min RAM | Min VRAM | Notes |
|---|---|---|---|---|
| `gemma3:4b` | ~3 GB | 8 GB | 4 GB | Ultra light, basic classification |
| `llama3:8b` | ~5 GB | 8 GB | 6 GB | Recommended, fast and accurate |
| `gemma3:12b` | ~8 GB | 16 GB | 10 GB | Best accuracy |

> Without a dedicated GPU (dedicated VRAM), AI categorization is currently not suitable:
> on CPU-only laptops/workstations or shared-memory GPUs, inference time can become very high.
> Models can be selected in application settings.

---

## Tests

```bash
.venv/bin/python -m pytest -q
```

Headless Qt mode is auto-configured for tests via `tests/conftest.py`.

---

## Internationalization (i18n)

The application supports English and French:

- Language configurable via `general.language` (`en`, `fr`)
- Automatic fallback to `en`
- Catalogs: `src/ai_content_classifier/resources/i18n/en.json` and `fr.json`
- Service: `src/ai_content_classifier/services/i18n/i18n_service.py`

To add a translation:

1. Add keys/values in `en.json`
2. Add equivalents in `fr.json` (or another language)
3. Use `tr("namespace.key", "Default text")` in UI code

---

## License

GPL-3.0-only
