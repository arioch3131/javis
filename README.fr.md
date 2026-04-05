# Javis

> 🇬🇧 [English version](README.md)

Javis est une application desktop qui aide a classifier et organiser de grandes
bibliotheques de fichiers mixtes (documents, images, etc.) avec des modeles d'IA
locaux, sans cloud obligatoire.

> **Projet personnel** maintenu sur le temps libre. Les issues et PR sont les
> bienvenues, mais les delais de reponse ne sont pas garantis.

---

## Pourquoi Javis

Vous avez des milliers de fichiers disperses entre dossiers et disques externes.
Les trier a la main prend des heures. Javis scanne vos dossiers, extrait les
metadonnees, puis laisse un modele IA local categoriser chaque fichier
automatiquement, avant de vous aider a organiser l'ensemble.

- **Inference locale** : les donnees restent sur votre machine.
- **Bibliotheques mixtes** : images et documents dans le meme espace.
- **Flux unique** : scan -> categorisation -> organisation.

---

## Captures d'ecran

| Vue principale | Categorisation en cours |
|---|---|
| <img src="docs/assets/demo3.png" alt="Vue grille avec fichiers scannes" width="420"/> | <img src="docs/assets/demo1.png" alt="Categorisation en cours avec details de progression" width="420"/> |

| Rapport de categorisation | Detail fichier avec classification IA |
|---|---|
| <img src="docs/assets/demo2.png" alt="Rapport de categorisation par categorie" width="420"/> | <img src="docs/assets/demo4.png" alt="Panneau detail fichier avec categorie IA et score de confiance" width="420"/> |

---

## Demarrage rapide

1. Installer [Ollama](https://ollama.com) puis telecharger des modeles :
```bash
   ollama pull llava:7b    # pour les images
   ollama pull llama3:8b   # pour les documents
```
2. Installer et lancer Javis (voir [Prerequis](#prerequis) selon votre OS).
3. Cliquer sur **Scan Folder**, puis **Categorize**.

---

## Documentation

- Architecture (EN): `docs/ARCHITECTURE_V1.md`
- Architecture (FR): `docs/ARCHITECTURE_V1.fr.md`
- Functionalities (EN): `docs/FUNCTIONALITIES_V1.md`
- Functionalities (FR): `docs/FUNCTIONALITIES_V1.fr.md`

---

## Prerequis

### Ubuntu 24.04

#### Paquets systeme PyQt6
```bash
sudo apt update
sudo apt install -y python3-pyqt6
sudo apt install -y qt6-qpa-plugins libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1
```

#### Modules Qt optionnels
```bash
sudo apt install -y python3-pyqt6.qtsvg python3-pyqt6.qtwebengine
```

#### Verification
```bash
python3 -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```

#### Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Application

```bash
git clone https://github.com/arioch3131/javis.git
cd javis
pip install .
python src/ai_content_classifier/main.py
```

---

### Windows

#### Ollama

Telecharger et installer depuis https://ollama.com/download/windows

#### Application

Telecharger le dernier installeur depuis la
[page Releases](https://github.com/arioch3131/javis/releases)
et executer `Javis_setup.exe`.

Aucun Python requis pour le mode installeur.

#### Windows depuis les sources (avance)

1. Installer Python 3.11 depuis https://www.python.org/downloads/windows/
2. Cloner le depot puis lancer le script d'installation :
```powershell
git clone https://github.com/arioch3131/javis.git
cd javis
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

3. Optionnel : lancer l'application juste apres l'installation :
```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1 -RunApp
```

Si vous n'utilisez pas `-RunApp`, activez le virtualenv avant d'executer :
```powershell
.\.venv\Scripts\Activate.ps1
python src\ai_content_classifier\main.py
```

---

## Modeles IA recommandes

Telecharger un modele avec `ollama pull <modele>`.

### Images (vision)

| Modele | Taille | RAM min | VRAM min | Notes |
|---|---|---|---|---|
| `moondream` | ~1.5 Go | 4 Go | 2 Go | Ultra leger, classification basique |
| `llava:7b` | ~4 Go | 8 Go | 6 Go | Recommande, bon equilibre |
| `llava:13b` | ~8 Go | 16 Go | 10 Go | Meilleure precision |

### Documents (texte)

| Modele | Taille | RAM min | VRAM min | Notes |
|---|---|---|---|---|
| `gemma3:4b` | ~3 Go | 8 Go | 4 Go | Ultra leger, classification basique |
| `llama3:8b` | ~5 Go | 8 Go | 6 Go | Recommande, rapide et precis |
| `gemma3:12b` | ~8 Go | 16 Go | 10 Go | Meilleure precision |

> Sans GPU dedie, le temps d'inference peut devenir tres eleve.
> Les machines CPU-only et GPU memoire partagee ne sont pas recommandees.
> Les modeles sont selectionnables dans les parametres de l'application.

---

## Formats de fichiers pris en charge

Par defaut, Javis gere :

- Images : `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`
- Documents : `.pdf`, `.docx`, `.txt`, `.md`, `.rtf`, `.odt`

Le support video et audio est prevu pour une version ulterieure.

La listes par défaut peuvent être ajustées dans les parametres de l'application, et vous pouvez ajouter des extensions personnalisees dans la configuration de scan.

---

## Tests

```bash
.venv/bin/python -m pytest -q
```

Le mode Qt headless est configure automatiquement via `tests/conftest.py`.

---

## Migrations de base de donnees (Alembic)

Les migrations sont appliquees automatiquement au demarrage de l'application.

Commandes manuelles si necessaire :
```bash
.venv/bin/python -m alembic -c pyproject.toml current
.venv/bin/python -m alembic -c pyproject.toml upgrade head
.venv/bin/python -m alembic -c pyproject.toml downgrade -1
```

---

## Contribuer

Les contributions sont les bienvenues. Voir [CONTRIBUTING.md](CONTRIBUTING.md)
pour les consignes de traduction et de developpement.

---

## Clause de non-responsabilite

Ce logiciel est fourni "en l'etat", sans garantie d'aucune sorte.
Vous l'utilisez a vos propres risques. L'auteur ne pourra pas etre tenu
responsable des dommages, y compris la perte de donnees ou l'interruption
d'activite.

---

## Licence

GPL-3.0-only
