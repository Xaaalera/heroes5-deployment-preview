# Contributions / Изменения

## RU

Перед push предиктора обязательно выполнить `python -X utf8 scripts/accuracy-campaign.py` в настроенном стенде (`H5_WORKSPACE`, `H5_PREVIEW_BUILD`). Прогон делает десять свежих загрузок трёх типов карт: WorkshopPolygon и две помеченные копии настоящих карт генератора Universe. На каждой проходят все отобранные паки. JSON сохраняет прогноз до Start, факт, флаги движка, решение разделения, попытки клеток и обоснование промаха. Зачёт — полное совпадение позиций; грейд не штрафуется, разделение помечается и считается промахом. Главный порог —≥70% полностью совпавших **смешанных** боёв; одиночные считать отдельно. `python -X utf8 scripts/accuracy-campaign.py --verify-latest` сверяет результат и хеши исходника/DLL/EXE/карт; `.githooks/pre-push` запускает его после независимого review gate. Если проверка не проходит, не публиковать новый точный релиз и не обходить хук.

Правки проверяются на закреплённом devkit. Обновлять README и wiki при изменении установки/поведения; проверенный commit среды указывать явно. Живые результаты сохранять в [дневнике](https://xaaalera.github.io/heroes5-knowledge/reference/research-diary/), не повышать область проверки по одному успешному build.

Перед push: npm ci, npm test, npm run review:secrets. Для текущего diff из npm run review:info получить независимые craft, architecture, tests, docs, security заключения по контрактам devkit/.agents/review. Оценка =10−20×blocker−3×major−minor; нерешённые blocker/major не допускаются. Docs-review включает все Markdown-пути, reviewer и восемь критериев purpose/structure/specificity/reproducibility/evidence/applicability/translations/maintenance с обоснованием и списком findings.

Реальные оценки передаются в npm run review:attest -- <results.json>. Сгенерированная .review/attestations коммитится отдельно. Hook и CI проверяют запись и тесты; они не являются личностью рецензента и не запускают игру. После изменения исходников нужно новое ревью. База задаётся .claude/review.config.json; её нельзя менять, чтобы скрыть непроверенные изменения.

Не коммитить игру, PAK, H5M, H5U, DLL/EXE, профили, сохранения, логи или локальные пути. Собранные файлы хранятся в .local. Лицензию на чужие игровые ресурсы эти исходники не предоставляют.

## EN

Before pushing predictor changes, run `python -X utf8 scripts/accuracy-campaign.py` in the configured test environment (`H5_WORKSPACE`, `H5_PREVIEW_BUILD`). Ten fresh loads rotate WorkshopPolygon and tagged copies of two genuine Universe RMG maps; each tests every selected pack. JSON records the pre-Start prediction, actual positions, engine policy, split decision, cell attempts and mismatch explanation. Only fully matching positions count; upgrades do not penalize spatial accuracy, while splitting is a labelled miss. The main gate requires at least70% of **mixed** battles to match; solo packs are reported separately. `python -X utf8 scripts/accuracy-campaign.py --verify-latest` checks the result and source/DLL/EXE/map hashes; `.githooks/pre-push` runs it after independent review. Do not publish a new accuracy claim or bypass the hook on failure.

Use the pinned devkit, update README/wiki when installation or behavior changes and name the tested environment commit. Preserve real live outcomes in the linked diary; a successful build does not expand validation scope.

Before push run npm ci/test/review:secrets and obtain independent craft/architecture/tests/docs/security judgments for review:info's exact diff, using devkit/.agents/review contracts. Score 10−20×blockers−3×majors−minors, with no unresolved blocker/major. Docs report identifies reviewer, all Markdown paths, eight reasoned criteria listed above and findings.

Pass actual results to review:attest, commit the generated attestation separately, then push. Hooks/CI verify records/tests, not reviewer identity or gameplay. New source edits need renewed review; never move the base to hide work. No game files, packages/binaries, profiles, saves, logs or personal paths belong in Git. Build outputs stay in .local; no game-resource rights are granted by this repository.
