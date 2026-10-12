# Agent instructions: native deployment preview

RU: Обязательный порядок проверки SDK: если факт можно установить через процесс, hooks, события, буферы или API игры, использовать именно эти данные. Не делать и не анализировать скриншоты для определения фазы боя, готовности карты, результата команды, количества моделей, состояния модуля или численных расчётов. Отсутствующая или неисправная диагностика требует исправить диагностику; ошибка, тайм-аут и неопределённость не разрешают заменять её скриншотом. Снимок допускается только по прямому запросу владельца именно на изображение или визуальное сравнение. По собственной инициативе не захватывать игру, включая проверки UI: клетки, сетка, координаты и состояние окна имеют программные источники истины. До проверки назвать свойство и программный источник; отсутствие диагностики требует её исправления. Перед изменением восстановить последний проверенный сценарий из журнала; не создавать заново уже работающий механизм.
EN: Mandatory SDK verification order: when process state, hooks, events, buffers or game APIs can establish a fact, use that data. Do not capture or inspect screenshots to determine battle phase, map readiness, command completion, model counts, module state or numerical calculations. Missing/broken telemetry requires repairing telemetry; errors, timeouts and uncertainty do not authorize screenshot fallback. Do not autonomously capture game screenshots, including for UI checks. Capture requires an explicit owner request for that image or visual comparison. Cells, grid dimensions, positions, window visibility/bounds, selection and controls must be checked through process/hooks/API/Win32 diagnostics. Before any check, name the property and its programmatic oracle; missing diagnostics must be repaired. A generic request to test, fix or show a window does not authorize image-based state checking. Recover the last verified scenario from the journal before making changes; do not recreate a working mechanism.

RU/EN: Owner requires the after-Start placement button and comparison window to be actual engine-native UI widgets/windows. A styled Win32 child/overlay is not feature parity. Preserve the comparison data, diagrams and formatter during UI migration. Verify native widget identity, game cursor, hover/pressed/disabled states, actual ATB anchor, closing and input isolation programmatically; screenshots require an explicit image request.

RU/EN: After every new native UI mutation, verify continued engine callback progress and check owned Win32 windows for runtime-error dialogs before the next mutation/HMR. Successful registration, tree readback or replacement status alone does not establish a healthy game. Retain uncertain calls/code until the original thread/process has a verified outcome; never replay them to diagnose a frozen frame.

## SDK adapter boundary - architectural axiom

