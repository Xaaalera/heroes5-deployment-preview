# Heroes V Deployment Preview

RU: аварийное завершение тестового процесса требует исходных PID, времени создания и пути. Если запускатель не вернул время создания или идентичность изменилась, принудительное завершение запрещено; журнал сохраняет неподтверждённую очистку. Обычный запрос выхода остаётся первым действием.

EN: Forced cleanup requires the original PID, creation time and executable path. Missing launch creation identity or a changed process refuses termination and records unconfirmed cleanup. Normal game shutdown is attempted first.

RU: проверенные зависимости: devkit `bc471b6`, Game API `2aa326d`. Мастерская использует один canonical checkout; самостоятельный clone получает закреплённые сабмодули. Исследование алгоритма предиктора остаётся на паузе.

EN: Verified dependency revisions: devkit `bc471b6`, Game API `2aa326d`. The workshop shares canonical checkouts; standalone clones use pinned submodules. Predictor algorithm research remains paused.

RU, 2026-10-07: [xkit 0.1.0](https://github.com/Xaaalera/heroes5-mod-devkit/releases/tag/v0.1.0) опубликован с готовым SDK. Новый SDK-плагин выпускается отдельной DLL; общие dinput8.dll и d3d9.dll обеспечивают подключение. Исходная библиотека игры сохраняется локально как d3d9.universe.dll и не распространяется. Проверены две независимые DLL и обычный запуск. Этот плагин сохраняет собственный legacy-контракт и ещё не переведён на HMR.
EN: xkit 0.1.0 is published with a ready SDK bundle. New SDK plugins ship as separate DLLs with shared dinput8.dll/d3d9.dll infrastructure; the game original remains local as d3d9.universe.dll. Two independent player DLLs and ordinary startup are verified. This existing plugin retains its legacy contract and is not yet migrated to HMR.


[Game API](https://github.com/Xaaalera/heroes5-game-api) — shared C++ game bindings / общая библиотека привязок к игре.

RU,2026-10-04: общий devkit разрабатывает ABI3 hot reload и выпуск новых SDK-плагинов в bin/Heroes5Mods/Plugins. Этот предиктор сохраняет текущий legacy DLL-контракт и пока не поддерживает такую перезагрузку. EN: Shared bootstrap remains the ordinary player entry; the SDK prototype does not automatically migrate this plugin. [SDK status/release notes](https://github.com/Xaaalera/heroes5-mod-devkit).


## Author and related projects / Автор и связанные проекты

Автор / Author: [Xaaalera](https://github.com/Xaaalera) · [email](mailto:dampirsimpl@gmail.com) · [личный Telegram / personal Telegram](https://t.me/Victima).

- [Deployment Preview / Предиктор](https://github.com/Xaaalera/heroes5-deployment-preview).
- [Bank Reference / Справочник армий](https://github.com/Xaaalera/heroes5-bank-reference).
- [Mod Devkit / Девкит](https://github.com/Xaaalera/heroes5-mod-devkit): shared development and test tools for both DLL mods.
- [Knowledge source / Исходники базы](https://github.com/Xaaalera/heroes5-knowledge) · [public knowledge / база знаний](https://xaaalera.github.io/heroes5-knowledge/).
- [Heroes V Universe / Heroes Lobby](https://h5lobby.com/).

RU: личные проекты автора; не официальные продукты Universe. EN: Personal projects by the author, not official Universe products.

## RU

Предиктор расстановки для [Heroes V Universe](https://h5lobby.com/). До Start показывает проекции известных типов противника, карточки грейдов и область хода. Скрытые количества и грейды не раскрывает; фактическое разделение армии может отличаться. [Возможности, изображения и ограничения](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/).

### Игроку: установка и удаление

Поставка — DLL для обычного запуска через **Heroes/Lobby**, без отдельного EXE нашего мода. Наличие опубликованного архива проверяй в [Releases](https://github.com/Xaaalera/heroes5-deployment-preview/releases): если список пуст, пользовательский пакет ещё не опубликован. Code → Download ZIP скачивает исходники. Старый EXE-кандидат отменён. Версия 0.1.0-preview.2 экспериментальная.

1. Закрой игру. Файлы пакета: bin/dinput8.dll и bin/Heroes5Mods/WorkshopDeploymentPreview.dll в папке установленной игры.
2. Общий dinput8.dll нужен один раз для обоих наших модов. Не перезаписывай файл другого мода с этим именем: совместимость не проверена. Штатные d3d9.dll, uni.dll, um.dll не заменяются.
3. Запускай Heroes/Lobby как раньше. В обычном бою до Start должны появиться проекции. Python, Git и компилятор игроку не нужны.

Первый ПКМ открывает карточку базового или известного грейда; повторный переключает неопределённые варианты и дальность. Двойной ЛКМ открывает подробное окно. После Start проекции исчезают.

Для отключения закрой игру и убери bin/Heroes5Mods/WorkshopDeploymentPreview.dll. Общий bin/dinput8.dll удаляй после всех наших DLL-модов и только если он установлен из нашего пакета. В UserMODs предиктор ничего не ставит.

### Совместимость и проверка

Поддерживается [закреплённая сборка](https://xaaalera.github.io/heroes5-knowledge/reference/universe-build/), определённая четырьмя SHA-256. Несовпадение или отказ модуля прекращает запуск с сообщением. Хеши игры не удостоверяют происхождение сторонних DLL.

Опубликованный preview.2 проверен с SDK [71509e4](https://github.com/Xaaalera/heroes5-mod-devkit/tree/71509e43af0faf080d8a47ed5b3ff8c72da2a3e9). Проверены обычный H5_Game.exe до меню и автоматическая загрузка DLL; затем пять циклов загрузки боя, карточек и очистки через обычный процесс игры с тестовыми командами и наблюдателем. Второй мод был загружен одновременно. Это ограниченная проверка совместной работы, не гарантия всех арен и хранилищ. В ранней проверке опубликованного preview.2 смешанный пак совпал лишь в 1 из 7 позиций, а один отряд разделился. Более новая кандидатная DLL описана ниже и ещё не опубликована. Сам интерфейс Heroes/Lobby отдельно не автоматизировался.

### Разработчику

Checkpoint4 октября2026: DLL baca89 реализует резервsource-simple fallback для source-simple с native army rectangle и сохранением частичных клеток.240 синтетических native mixed сравнений и selector counterexample проходят; полный58/58 PASS. Живой generated Archer40→20+20 контроль2/2 с штатным выходом не требовал fallback; forced live fallback/новая широкая матрица ещё нужны.273/273 относится к прежней a8d794.

Checkpoint4 октября2026: десять свежих загрузок текущей DLL a8d794 дали **273/273 exact** боёв(mixed213/213,solo60/60), все штатно закрыты. Независимый strict Superadmin verifier PASS по исходным прогнозам до Start/текущим хешам/полноте паков. Вердикт goal_completefalse: оставшиеся ветви, live equality и полный алгоритм ещё не закрыты. Legacy CLI exit1 — старый acceptance flag; не исправляй сохранённый JSON. Выпуска не было.

Checkpoint4 октября2026: нативный SDK levelup-state заменил OCR в проверке окна уровня. Текущая DLL a8d794 дала72/72 полных совпадения на всех36 составах с Angels10 и Peasant1000, с возвратом/штатным выходом. Native55/55,SDK45/45 PASS. Принудительное реальное окно1→2 проверено отдельно; десятизагрузочный протокол и остальные ветви ещё открыты.

Checkpoint4 октября2026: DLL a8d794 привязывает исходные scripted-дескрипторы к доверенному окну и строит прогноз до Start. Native54/54 PASS;6/6 заданных сцен совпали полностью(18/18 отрядов) для одного состава80/35/12, после наблюдения каждая игра штатно закрыта. Результаты/возврат на карту этим протоколом не проверены; полный36/hero/ten-load набор и остальные ветви остаются открыты. Обычные входы не расширены; выпуск не готов.

Checkpoint3 октября2026: исследовательская DLLfb8e74 добавляет Superadmin-захват исходных аргументов StartCombat до создания боя. SourceTrace ABI7(58 words) различает map-neutral/scripted источники и неизвестные модификаторы; InputTrace15/ProjectionTrace8 сохранены. Native54/54 PASS. Live scripted состав80/35/12 снят точно, но его прогноз/привязка к окну ещё не готовы. Обычный pack_4 прогноз совпал3/3 до отказа проверки результатов на пустом снимке; это неполный прогон. Обычные входы не расширены, выпуск не готов. Подробности — в дневнике исследования RU/EN.

В связанной мастерской SDK имеет один корневой checkout; `devkit/` мода — ссылка на него. Из корня мастерской выполнить `powershell -NoProfile -File scripts/sync-subrepos.ps1 -Check`, исправление — без `-Check`. Текущая версия — HEAD общего SDK и gitlink этого мода, а не историческая версия выпуска выше. Общие правки не копируются между репами. Самостоятельный клон сохраняет обычный submodule. Перед новым выпуском закрепить изменения SDK коммитом, синхронизировать gitlink и повторить проверки.

Исследовательский суперадмин: переменная `H5_PREVIEW_SUPERADMIN=1` при запуске тестовой игры включает отдельный снимок исходных типов и количеств объекта до Start. Чтение: диагностический `workshop_preview_loader.exe --pid PID --dll PATH --admin-source-trace`. Обычный запуск возвращает пустой список. Это пока **источник данных для исследования**, а не точный суперадминский прогноз:100/100 не подтверждены. [Механизм и живые контроли](https://xaaalera.github.io/heroes5-knowledge/reference/research-diary/) будут дополнены после полной проверки.

Финальная приёмка: **10 свежих загрузок карт**, на каждой последовательно проверяются все отобранные одиночные и смешанные паки. Используются WorkshopPolygon и две помеченные копии карт, созданных RMG Universe; исходные RMG-карты и составы не меняются. Бой засчитывается только при полном совпадении клеток всех стеков; грейд не штрафуется, разделение считается ожидаемым промахом и объясняется отдельно. Главный порог — не менее70% **смешанных** боёв с полным совпадением; одиночные показываются отдельной статистикой. `python -X utf8 scripts/accuracy-campaign.py` сохраняет подробный JSON. Хук перед push запускает `--verify-latest` и отклоняет устаревший результат после изменения исходника/DLL/карты. Пока такая серия не прошла, точность релиза не подтверждена.

Локальная кандидатная DLL от25 сентября, ещё не включённая в preview.2, учитывает собственную армию героя и публичные словесные диапазоны численности нейтралов. В C++ добавлены оценка разрежения и защитной ветки, корректировка рядов2×2 и совместной защиты с разрежением. Скрытые точные количества, грейды и разделение не читаются. 14 нативных проверок прошли. Отдельные загрузки RMG-A и RMG-B дали13/18 и11/13 полностью совпавших смешанных построений; защитный семиотрядный бой с малой армией героя —7/7 точных пар. С10 ангелами DLL ещё может ложно включать защиту, а серия десяти загрузок не пройдена. [Проверки и ограничения](https://xaaalera.github.io/heroes5-knowledge/reference/research-diary/#rmg-placement-check).

Нужны Windows, Git, Visual Studio 2022 C++ x86 tools, CMake 3.21+. Для тестов также Python 3.10+ и requirements-dev.txt.

    git clone --recursive https://github.com/Xaaalera/heroes5-deployment-preview.git
    cd heroes5-deployment-preview
    cmake -S . -B .local/player-build -A Win32
    cmake --build .local/player-build --config Release
    cmake --install .local/player-build --config Release --prefix .local/dist
    cmake -S devkit/native -B .local/bootstrap -A Win32
    cmake --build .local/bootstrap --config Release
    cmake --install .local/bootstrap --config Release --prefix .local/dist
    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements-dev.txt
    $env:H5_PREVIEW_BUILD = (Resolve-Path .local/player-build/Release).Path
    .venv/Scripts/python scripts/check.py

Install по умолчанию содержит только DLL. EXE workshop_preview_loader остаётся диагностикой и устанавливается лишь явным --component Diagnostics; игроку его не поставлять. Девять проверок C++/x86 допускают только явный пропуск game-EXE oracle при отсутствии игры. H5_WORKSPACE указывает подготовленный стенд для полного сравнения.

Для живой проверки установи DLL в sandbox и используй scripts/native-preview-check.py --auto-load. Python и диагностический EXE в этом тесте читают состояние и управляют сценарием; они не являются пользовательским способом запуска. Не сочетай старую инъекцию --native-loader с установленным dinput8.dll: разные пути могут загрузить две копии плагина. SDK --control --observe-deployment записывает результат Start отдельно от входов прогноза.

Локальный опыт с изменённым SDK можно явно направить через `H5_PREVIEW_DEVKIT=<checkout-devkit>`; это не смена закреплённого gitlink. `accuracy-campaign.py --background` использует этот SDK для запроса неактивируемого окна и проверки положения/фокуса; первая проверка была отклонена из-за повторного захвата фокуса/курсора, исправленная версия ещё не испытана в игре. Итоговый `--verify-latest` принимает только закреплённый devkit, а не локальную подмену.

### Авторские герои и умения в Superadmin

Для одной загрузки Polygon доступны `--hero NAME` и повторяемый `--hero-skill ID`. Герой должен уже существовать и принадлежать текущему игроку. Умения выдаются по порядку; проверяются принятие, пустые очереди и рост мастерства. Отказ сохраняется и останавливает опыт до боя. Параметры требуют `--rounds 1 --map polygon --superadmin-source`; максимум32 выдачи. Правила обычного прогноза не меняются.

Проверенный контроль: `python -X utf8 scripts/accuracy-campaign.py --rounds 1 --map polygon --only-pack pack_15 --superadmin-source --hero Calid --hero-skill 6 --hero-skill 6 --hero-skill 6 --hero-skill 60 --hero-skill 91`. Отчёт хранит `research_hero`, `research_hero_skills`, `run.hero_skill_steps` и frozen прогноз. Результат7/7 и baseline36 — один контроль, не десятизагрузочная приёмка.

## EN

### Authored heroes and skills in Superadmin

A single Polygon load accepts `--hero NAME` and repeated `--hero-skill ID`. The hero must already exist and belong to the current player. Grants run in order; acceptance, empty queues and increasing mastery are checked. A rejection is saved and stops the experiment before battle. These options require `--rounds 1 --map polygon --superadmin-source`, with at most32 grants. Ordinary prediction policy is unchanged.

Verified control: `python -X utf8 scripts/accuracy-campaign.py --rounds 1 --map polygon --only-pack pack_15 --superadmin-source --hero Calid --hero-skill 6 --hero-skill 6 --hero-skill 6 --hero-skill 60 --hero-skill 91`. Reports retain `research_hero`, `research_hero_skills`, `run.hero_skill_steps` and the frozen forecast. Exact7/7 and baseline36 establish one control, not ten-load acceptance.

Deployment predictor for the linked Universe build. Before Start it shows public creature-type projections, upgrade cards and movement range; it does not reveal hidden quantities/upgrades or guarantee the game's stack splitting. See the linked wiki for images, controls and limits.

### Player installation

Check Releases for a published DLL archive. If none is listed, no player package is available yet. Do not use the source ZIP or withdrawn EXE candidate. Version 0.1.0-preview.2 is experimental. Exit the game; place bin/dinput8.dll and bin/Heroes5Mods/WorkshopDeploymentPreview.dll under the installed game directory. Both mods share one bootstrap. Never overwrite another mod's dinput8.dll without compatibility checks; original d3d9.dll, uni.dll and um.dll stay unchanged.

Start through Heroes/Lobby as usual. No separate mod EXE, Python, Git or compiler is required. First RMB opens the base/known grade card; repeated RMB cycles uncertain grades and range; double LMB opens details. Start clears projections.

To disable, exit and remove the plugin DLL. Remove our shared dinput8.dll only after all our DLL mods are removed. The predictor installs no UserMODs file.

### Compatibility and development

October4,2026 checkpoint: DLL baca89 implementssource-simple fallback source-simple fallback with native army rectangle and preserved partial cells.240 synthetic native mixed comparisons and selector counterexample pass; full58/58 pass. Live generated Archer40→20+20 matches2/2 with normal exit but did not require fallback. Forced live fallback/new broad matrix remain;273/273 belongs to prior a8d794.

October4,2026 checkpoint: ten fresh loads on current DLL a8d794 yield **273/273 exact** battles(mixed213/213,solo60/60), all normally closed. Independent strict Superadmin verification passes original forecasts frozen before Start/current hashes/full pack coverage. Verdict goal_completefalse retains remaining branches/live equality/full-algorithm requirements. Legacy CLI exit1 is its old acceptance flag; do not alter preserved JSON. No release published.

October4,2026 checkpoint: native SDK levelup-state replaces OCR for the specific level modal check. Current DLL a8d794 matches72/72 complete formations across all36 cases with Angels10 and Peasant1000, including return/normal exit. Native55/55,SDK45/45 pass. A real forced1→2 modal is verified separately; ten-load protocol and remaining branches are open.

October4,2026 checkpoint: DLL a8d794 binds original scripted descriptors to the trusted placement window and predicts before Start. Native54/54 pass; six requested scenes match6/6 battles and18/18 units for one80/35/12 army. Each game exits normally directly after the snapshot. Results/adventure return is unverified; full36/hero/ten-load and remaining branches stay open. Ordinary inputs remain unchanged; not ready for release.

October3,2026 checkpoint: research DLLfb8e74 adds Superadmin capture of original StartCombat arguments before construction. SourceTrace ABI7(58 words) distinguishes map-neutral/scripted inputs and unknown modifiers; InputTrace15/ProjectionTrace8 remain. Native54/54 pass. Scripted80/35/12 capture is live-verified, but its window binding/forecast are unfinished. Normal pack_4 forecast matches3/3 before results checking rejects a blank frame; the run is incomplete. Ordinary inputs are unchanged; this is not a release. See the RU/EN research diary for evidence and limits.

Research Superadmin: `H5_PREVIEW_SUPERADMIN=1` at test-game startup enables a separate pre-Start source-stack trace. Read it with diagnostic `workshop_preview_loader.exe --pid PID --dll PATH --admin-source-trace`. Ordinary startup returns an empty list. This is **an input investigation tool**, not a certified exact predictor;100/100 remains unverified.

Final acceptance runs **ten fresh map loads**, testing every selected solo and mixed pack on each map. It rotates WorkshopPolygon and two tagged copies of Universe RMG maps; source RMG maps and creature armies remain intact. A battle counts only when every occupied cell matches; grades are reported separately, while splitting is an expected but counted miss with its own explanation. The primary gate requires at least70% of **mixed** battles to match fully; solo packs have separate statistics. `python -X utf8 scripts/accuracy-campaign.py` writes detailed JSON. The pre-push hook runs `--verify-latest` and rejects evidence made stale by source/DLL/loader/map changes or unexplained misses. The current release has not passed this campaign.

The local September26 candidate DLL is not in preview.2. Its C++ code uses the known hero army, own hero Attack/Battle Frenzy and public qualitative neutral-count bands to estimate spread and defence. It never reads hidden exact neutral counts, upgrades or splitting. The last complete ten-load run matched **111/149 mixed formations (74.5%)**, but the strict gate rejected two unexplained misses, and two seven-stack fights matched only3/7 exact type+cell pairs. A later run stopped on a transient module-snapshot error before round6; a bounded retry was added to the diagnostic loader. An unverified guard-row edit was reverted after sandbox startup crashes; the restored source passed14 native checks but its rebuilt DLL still needs a fresh live control. This candidate is **not ready for release**. [Evidence and limits](https://xaaalera.github.io/heroes5-knowledge/en/reference/research-diary/#rmg-placement-check).

Four pinned game hashes define compatibility. A mismatch or module initialization failure reports an error and cancels startup. Game hashes do not authenticate arbitrary plugin DLLs. The SDK revision above identifies the published preview.2 verification.

Normal H5_Game.exe startup reached the menu with automatic DLL loading; five instrumented battle/card/cleanup cycles then passed through the ordinary game process with both DLL mods present. This is bounded combined-use evidence, not all-arena/all-bank certification. The early published preview.2 mixed-pack run matched1 of7 positions and one predicted stack split; the newer unreleased candidate is described above. Exact placement is not guaranteed. The Heroes/Lobby interface itself was not separately automated.

Developer prerequisites and commands are shared above. Default install contains DLLs only; the old EXE remains a diagnostic target and requires explicit --component Diagnostics installation. The14 native checks allow only the documented absent-game oracle skip. H5_WORKSPACE selects the prepared sandbox for that oracle.

Use native-preview-check.py --auto-load after installing sandbox DLLs. Test-time Python/diagnostic inspection is not player runtime. Do not combine legacy --native-loader injection with automatic DLL loading. SDK --control --observe-deployment records actual Start positions separately from prediction inputs.

In a linked workshop, this mod's devkit path is a junction to the single top-level SDK. Run the workshop's `scripts/sync-subrepos.ps1 -Check`, repairing without `-Check`. Current HEAD/gitlink define the version; do not copy shared edits between repos. Standalone clones retain normal submodules. Before a new release commit the SDK changes, synchronize pins and reverify consumers.

An explicit `H5_PREVIEW_DEVKIT=<devkit-checkout>` can select a locally edited SDK for research without changing the pinned gitlink. `accuracy-campaign.py --background` requests a no-activation window and verifies off-screen placement/focus through that SDK. The first live check was refused when the game reclaimed focus/cursor clipping; the corrected helper has not yet been verified in-game. The final `--verify-latest` gate accepts only the pinned devkit, never the local override.

## Standalone use / Работа вне мастерской

RU: этот репозиторий можно использовать отдельно. Начни с его README и AGENTS.md; глобальная папка мастерской не обязательна. Если есть .gitmodules, выполни `git submodule update --init --recursive` после клонирования. В связанной мастерской используй её sync-subrepos вместо создания вторых checkout.
EN: This repository can be used independently. Start with its README and AGENTS.md; the global workshop is optional. If .gitmodules exists, initialize pinned dependencies with `git submodule update --init --recursive`. In a linked workshop use its canonical dependency synchronization.

- [Devkit commands / команды SDK](https://github.com/Xaaalera/heroes5-mod-devkit/blob/main/docs/commands.md).
- [Game API contracts / контракты библиотеки](https://github.com/Xaaalera/heroes5-game-api/blob/main/docs/mechanisms/game-bindings.md).
- [Research index / карта исследований](https://xaaalera.github.io/heroes5-knowledge/reference/research-index/).

[Code standards / стандарты кода](https://github.com/Xaaalera/claude-skills).
