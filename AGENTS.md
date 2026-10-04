# Agent instructions: native deployment preview


## Public projects / Публичные проекты

- [Deployment Preview / Предиктор](https://github.com/Xaaalera/heroes5-deployment-preview): native placement projections.
- [Bank Reference / Справочник армий](https://github.com/Xaaalera/heroes5-bank-reference): possible bank armies.
- [Mod Devkit / Девкит](https://github.com/Xaaalera/heroes5-mod-devkit): shared tools used to build and test both DLL mods.
- [Knowledge / База знаний](https://github.com/Xaaalera/heroes5-knowledge) · [public site / сайт](https://xaaalera.github.io/heroes5-knowledge/).
- [Author / Автор — Xaaalera](https://github.com/Xaaalera) · [email](mailto:dampirsimpl@gmail.com) · [personal Telegram / личный Telegram](https://t.me/Victima).
- [Heroes V Universe / Heroes Lobby](https://h5lobby.com/).

RU: эти проекты принадлежат автору; база знаний и моды не являются официальными продуктами Universe. Общие факты и контакты обновлять во всех канонических репозиториях. EN: These are the author's projects, not official Universe products. Keep shared facts and contact links consistent across canonical repositories.

## RU

- В мастерской `devkit/` этого мода — ссылка на единственный корневой SDK; версия берётся из его HEAD и gitlink, общие незакоммиченные правки видны всем потребителям. Перед сборками/тестами из корня мастерской запускать `scripts/sync-subrepos.ps1 -Check`. Не создавать вторую копию и не копировать общие файлы. После коммита SDK синхронизировать gitlink и проверить потребителя; самостоятельный клон использует закреплённый submodule.

- Приоритет владельца, 2 октября 2026: восстановить полный алгоритм; суперадминский прогноз до Start должен совпадать целиком в100% боёв. Все несостыковки документировать. Разрешены специальные армии для проверки теорий; полигон содержит36 составов. Входы/выдачу обычного режима обсудить отдельно; не вводить новые сокращения. Номера рядов отложены.

- Последнее указание владельца: тестировать обычным видимым запуском песочницы — открыть игру, выполнить команды, закрыть игру; больше не заниматься фоновым/off-screen запуском. Разрешение на этот цикл уже дано, повторно не спрашивать. Перед запуском проверять, что нет другого `H5_Game.exe`; к игре владельца не подключаться. Предположительная правка циклической группы стрелков отменена после двух сбоев запуска 26 сентября; восстановленный исходник прошёл нативные тесты, но пересобранная DLL ещё требует нового живого контроля. Не повторять один и тот же сбой запуском по кругу. Новейшие результаты — в корневом `docs/2026-09-23-handoff.md`.

- Владелец разрешил отдельный исследовательский режим «суперадмин». Текущий первый этап реализован: `H5_PREVIEW_SUPERADMIN=1` позволяет читать исходные типы/количества объекта до Start через отдельный экспорт; обычный режим отдаёт пустой список. Точный прогноз ещё не реализован. Цель —100/100 полных совпадений предсказания, зафиксированного ДО Start. After-Start снимок — только проверка, никогда не вход готового прогноза. Не заявлять100% до живой проверки.

- Уточнение владельца: финальный прогон — десять свежих загрузок WorkshopPolygon и помеченных RMG-карт. На каждой проверить все отобранные одиночные и смешанные паки. Зачёт боя — полное совпадение клеток; грейд не штрафуется, разделение считается ожидаемым промахом с доказанной причиной. Главный порог≥70% смешанных боёв; одиночные отдельно. Перед push выполнить `accuracy-campaign.py` и его `--verify-latest`; хук проверяет свежесть JSON по хешам.

- С 25 сентября 2026 владелец разрешил учитывать известную армию своего героя (включая количества). Скрытые грейды, количества и факт разделения нейтралов по-прежнему не читаются и не раскрываются. Собственные записи CPlacementInfo отделять от диагностического наблюдения после Start. Python остаётся инструментом стенда, игровой расчёт — в C++ DLL.

- Пользователь запускает игру обычным способом через Heroes/Lobby. Наши моды подключаются через DLL; отдельный EXE для игрока запрещён владельцем. Диагностические EXE и Python-команды принадлежат только инструкциям разработчика. При смене поставки синхронизировать README, RU/EN wiki, devkit, инструкции агентам и release notes; прежние EXE-пакеты не публиковать.

- Читать README.md, CONTRIBUTING.md и devkit/AGENTS.md. Devkit закреплён gitlink; не обновлять его молча до main. При обновлении фиксировать проверенную ревизию в README.
- Сохранять исходные игровые файлы. Не использовать скрытый состав охраны как вход прогноза/справки. Игра и её данные не входят в репозиторий.
- Установка и тесты используют разные режимы: build/эмуляция не равны свежему игровому подтверждению. В отчёте показывать passed/failed/skipped и непроверенное. Физический ввод не заменяется PostMessage.
- Изолированные проверки: requirements-dev.txt и scripts/check.py. Для предиктора сначала нужна x86 Release-сборка; отсутствие компилятора/артефакта не считать PASS. Единственный допустимый пропуск у предиктора — явно отмеченный game-EXE oracle, когда игры нет.
- Не запускать живой сценарий как часть unit-тестов, не забирать общий курсор без согласованного интервала. Следовать авторизованной задаче; обычные безопасные действия не требуют повторных подтверждений.
- Обязательное независимое review перед push описано в CONTRIBUTING.md; не выдумывать отчёты. RU/EN и wiki-ссылки поддерживаются вместе.

## EN

- In the workshop this mod's devkit is a junction to the single top-level SDK; its HEAD/gitlink define the version and uncommitted edits are shared by all consumers. Run the workshop's `scripts/sync-subrepos.ps1 -Check` before builds/tests. Never create a second copy or copy shared files. After an SDK commit align pins and reverify this consumer; standalone clones retain pinned submodules.

- October 2, 2026 owner priority: reconstruct the complete algorithm and100% whole-pack Superadmin predictions frozen before Start. Record every discrepancy. Authored theory armies are authorized; the polygon has36 compositions. Ordinary input/output policy is deferred; do not introduce new reductions. Row ranks remain deferred.

- Latest owner workflow: use the ordinary visible sandbox launch, run the test commands, then close that game; stop background/off-screen startup experiments. Authorization persists without another permission request. Refuse any second `H5_Game.exe` and never attach to the owner's game. A tentative cyclic-shooter guard change preceded two September26 startup crashes and was reverted; restored source passed native checks but the rebuilt DLL still needs a fresh live control. Do not repeat the same crash in a launch loop. Read the newest root `docs/2026-09-23-handoff.md` entry.

- Owner authorized separate Superadmin research. Stage one is implemented: `H5_PREVIEW_SUPERADMIN=1` allows an explicit pre-Start source type/quantity trace; ordinary mode exposes no stacks. An exact predictor is still unfinished. The admin target is100/100 complete matches for predictions frozen BEFORE Start. After-Start snapshots are validation only. Do not claim100% before live verification.

- Owner correction: ten fresh loads rotate authored and RMG maps, testing all selected solo/mixed packs on each. A battle counts only if all occupied cells match. Grades do not penalize spatial accuracy; a proven split is a labelled miss. Require≥70% full matches among mixed packs; track solos separately. Run `accuracy-campaign.py` and `--verify-latest` before push; the hook checks JSON freshness by hashes.

- On September25,2026 the owner authorized the known player hero army, including quantities, as prediction input. Hidden neutral upgrades, counts and splitting remain unread and undisclosed. Keep own CPlacementInfo records separate from after-Start diagnostic observation. Python is test tooling; gameplay calculations belong in the C++ DLL.

- Players keep the ordinary Heroes/Lobby launch. Our mods load through DLLs; the owner rejects separate player launchers. Diagnostic EXEs and Python commands belong only in developer instructions. Delivery changes must update README, RU/EN wiki, devkit, agent instructions and release notes together; never publish the superseded EXE packages.

Read README, CONTRIBUTING and devkit/AGENTS. Devkit is pinned: do not silently track latest main; update the tested revision when changing it. Preserve game files and exclude hidden guard composition from prediction/reference inputs. Do not publish game data.

Build/emulation and a fresh game run are different evidence. Report passed/failed/skipped and unverified scope; PostMessage is not physical-input acceptance. Use requirements-dev and scripts/check.py; predictor needs an x86 Release build first. Missing tools/artifacts cannot yield PASS. Only its explicitly identified absent-game oracle may be skipped.

Unit checks do not launch a game or commandeer shared input. Work within the authorized task without repeated confirmation for ordinary safe actions. Independent pre-push review is mandatory; preserve RU/EN and wiki links.
