# Javis

> 🇬🇧 [English version](README.md)

Classification et organisation automatique de contenus (documents, images, etc.) via des modèles d'IA locaux avec Ollama, avec une interface PyQt6.

## Documentation

- Architecture (EN) : `docs/ARCHITECTURE_V1.md`
- Architecture (FR) : `docs/ARCHITECTURE_V1.fr.md`
- Fonctionnalités (EN) : `docs/FUNCTIONALITIES_V1.md`
- Fonctionnalités (FR) : `docs/FUNCTIONALITIES_V1.fr.md`

## Statut du projet

Ce projet est un projet personnel maintenu sur mon temps libre.  
Les Issues et Pull Requests sont les bienvenues, mais je peux avoir des délais de réponse/review importants.

## Politique de support

- Pas de SLA, pas de support garanti, et pas de délai de réponse garanti.
- La maintenance se fait en mode best-effort, selon la disponibilité.
- Les contributions sont bienvenues, mais le rythme de review/merge dépend du temps disponible.

## Clause de non-responsabilité

- Ce logiciel est fourni "en l'état", sans garantie d'aucune sorte, expresse ou implicite.
- Vous utilisez ce projet à vos propres risques.
- L'auteur ne pourra pas être tenu responsable des dommages directs, indirects, incidents ou consécutifs, y compris perte de données, interruption d'activité ou problèmes de sécurité.

---

## Prérequis

### Ubuntu 24.04

#### Paquets système PyQt6

```bash
sudo apt update
sudo apt install -y python3-pyqt6
sudo apt install -y qt6-qpa-plugins libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1
```

#### Modules Qt optionnels

```bash
sudo apt install -y python3-pyqt6.qtsvg python3-pyqt6.qtwebengine
```

#### Vérification

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

Télécharger et installer depuis https://ollama.com/download/windows

#### Application

Télécharger le dernier installeur depuis la
[page Releases](https://github.com/arioch3131/ai-content-classifier/releases)
et exécuter `Javis_setup.exe`

Aucun Python requis — tout est inclus dans l'installeur.

---

## Modèles IA recommandés

Télécharger un modèle avec `ollama pull &lt;modèle&gt;`

### Images (vision)

| Modèle | Taille | RAM min | VRAM min | Notes |
|---|---|---|---|---|
| `moondream` | ~1.5 Go | 4 Go | 2 Go | 🪶 Ultra léger, classification basique |
| `llava:7b` | ~4 Go | 8 Go | 6 Go | ✅ Recommandé — bon équilibre |
| `llava:13b` | ~8 Go | 16 Go | 10 Go | ⭐ Meilleure précision |

### Documents (texte)

| Modèle | Taille | RAM min | VRAM min | Notes |
|---|---|---|---|---|
| `gemma3:4b` | ~3 Go | 8 Go | 4 Go | 🪶 Ultra léger, classification basique |
| `llama3:8b` | ~5 Go | 8 Go | 6 Go | ✅ Recommandé — rapide et précis |
| `gemma3:12b` | ~8 Go | 16 Go | 10 Go | ⭐ Meilleure précision |

> **Sans GPU dédié (VRAM dédiée), la catégorisation IA n'est pas adaptée en l'état** :
> sur laptop/workstation CPU-only ou mémoire partagée, les temps d'inférence peuvent devenir très élevés.
> Les modèles sont sélectionnables dans les paramètres de l'application.

---

## Tests

```bash
.venv/bin/python -m pytest -q
```

Le mode headless Qt est configuré automatiquement pour les tests via `tests/conftest.py`.

---

## Internationalisation (i18n)

L'application supporte l'anglais et le français :

- Langue configurable via `general.language` (`en`, `fr`)
- Fallback automatique vers `en`
- Catalogues : `src/ai_content_classifier/resources/i18n/en.json` et `fr.json`
- Service : `src/ai_content_classifier/services/i18n/i18n_service.py`

Pour ajouter une traduction :

1. Ajouter les clés/valeurs dans `en.json`
2. Ajouter les équivalents dans `fr.json` (ou autre langue)
3. Utiliser `tr("namespace.key", "Default text")` dans le code UI

---

## Parametres du Cache Thumbnail

Le comportement du cache disque des thumbnails est configurable dans Parametres (onglet Thumbnails) :

- `thumbnails.cache.enabled` (defaut : `true`)
- `thumbnails.cache.ttl_sec` (defaut : `3600`)
- `thumbnails.cache.cleanup_interval_sec` (defaut : `300`)
- `thumbnails.cache.max_size_mb` (defaut : `1024`)
- `thumbnails.cache.renew_on_hit` (defaut : `false`)
- `thumbnails.cache.renew_threshold` (defaut : `0.5`)

Note de compatibilite :
- Avec `omni-cache 2.0.0`, `max_size` est ignore proprement.
- Avec `omni-cache 2.1.0+`, `max_size` est active automatiquement.

Vous pouvez purger le cache depuis :
- `Tools > Database > Clear Thumbnail Cache`
- Parametres > Thumbnails > `Clear Thumbnail Cache`

---

## Licence

GPL-3.0-only
