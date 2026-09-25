# Heroes V Deployment Preview

## RU

Предиктор расстановки для [Heroes V Universe](https://h5lobby.com/). До Start показывает проекции известных типов противника, карточки грейдов и область хода. Скрытые количества и грейды не раскрывает; фактическое разделение армии может отличаться. [Возможности, изображения и ограничения](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/).

### Игроку: установка и удаление

Поставка — DLL для обычного запуска через **Heroes/Lobby**, без отдельного EXE нашего мода. [Releases](https://github.com/Xaaalera/heroes5-deployment-preview/releases) содержит выпуски; Code → Download ZIP скачивает исходники. Старый EXE-кандидат отменён. Версия 0.1.0-preview.2 экспериментальная.

1. Закрой игру. Файлы пакета: bin/dinput8.dll и bin/Heroes5Mods/WorkshopDeploymentPreview.dll в папке установленной игры.
2. Общий dinput8.dll нужен один раз для обоих наших модов. Не перезаписывай файл другого мода с этим именем: совместимость не проверена. Штатные d3d9.dll, uni.dll, um.dll не заменяются.
3. Запускай Heroes/Lobby как раньше. В обычном бою до Start должны появиться проекции. Python, Git и компилятор игроку не нужны.

Первый ПКМ открывает карточку базового или известного грейда; повторный переключает неопределённые варианты и дальность. Двойной ЛКМ открывает подробное окно. После Start проекции исчезают.

Для отключения закрой игру и убери bin/Heroes5Mods/WorkshopDeploymentPreview.dll. Общий bin/dinput8.dll удаляй после всех наших DLL-модов и только если он установлен из нашего пакета. В UserMODs предиктор ничего не ставит.

### Совместимость и проверка

Поддерживается [закреплённая сборка](https://xaaalera.github.io/heroes5-knowledge/reference/universe-build/), определённая четырьмя SHA-256. Несовпадение или отказ модуля прекращает запуск с сообщением. Хеши игры не удостоверяют происхождение сторонних DLL.

SDK закреплён на [71509e4](https://github.com/Xaaalera/heroes5-mod-devkit/tree/71509e43af0faf080d8a47ed5b3ff8c72da2a3e9). Проверены обычный H5_Game.exe до меню и автоматическая загрузка DLL; затем пять циклов загрузки боя, карточек и очистки через обычный процесс игры с тестовыми командами и наблюдателем. Второй мод был загружен одновременно. Это ограниченная проверка совместной работы, не гарантия всех арен и хранилищ. В текущем прогоне смешанного пака совпала 1 из 7 позиций; один прогнозируемый отряд разделился на два. Точный прогноз всех клеток не обещается. Сам интерфейс Heroes/Lobby отдельно не автоматизировался.

### Разработчику

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

## EN

Deployment predictor for the linked Universe build. Before Start it shows public creature-type projections, upgrade cards and movement range; it does not reveal hidden quantities/upgrades or guarantee the game's stack splitting. See the linked wiki for images, controls and limits.

### Player installation

Use the DLL package from Releases, not the source ZIP or withdrawn EXE candidate. Version 0.1.0-preview.2 is experimental. Exit the game; place bin/dinput8.dll and bin/Heroes5Mods/WorkshopDeploymentPreview.dll under the installed game directory. Both mods share one bootstrap. Never overwrite another mod's dinput8.dll without compatibility checks; original d3d9.dll, uni.dll and um.dll stay unchanged.

Start through Heroes/Lobby as usual. No separate mod EXE, Python, Git or compiler is required. First RMB opens the base/known grade card; repeated RMB cycles uncertain grades and range; double LMB opens details. Start clears projections.

To disable, exit and remove the plugin DLL. Remove our shared dinput8.dll only after all our DLL mods are removed. The predictor installs no UserMODs file.

### Compatibility and development

Four pinned game hashes define compatibility. A mismatch or module initialization failure reports an error and cancels startup. Game hashes do not authenticate arbitrary plugin DLLs. The shared SDK revision above is pinned.

Normal H5_Game.exe startup reached the menu with automatic DLL loading; five instrumented battle/card/cleanup cycles then passed through the ordinary game process with both DLL mods present. This is bounded combined-use evidence, not all-arena/all-bank certification. The current mixed-pack run matched 1 of 7 positions, and one predicted stack split into two. Exact placement is not guaranteed. The Heroes/Lobby interface itself was not separately automated.

Developer prerequisites and commands are shared above. Default install contains DLLs only; the old EXE remains a diagnostic target and requires explicit --component Diagnostics installation. Nine C++/x86 tests allow only the documented absent-game oracle skip. H5_WORKSPACE selects the prepared sandbox for that oracle.

Use native-preview-check.py --auto-load after installing sandbox DLLs. Test-time Python/diagnostic inspection is not player runtime. Do not combine legacy --native-loader injection with automatic DLL loading. SDK --control --observe-deployment records actual Start positions separately from prediction inputs.
