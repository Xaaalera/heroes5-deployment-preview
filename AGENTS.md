# Agent instructions: native deployment preview

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
