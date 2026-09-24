# Contributions / Изменения

## RU

Правки проверяются на закреплённом devkit. Обновлять README и wiki при изменении установки/поведения; проверенный commit среды указывать явно. Живые результаты сохранять в [дневнике](https://xaaalera.github.io/heroes5-knowledge/reference/research-diary/), не повышать область проверки по одному успешному build.

Перед push: npm ci, npm test, npm run review:secrets. Для текущего diff из npm run review:info получить независимые craft, architecture, tests, docs, security заключения по контрактам devkit/.agents/review. Оценка =10−20×blocker−3×major−minor; нерешённые blocker/major не допускаются. Docs-review включает все Markdown-пути, reviewer и восемь критериев purpose/structure/specificity/reproducibility/evidence/applicability/translations/maintenance с обоснованием и списком findings.

Реальные оценки передаются в npm run review:attest -- <results.json>. Сгенерированная .review/attestations коммитится отдельно. Hook и CI проверяют запись и тесты; они не являются личностью рецензента и не запускают игру. После изменения исходников нужно новое ревью. База задаётся .claude/review.config.json; её нельзя менять, чтобы скрыть непроверенные изменения.

Не коммитить игру, PAK, H5M, H5U, DLL/EXE, профили, сохранения, логи или локальные пути. Собранные файлы хранятся в .local. Лицензию на чужие игровые ресурсы эти исходники не предоставляют.

## EN

Use the pinned devkit, update README/wiki when installation or behavior changes and name the tested environment commit. Preserve real live outcomes in the linked diary; a successful build does not expand validation scope.

Before push run npm ci/test/review:secrets and obtain independent craft/architecture/tests/docs/security judgments for review:info's exact diff, using devkit/.agents/review contracts. Score 10−20×blockers−3×majors−minors, with no unresolved blocker/major. Docs report identifies reviewer, all Markdown paths, eight reasoned criteria listed above and findings.

Pass actual results to review:attest, commit the generated attestation separately, then push. Hooks/CI verify records/tests, not reviewer identity or gameplay. New source edits need renewed review; never move the base to hide work. No game files, packages/binaries, profiles, saves, logs or personal paths belong in Git. Build outputs stay in .local; no game-resource rights are granted by this repository.
