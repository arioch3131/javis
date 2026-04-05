## Local Git Hooks

Install local hooks before contributing:

```bash
bash scripts/install_git_hooks.sh
```

The pre-commit hook runs `ruff` checks on staged Python files to prevent lint/format regressions.

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
