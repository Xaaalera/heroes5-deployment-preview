# Agent instructions: native deployment preview

## Documentation ownership and article critique / Документация и критика статей

RU: Единственный источник живой документации — [наш сайт](https://xaaalera.github.io/heroes5-knowledge/), исходники статей — knowledge/docs. В репозиториях оставляем краткий README с назначением и ссылками, AGENTS с рабочими правилами и обязательные лицензии; руководства, справочники и объяснения не копируем по репам. Исторические исследования и приватные журналы сохраняем отдельно, не выдаём за текущую инструкцию. Изменение поведения сопровождается обновлением соответствующей статьи.
EN: The website is the sole source of living human documentation, authored in knowledge/docs. Repositories retain concise README entry points, AGENTS working rules and required notices; manuals, references and explanations link to the site instead of maintaining parallel copies. Preserve historical/private evidence separately and update the canonical article when behavior changes.

RU: Каждая новая или изменённая статья проходит пять независимых критиков по [методу critique](https://github.com/Xaaalera/claude-skills/blob/main/plugins/critique/skills/critique/SKILL.md): понятность новичку, техническая точность, воспроизводимость, структура/навигация, терминология/перевод. Каждый критик указывает место, конкретную проблему, последствия, серьёзность и доказательство; автор не выступает своим критиком. Проверяем факты по коду и наблюдениям, исправляем подтверждённые существенные ошибки, не придумываем оценки. До трёх раундов на статью; фиксируем хеш проверенного текста и решения по замечаниям. Подробный стандарт — [на сайте](https://xaaalera.github.io/heroes5-knowledge/contributing/).
EN: Every new or changed article receives five independent critiques: newcomer clarity, technical accuracy, reproducible steps, structure/navigation, terminology/translation. Findings identify location, failure, consequence, severity and evidence; the author is not a critic. Verify claims against code/observations, fix confirmed substantial defects, record the reviewed content hash and finding disposition, and cap review at three rounds. Follow the canonical site authoring standard; never invent scores.



## RU

- Пользователь запускает игру обычным способом через Heroes/Lobby. Наши моды подключаются через DLL; отдельный EXE для игрока запрещён владельцем. Диагностические EXE и Python-команды принадлежат только инструкциям разработчика. При смене поставки синхронизировать README, RU/EN wiki, devkit, инструкции агентам и release notes; прежние EXE-пакеты не публиковать.

- Читать README.md, CONTRIBUTING.md и devkit/AGENTS.md. Devkit закреплён gitlink; не обновлять его молча до main. При обновлении фиксировать проверенную ревизию в README.
- Сохранять исходные игровые файлы. Не использовать скрытый состав охраны как вход прогноза/справки. Игра и её данные не входят в репозиторий.
- Установка и тесты используют разные режимы: build/эмуляция не равны свежему игровому подтверждению. В отчёте показывать passed/failed/skipped и непроверенное. Физический ввод не заменяется PostMessage.
- Изолированные проверки: requirements-dev.txt и scripts/check.py. Для предиктора сначала нужна x86 Release-сборка; отсутствие компилятора/артефакта не считать PASS. Единственный допустимый пропуск у предиктора — явно отмеченный game-EXE oracle, когда игры нет.
- Не запускать живой сценарий как часть unit-тестов, не забирать общий курсор без согласованного интервала. Следовать авторизованной задаче; обычные безопасные действия не требуют повторных подтверждений.
- Обязательное независимое review перед push описано в CONTRIBUTING.md; не выдумывать отчёты. RU/EN и wiki-ссылки поддерживаются вместе.

## EN

- Players keep the ordinary Heroes/Lobby launch. Our mods load through DLLs; the owner rejects separate player launchers. Diagnostic EXEs and Python commands belong only in developer instructions. Delivery changes must update README, RU/EN wiki, devkit, agent instructions and release notes together; never publish the superseded EXE packages.

Read README, CONTRIBUTING and devkit/AGENTS. Devkit is pinned: do not silently track latest main; update the tested revision when changing it. Preserve game files and exclude hidden guard composition from prediction/reference inputs. Do not publish game data.

Build/emulation and a fresh game run are different evidence. Report passed/failed/skipped and unverified scope; PostMessage is not physical-input acceptance. Use requirements-dev and scripts/check.py; predictor needs an x86 Release build first. Missing tools/artifacts cannot yield PASS. Only its explicitly identified absent-game oracle may be skipped.

Unit checks do not launch a game or commandeer shared input. Work within the authorized task without repeated confirmation for ordinary safe actions. Independent pre-push review is mandatory; preserve RU/EN and wiki links.

## Public projects / Публичные проекты

- [Deployment Preview / Предиктор](https://github.com/Xaaalera/heroes5-deployment-preview): native placement projections.
- [Bank Reference / Справочник армий](https://github.com/Xaaalera/heroes5-bank-reference): possible bank armies.
- [Mod Devkit / Девкит](https://github.com/Xaaalera/heroes5-mod-devkit): shared tools used to build and test both DLL mods.
- [Knowledge / База знаний](https://github.com/Xaaalera/heroes5-knowledge) · [public site / сайт](https://xaaalera.github.io/heroes5-knowledge/).
- [Author / Автор — Xaaalera](https://github.com/Xaaalera) · [email](mailto:dampirsimpl@gmail.com) · [personal Telegram / личный Telegram](https://t.me/Victima).
- [Heroes V Universe / Heroes Lobby](https://h5lobby.com/).

RU: эти проекты принадлежат автору; база знаний и моды не являются официальными продуктами Universe. Общие факты и контакты обновлять во всех канонических репозиториях. EN: These are the author's projects, not official Universe products. Keep shared facts and contact links consistent across canonical repositories.


## Standalone use / Работа вне мастерской

RU: этот репозиторий можно использовать отдельно. Начни с его README и AGENTS.md; глобальная папка мастерской не обязательна. Если есть .gitmodules, выполни `git submodule update --init` после клонирования. В связанной мастерской используй её sync-subrepos вместо создания вторых checkout.
EN: This repository can be used independently. Start with its README and AGENTS.md; the global workshop is optional. If .gitmodules exists, initialize pinned dependencies with `git submodule update --init`. In a linked workshop use its canonical dependency synchronization.

- [Devkit commands / команды SDK](https://xaaalera.github.io/heroes5-knowledge/reference/xkit-commands/).
- [Game API contracts / контракты библиотеки](https://xaaalera.github.io/heroes5-knowledge/reference/game-api/).
- [Research index / карта исследований](https://xaaalera.github.io/heroes5-knowledge/reference/research-index/).


## Code standards / Стандарты кода

RU: перед новой правкой применяй подходящие установленные скиллы из [маркетплейса автора](https://github.com/Xaaalera/claude-skills). Имена переменных/параметров должны объяснять смысл; не использовать непрозрачные сокращения. C++ сохраняет calling convention, lifetime и ABI; Python использует описательные snake_case имена. Обязательные имена API/protocol/register и общепринятые PID/DLL/ABI сокращения допустимы. JS правила не переносить механически на C++/Python.
EN: Load the applicable guides before coding/reviewing. Use descriptive names, small functions with one responsibility, canonical dependencies and no speculative abstractions. Preserve native ABI/protocol compatibility during readability changes. Existing code is changed when relevant, not mass-renamed by this policy.

- All code: [solid](https://github.com/Xaaalera/claude-skills/blob/main/plugins/meta/skills/solid/SKILL.md), [ockham](https://github.com/Xaaalera/claude-skills/blob/main/plugins/meta/skills/ockham/SKILL.md).
- JS/TS only: [conventions](https://github.com/Xaaalera/claude-skills/blob/main/plugins/frontend-js/skills/conventions/SKILL.md).
- Tests: Codex alias `tests-architecture`, upstream [tests:architecture](https://github.com/Xaaalera/claude-skills/blob/main/plugins/tests/skills/architecture/SKILL.md).
- Documents: [standard](https://github.com/Xaaalera/claude-skills/blob/main/plugins/docs/skills/standard/SKILL.md), [lean-writing](https://github.com/Xaaalera/claude-skills/blob/main/plugins/meta/skills/lean-writing/SKILL.md), [wittgenstein](https://github.com/Xaaalera/claude-skills/blob/main/plugins/meta/skills/wittgenstein/SKILL.md).
- Changed user-facing UI: [ui-strings](https://github.com/Xaaalera/claude-skills/blob/main/plugins/i18n/skills/ui-strings/SKILL.md), [responsive-layout](https://github.com/Xaaalera/claude-skills/blob/main/plugins/frontend-css/skills/responsive-layout/SKILL.md).
- New public JSON error boundaries: [format](https://github.com/Xaaalera/claude-skills/blob/main/plugins/error/skills/format/SKILL.md); version changes explicitly, do not silently reinterpret native status words.
- Reviewers load every applicable guide listed in .claude/review.config.json. If a guide is not installed, read the canonical source above and report availability honestly. Do not vendor independent copies of these standards.


## Human-usable functionality / Использование человеком

RU/EN: Human docs/help/descriptions use meaningful function/event/type names and explain role; never raw memory addresses, structure byte offsets or address-only disassembler labels. Numeric bindings remain in source/private logs. Reviewers reject opaque address explanations; preserve dated findings when correcting old docs.

RU/EN: prefer standard language facilities or maintained libraries for infrastructure. SDK log adapters attach operation/plugin/stage/level/time and source locations; do not build another logger. Readable output and linked raw diagnostics are required for human use; preserve player delivery without developer Python dependencies.

RU: весь функционал проекта должен быть пригоден для самостоятельного использования человеком без AI. Основной сценарий требует понятного входа, справки, разумных настроек по умолчанию, видимого состояния и ошибок с действием для исправления. Цепочка внутренних Python/PowerShell/RPC команд не заменяет пользовательский интерфейс. Разработчик должен уметь подготовить окружение, создать/запустить/обновить плагин и получить готовый мод по документации самостоятельно.
EN: Every feature must be usable by a person without an AI agent. Provide a clear entry point, help, sensible defaults, observable progress and actionable errors. Internal scripts/RPC sequences may support diagnostics but do not satisfy the main user workflow. Acceptance includes following the documented workflow as a human; never document a planned friendly command as already implemented. This is a project rule, not a new skill.

RU: правило также относится к README, документации, справке, описаниям, примерам и сообщениям. Писать для указанной аудитории простым языком: зачем функция нужна, как начать, какой результат ожидается, как исправить ошибку. Объяснять термины при первом использовании; внутренние механизмы выносить в документацию разработчика. Инструкция не должна требовать AI для расшифровки или поиска пропущенных шагов.
EN: Apply the same rule to README, documentation, help, descriptions, examples and messages. Explain purpose, starting steps, expected result and recovery in language appropriate to the reader. Define unfamiliar terms on first use; keep internals in developer documentation. A person must be able to follow the instructions without AI filling missing steps.