Contract / Контракт: [обязательная архитектура модов и xkit](https://xaaalera.github.io/heroes5-knowledge/modding/native-projects/#architecture-contract). Read the layer responsibilities, dependency rules, lifecycle and migration acceptance requirements before changing mod integration. The contract is mandatory; its documentation is not proof that current code already complies.

Plugin behavior is independent of the development SDK. Only a plugin's integration adapter imports the SDK runtime ABI and translates the shared lifecycle, events, commands and state contract. Reuse existing algorithms and UI through that adapter; a migration alone does not authorize rewriting or dropping working features. Game API bindings may be shared independently of xkit.
The shared player runtime/loader is a separate layer from xkit development tools and from each plugin's adapter. Each native mod ships independently with its declared shared runtime dependencies; players do not install the development environment. Existing formats require an explicit adapter, not automatic compatibility merely because source code exists.
Review dependency direction and complete pre-migration feature parity. Treat SDK imports outside adapter/infrastructure, hidden player dependency on developer tools, or acceptance of a reduced feature set as architecture findings.

RU: Эта архитектура обязательна для любой реализации и миграции. Зависимости направлены от адаптера к контракту runtime и к логике мода; логика мода не импортирует адаптер или внутренности SDK. Типы транспорта, расположение resident buffers, команды supervisor, пути мастерской и детали HMR не должны проникать в алгоритм или интерфейс мода. Алгоритмы, игровые правила и интерфейс конкретного мода не переносить в общий runtime. Изменение SDK не является основанием переписывать рабочую логику мода. Нарушение границы — блокирующее замечание архитектурного ревью; готовность упаковки и сохранность поведения проверяются отдельно.
EN: This architecture is mandatory for every implementation and migration. The adapter depends on the runtime contract and mod behavior; mod behavior must not import the adapter or SDK internals. Transport types, resident-buffer layouts, supervisor commands, workshop paths and HMR mechanics must not leak into mod algorithms or UI. Keep mod-specific algorithms, game rules and UI out of the shared runtime. An SDK change does not authorize rewriting working mod behavior. Boundary violations block architecture review; package readiness and behavioral parity are separate acceptance requirements.

RU: Независимость готового мода от среды разработки — обязательное условие, а не последующий этап. Логика и интерфейс принадлежат самому моду; только его адаптер знает контракт общего игрового runtime. Готовый пакет запускается обычным способом через Heroes/Lobby со своими объявленными игровыми зависимостями, без установленного xkit, Python/Node, supervisor, исходников и путей мастерской. При изменении адаптера, загрузчика или упаковки проверяй именно итоговый пакет: установочные пути, экспорты и импорты DLL, состав зависимостей и обычный запуск без процессов разработчика. Успех HMR внутри SDK не заменяет эту проверку. Сохраняй все ранее работавшие функции; не считай миграцию завершённой по сокращённому набору. Изолированные проверки можно делать в фоне; игровую проверку выполняй только когда доступен разрешённый ввод.
EN: Independence of the finished mod from the development environment is mandatory from the design stage. Behavior and UI belong to the mod; only its adapter knows the shared game-runtime contract. The final package starts normally through Heroes/Lobby with declared game dependencies, without installed xkit, Python/Node, supervisor, sources or workshop paths. Changes to an adapter, loader or packaging require checking the actual final package: installation paths, DLL exports/imports, dependencies and ordinary startup without developer processes. Successful SDK HMR does not substitute for this acceptance. Preserve every previously working feature; a reduced feature set cannot complete migration. Isolated checks may run in the background; game checks must respect current input authorization.

RU: Перед повторной проверкой найди сохранённую приёмку и сравни её хеши исходников/зависимостей, версию игры и проверенные условия. Совпадающий результат переиспользуй. Повторяй только связанную проверку при изменении этих условий, новом сбое или обязательном gate; укажи причину повторения и сохрани новый результат. Не повторяй исследование или startup-сценарий по привычке для каждой правки.
EN: Before repeating a check, find its acceptance receipt and compare source/dependency hashes, game version and verified conditions. Reuse matching evidence. Rerun only the relevant check for changed conditions, a new failure or a mandatory gate; record the reason and new result. Never repeat research or startup checks by habit for each edit.


RU/EN, 2026-10-08: owner resumed algorithm research after documentation. Target100% whole-pack Superadmin matches in creature/quantity/cell with forecasts frozen beforeStart. Preserve ordinary-input restrictions and the separate all-player after-Start explanation TODO. Historical owner-pause notes below are superseded; no old-DLL acceptance transfers to a rebuilt DLL.

## Documentation ownership and article critique / Документация и критика статей

RU: Перед новым инструментом или зависимостью читай [список технологий](https://xaaalera.github.io/heroes5-knowledge/reference/technology-stack/) и проверяй код/манифесты. Сначала переиспользуй имеющееся; добавление, обновление или удаление зависимости требует обновить список с назначением, местом использования и источником версии. Обновляй канонический список в том же изменении, что и код/манифесты зависимости, включая смену назначения или места использования. Проверяй уже подключённые библиотеки, модули и средства языка; новую технологию добавляй только для конкретной задачи, которую имеющиеся средства не решают. Исследованные варианты не выдавать за подключённые. EN: Consult the [technology inventory](https://xaaalera.github.io/heroes5-knowledge/en/reference/technology-stack/) and actual code/manifests before introducing tools or dependencies. Reuse existing solutions first; additions, upgrades and removals must update purpose, usage location and version source in the inventory. Update the canonical inventory in the same change as dependency code/manifests, including changes to purpose or usage location. Inspect installed libraries, modules and language facilities first; add a technology only for a concrete need the existing tools do not meet. Research candidates are not installed technologies.

RU: Единственный источник живой документации — [наш сайт](https://xaaalera.github.io/heroes5-knowledge/), исходники статей — knowledge/docs. В репозиториях оставляем краткий README с назначением и ссылками, AGENTS с рабочими правилами и обязательные лицензии; руководства, справочники и объяснения не копируем по репам. Исторические исследования и приватные журналы сохраняем отдельно, не выдаём за текущую инструкцию. Изменение поведения сопровождается обновлением соответствующей статьи.
EN: The website is the sole source of living human documentation, authored in knowledge/docs. Repositories retain concise README entry points, AGENTS working rules and required notices; manuals, references and explanations link to the site instead of maintaining parallel copies. Preserve historical/private evidence separately and update the canonical article when behavior changes.

RU: Каждая новая или изменённая статья проходит пять независимых критиков по [методу critique](https://github.com/Xaaalera/claude-skills/blob/main/plugins/critique/skills/critique/SKILL.md): понятность новичку, техническая точность, воспроизводимость, структура/навигация, терминология/перевод. Каждый критик указывает место, конкретную проблему, последствия, серьёзность и доказательство; автор не выступает своим критиком. Проверяем факты по коду и наблюдениям, исправляем подтверждённые существенные ошибки, не придумываем оценки. До трёх раундов на статью; фиксируем хеш проверенного текста и решения по замечаниям. Подробный стандарт — [на сайте](https://xaaalera.github.io/heroes5-knowledge/contributing/).
EN: Every new or changed article receives five independent critiques: newcomer clarity, technical accuracy, reproducible steps, structure/navigation, terminology/translation. Findings identify location, failure, consequence, severity and evidence; the author is not a critic. Verify claims against code/observations, fix confirmed substantial defects, record the reviewed content hash and finding disposition, and cap review at three rounds. Follow the canonical site authoring standard; never invent scores.



## RU

- Пользователь запускает игру обычным способом через Heroes/Lobby. Наши моды подключаются через DLL; отдельный EXE для игрока запрещён владельцем. Диагностические EXE и Python-команды принадлежат только инструкциям разработчика. При смене поставки синхронизировать README, RU/EN wiki, devkit, инструкции агентам и release notes; прежние EXE-пакеты не публиковать.

- Читать README.md, CONTRIBUTING.md и devkit/AGENTS.md. Devkit закреплён gitlink; не обновлять его молча до main. При обновлении фиксировать проверенную ревизию в README.
- Сохранять исходные игровые файлы. Разрешённые входы обычного прогноза и отдельного полного расчёта определены в правилах исследовательской ветки ниже; не расширять их молча. Игра и её данные не входят в репозиторий.
- Установка и тесты используют разные режимы: build/эмуляция не равны свежему игровому подтверждению. В отчёте показывать passed/failed/skipped и непроверенное. Физический ввод не заменяется PostMessage.
- Изолированные проверки: requirements-dev.txt и scripts/check.py. Сначала нужна x86 Release-сборка нужного типа; отсутствие компилятора или артефакта не считать PASS. Полный профиль не допускает пропусков; границы публичного профиля без игровых файлов определены выше.
- Не запускать живой сценарий как часть unit-тестов, не забирать общий курсор без согласованного интервала. Следовать авторизованной задаче; обычные безопасные действия не требуют повторных подтверждений.
- Обязательное независимое review перед push описано в CONTRIBUTING.md; не выдумывать отчёты. RU/EN и wiki-ссылки поддерживаются вместе.

## EN

- Players keep the ordinary Heroes/Lobby launch. Our mods load through DLLs; the owner rejects separate player launchers. Diagnostic EXEs and Python commands belong only in developer instructions. Delivery changes must update README, RU/EN wiki, devkit, agent instructions and release notes together; never publish the superseded EXE packages.

Read README, CONTRIBUTING and devkit/AGENTS. Devkit is pinned: do not silently track latest main; update the tested revision when changing it. Preserve game files. Admitted ordinary inputs and separate full-calculation inputs are defined in the research branch rules below; never extend them silently. Do not publish game data.

Build/emulation and a fresh game run are different evidence. Report passed/failed/skipped and unverified scope; PostMessage is not physical-input acceptance. Use requirements-dev and scripts/check.py with the appropriate x86 Release build. Missing tools/artifacts cannot yield PASS. Full mode permits no skips; the public profile's explicit unavailable-game boundary is defined above.

Unit checks do not launch a game or commandeer shared input. Work within the authorized task without repeated confirmation for ordinary safe actions. Independent pre-push review is mandatory; preserve RU/EN and wiki links.

## Public projects / Публичные проекты

- [Game API](https://github.com/Xaaalera/heroes5-game-api) — shared game bindings / общие привязки к игре.

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

## Research branch rules / Правила исследовательской ветки

RU: `npm test` по умолчанию выполняет полный профиль: все найденные проверки, без пропусков, с закреплённым игровым EXE и подходящей нативной DLL. Локальный pre-push принудительно выбирает `H5_TEST_PROFILE=full`, затем проверяет свежую серию боёв. Публичный CI явно использует `H5_TEST_PROFILE=public`: игровые oracle-проверки перечисляются отдельно как невыполненные; все остальные, включая проверки старых экспортов отдельной тестовой DLL, должны пройти без пропусков. Публичный профиль не подтверждает игровые проверки. Не загружать игровые файлы в CI или репозиторий.
EN: `npm test` defaults to the full profile: every discovered test, no skips, with the pinned game EXE and appropriate native DLL. Local pre-push forces `H5_TEST_PROFILE=full`, then checks the fresh battle campaign. Public CI explicitly uses `H5_TEST_PROFILE=public`: game-oracle cases are listed separately as unexecuted; every other test, including legacy-export checks against a separate test DLL, must pass without skips. Public results do not certify game-oracle coverage. Never upload game files to CI or the repository.

Profile error registry / Каталог ошибок профиля: `tests/preview_support.py` owns `TEST_PROFILE_INVALID` (choose full/public) and `TEST_GAME_ORACLE_REGISTRY_MISMATCH` (align discovery and explicit oracle metadata). The test CLI emits their shared status envelopes; unknown profiles and mismatched registries fail closed. / Неизвестный профиль и несовпадение реестра останавливают проверку; CLI использует общие структурированные ошибки каталога.

## RU

- В мастерской `devkit/` этого мода — ссылка на единственный корневой SDK; версия берётся из его HEAD и gitlink, общие незакоммиченные правки видны всем потребителям. Перед сборками/тестами из корня мастерской запускать `scripts/sync-subrepos.ps1 -Check`. Не создавать вторую копию и не копировать общие файлы. После коммита SDK синхронизировать gitlink и проверить потребителя; самостоятельный клон использует закреплённый submodule.

- Приоритет владельца от2октября2026: восстановить полный алгоритм и точный полный прогноз ДО Start; документировать все несостыковки. Разрешены специальные армии, полигон содержит36 составов. Отложенная тогда политика обычного режима впоследствии определена ниже; не расширять её молча. Согласованная нумерация рядов в окне сравнения не меняет алгоритм выбора клеток.

- Указание владельца, исправлено 2026-10-09: Сохраняй собственную видимую тестовую игру SDK и supervisor открытыми между проверками и ответами. Используй существующий проверенный owned-сеанс, HMR и команды SDK для карт, боёв и диагностики. Конец теста или ответа не является поводом закрыть игру. Закрывай только по просьбе владельца или после завершения всей задачи. Перезапускай лишь при подтверждённой необходимости проверки запуска/загрузчика или несовместимости состояния; сначала запиши конкретную причину. Не запускай второй H5_Game.exe и не подключайся к игре владельца.

- Полный внутренний расчёт реализован и в объявленной серии текущего кандидата совпал в273/273 боях. Это ограниченная проверка, не доказательство для всех армий и версий. Исследовательский режим `H5_PREVIEW_SUPERADMIN=1` и внутренний полный расчёт используют отдельные скрытые снимки; обычный прогноз их не наследует. Оба прогноза фиксируются ДО Start; After-Start снимок служит проверке и пояснениям, никогда не входом готового прогноза. Не выдавать полный расчёт за точность приблизительного режима.

- Уточнение владельца: финальный прогон — десять свежих загрузок WorkshopPolygon и помеченных RMG-карт. На каждой проверить все отобранные одиночные и смешанные паки. Зачёт боя — полное совпадение клеток; грейд не штрафуется, разделение считается ожидаемым промахом с доказанной причиной. Главный порог≥70% смешанных боёв; одиночные отдельно. Перед push выполнить `accuracy-campaign.py` и его `--verify-latest`; хук проверяет свежесть JSON по хешам.

- С 25 сентября 2026 разрешена известная армия своего героя, включая количества. Текущий обычный вход — публичные типы и числовые диапазоны; для проверенных обычных охран «Разведка» или надетая «Корона всевидящего» допускают точный исходный состав. Без этого разрешения скрытые количества не читаются. Скрытые грейды и готовое разделение не являются обычным входом. Подхват результата «Быстрой битвы» остаётся в плане. Собственную расстановку отделять от наблюдения после Start. Python — инструмент стенда; игровой расчёт принадлежит C++ DLL мода.

- Пользователь запускает игру обычным способом через Heroes/Lobby. Наши моды подключаются через DLL; отдельный EXE для игрока запрещён владельцем. Диагностические EXE и Python-команды принадлежат только инструкциям разработчика. При смене поставки синхронизировать README, RU/EN wiki, devkit, инструкции агентам и release notes; прежние EXE-пакеты не публиковать.

- Читать README.md, CONTRIBUTING.md и devkit/AGENTS.md. Devkit закреплён gitlink; не обновлять его молча до main. При обновлении фиксировать проверенную ревизию в README.
- Сохранять исходные игровые файлы. Разрешённые входы обычного прогноза и отдельного полного расчёта определены выше; не расширять их молча. Игра и её данные не входят в репозиторий.
- Установка и тесты используют разные режимы: build/эмуляция не равны свежему игровому подтверждению. В отчёте показывать passed/failed/skipped и непроверенное. Физический ввод не заменяется PostMessage.
- Изолированные проверки: requirements-dev.txt и scripts/check.py. Для предиктора сначала нужна x86 Release-сборка; отсутствие компилятора/артефакта не считать PASS. Единственный допустимый пропуск у предиктора — явно отмеченный game-EXE oracle, когда игры нет.
- Пользователь разрешает фокус, мышь и клавиатуру для авторизованной разработки и проверки SDK без повторного согласования. По сообщению пользователя о необходимости фокуса или ввода немедленно прекратить их использование до сообщения о продолжении. Проверять только собственную тестовую игру; фоновый ввод не выдавать за физическую проверку.
- Обязательное независимое review перед push описано в CONTRIBUTING.md; не выдумывать отчёты. RU/EN и wiki-ссылки поддерживаются вместе.

## EN

- In the workshop this mod's devkit is a junction to the single top-level SDK; its HEAD/gitlink define the version and uncommitted edits are shared by all consumers. Run the workshop's `scripts/sync-subrepos.ps1 -Check` before builds/tests. Never create a second copy or copy shared files. After an SDK commit align pins and reverify this consumer; standalone clones retain pinned submodules.

- October2,2026 owner priority: reconstruct the complete algorithm and exact whole-pack predictions frozen before Start; record every discrepancy. Authored theory armies are authorized; the polygon has36 compositions. The ordinary policy deferred then is now defined below; do not extend it silently. Approved row numbering in the comparison window does not change cell-selection rules.

- Owner workflow, corrected 2026-10-09: Keep the owned visible SDK game and its supervisor running across tests and assistant turns. Reuse its validated process/session; use HMR for compatible source changes and SDK commands for maps, battles and diagnostics. Ending a test or reply never justifies closing the game. Close only on owner request or completion of the whole task. Restart only for a demonstrated startup/bootstrap or incompatible-state requirement; record that concrete reason first. Refuse a second H5_Game.exe and never attach to the owner's game.

- The internal full calculation is implemented and matched273/273 battles in the declared current-candidate series. This is bounded evidence, not proof for all armies or builds. Research mode `H5_PREVIEW_SUPERADMIN=1` and the internal full calculation use separate hidden snapshots; ordinary prediction does not inherit them. Freeze both calculations BEFORE Start. After-Start facts support validation and explanations, never the existing forecast. Do not present full-calculation accuracy as approximate-mode accuracy.

- Owner correction: ten fresh loads rotate authored and RMG maps, testing all selected solo/mixed packs on each. A battle counts only if all occupied cells match. Grades do not penalize spatial accuracy; a proven split is a labelled miss. Require≥70% full matches among mixed packs; track solos separately. Run `accuracy-campaign.py` and `--verify-latest` before push; the hook checks JSON freshness by hashes.

- The known player hero army, including quantities, has been authorized since September25,2026. Ordinary input uses public types and numeric quantity ranges. For tested ordinary guards, Scouting or an equipped Crown of the All-Seeing admits exact source composition; otherwise hidden quantities remain unread. Hidden upgrades and the final split are not ordinary inputs. Quick Combat result ingestion remains planned. Separate own placement from after-Start observation. Python is test tooling; gameplay calculations belong in the mod's C++ DLL.

- Players keep the ordinary Heroes/Lobby launch. Our mods load through DLLs; the owner rejects separate player launchers. Diagnostic EXEs and Python commands belong only in developer instructions. Delivery changes must update README, RU/EN wiki, devkit, agent instructions and release notes together; never publish the superseded EXE packages.

Read README, CONTRIBUTING and devkit/AGENTS. Devkit is pinned: do not silently track latest main; update the tested revision when changing it. Preserve game files. The admitted ordinary inputs and separate full-calculation inputs are defined above; never extend them silently. Do not publish game data.

Build/emulation and a fresh game run are different evidence. Report passed/failed/skipped and unverified scope; PostMessage is not physical-input acceptance. Use requirements-dev and scripts/check.py; predictor needs an x86 Release build first. Missing tools/artifacts cannot yield PASS. Only its explicitly identified absent-game oracle may be skipped.

Unit checks do not launch a game or commandeer shared input. Work within the authorized task without repeated confirmation for ordinary safe actions. Independent pre-push review is mandatory; preserve RU/EN and wiki links.

## Research acceptance / Research workflow

Mandatory research workflow: before implementation, search retained project evidence, then the pinned senyaak/homm5-editor findings for this topic, then other external research. Record queries/results, applicability to our build, hypothesis, decision, targeted verification and limits; reuse matching evidence. Root workshop acceptance additionally requires the current-diff research receipt through research:check/review:gate. Independent review must verify the actual evidence, not just presence of JSON. Do not bypass research or claim unverified external findings as our own results. Standalone repository work follows the same research/evidence rule; the root workshop gate is not a player dependency.
