# Heroes V Deployment Preview

## RU

Нативный прототип прогноза расстановки для Heroes V: Повелители Орды с **[Universe / Heroes V Lobby](https://h5lobby.com/)**. [Сообщество Universe](https://vk.com/h5universe) · [страница разработки Universe](https://boosty.to/verydobro).

До Start показывает проекции известных типов противника, справочные карточки и область хода выбранного грейда. Первый ПКМ открывает базовый/известный грейд, следующие переключают неопределённые варианты; двойной ЛКМ открывает подробное окно. Фигуры непрозрачные со слабым тёплым свечением. После Start проекции очищаются.

Это не точная разведка скрытой армии: разделение, грейды и специальные построения могут отличаться. Один публичный тип предполагается одним отрядом. [Поведение и ограничения в вики](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/) · [механика игры](https://xaaalera.github.io/heroes5-knowledge/players/army-placement/).

### Совместимость

Рабочий код — C++ DLL, Python не нужен для установленной пары EXE/DLL. Загрузчик сверяет SHA-256 `H5_Game.exe`, `uni.dll`, `um.dll`, `d3d9.dll`; [проверенная связка](https://xaaalera.github.io/heroes5-knowledge/reference/universe-build/). Надписи Universe 2.0 недостаточно. При несовпадении не отключай проверку и не заменяй игровые DLL.

Инструменты и тесты: [Heroes V Mod Devkit](https://github.com/Xaaalera/heroes5-mod-devkit), проверенная ревизия [1b8934a](https://github.com/Xaaalera/heroes5-mod-devkit/tree/1b8934ac084491da460ce8bb145819e41e2cf888); она закреплена submodule `devkit/`. Это версия среды разработки, не номер релиза Universe.

### Собрать из исходников

Нужны Windows, Visual Studio 2022 C++ Build Tools с x86 toolchain и CMake 3.21+. Открой **x86 Native Tools Command Prompt**, затем:

```bat
git clone --recursive https://github.com/Xaaalera/heroes5-deployment-preview.git
cd heroes5-deployment-preview
cmake -G "NMake Makefiles" -S . -B .local/build/deployment-preview-native -DCMAKE_BUILD_TYPE=Release
cmake --build .local/build/deployment-preview-native --config Release
cmake --install .local/build/deployment-preview-native --config Release --prefix .local/dist/deployment-preview-native
```

Получатся `WorkshopDeploymentPreview.dll` и `workshop_preview_loader.exe` в `.local/dist/deployment-preview-native/`. Репозиторий хранит исходники, не дистрибутив игры. В CI собирается та же пара; статус успешной сборки не означает новый игровой тест.

### Установить, запустить и удалить

1. Закрой игру. Скопируй **оба своих собранных файла** в отдельную папку мода, сохранив их рядом. Не помещай DLL в UserMODs и не заменяй `d3d9.dll`, `uni.dll`, `um.dll`.
2. Запусти загрузчик с путём к поддерживаемому EXE. Пример из корня клона, если игра лежит в соседнем `HeroesV-Universe`:

```powershell
.local/dist/deployment-preview-native/workshop_preview_loader.exe --game "../HeroesV-Universe/bin/H5_Game.exe"
```

3. Замени путь своей установленной игрой либо её тестовой копией. В обычном нападении на нейтрала проверь проекции **до** Start, карточку и её переключение. Сам запуск процесса не подтверждает результат.
4. Для отключения закрой игру и запусти обычный `H5_Game.exe` напрямую. Для удаления после выхода достаточно убрать два файла мода из их отдельной папки; игровые EXE/DLL загрузчик на диске не меняет.

Не запускай одновременно второй экземпляр игры ради теста. Режим `--pid` — диагностическое подключение к уже работающему процессу, а не рекомендуемый способ установки. Совместная работа со справочником хранилищ отдельно не проверена.

### Проверить исходники

В Python 3.10+ x64 окружении:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -X utf8 scripts/check.py
```

Сначала собери Release по командам выше. Скрипт запускает 9 проверок C++/x86, печатает JSON с результатами и пропусками. Без собственной игры разрешён только явно отмеченный пропуск сравнения с исходным EXE; отсутствие сборки, компилятора или зависимостей не даёт успешной приёмки. Для полного сравнения задай `H5_WORKSPACE` с подготовленной `.local/test-game` поддерживаемой сборки.

При переносе логика C++ сохранена; нормализованы только окончания строк и пустые строки в конце файлов, новая пара пересобрана; все 9 проверок прошли с локальным EXE-оракулом. Это эмуляция и сборка, не свежий живой бой после переноса. Исторические игровые результаты — [в дневнике](https://xaaalera.github.io/heroes5-knowledge/reference/research-diary/).

Живой сценарий для разработчика: подготовить полигон по [devkit](https://github.com/Xaaalera/heroes5-mod-devkit/blob/1b8934ac084491da460ce8bb145819e41e2cf888/README.md), установить пару в `H5_WORKSPACE/.local/dist/deployment-preview-native`, затем `python scripts/native-preview-check.py`. Он запускает/завершает игру и требует подходящего рабочего окружения; не выполнять его вместо unit-тестов. Основной тест использует адресные сообщения; физическая мышь — отдельный контроль. `H5_PREVIEW_BUILD` позволяет указать иной каталог собранной DLL для проверок; иначе используется `.local/build/deployment-preview-native` этого клона.

## EN

Native deployment-preview prototype for Heroes V: Tribes of the East with the linked Universe project. Before Start it displays projections for public creature types, reference cards, upgrade-dependent movement, double-click details and subtle warm opaque figures; Start cleans them up. It does not reveal hidden quantities/upgrades or guarantee final placement. See the wiki for behavior and limitations.

### Build and install

Use Windows, Visual Studio 2022 C++ x86 tools and CMake 3.21+. Run the shared clone/configure/build/install commands from an x86 Native Tools prompt. They produce the DLL and loader side by side in `.local/dist/deployment-preview-native`. The pinned devkit submodule revision above identifies the tested development environment, not a Universe version.

Close the game, put the two built files in a separate mod directory and keep them together. Run the shared `--game` command with your supported EXE path. Do not put the DLL in UserMODs or replace Universe DLLs. The loader validates all four pinned binary hashes; a version label alone is insufficient. Do not bypass mismatch rejection.

Check projections/card behavior in a normal neutral battle before Start. To disable, exit and run the ordinary game EXE directly. To uninstall, exit and remove the two mod files; game binaries are not patched on disk. Python is not required by the installed pair. Diagnostic --pid attachment and combined use with bank reference are not claimed as the normal tested installation path.

### Verification

Use the shared venv/pip/check commands after the Release build. Nine C++/x86 checks print JSON and explicit skips. Only the optional pinned-game movement oracle may be unavailable; missing build/compiler/dependencies cannot yield an accepted run. H5_WORKSPACE may identify a prepared sandbox, and H5_PREVIEW_BUILD may select a different compiled-artifact directory.

C++ logic was preserved; only line endings and trailing blank lines were normalized. The pair was rebuilt, and all nine checks passed with the local game oracle. No fresh live battle followed extraction. Historical observations stay in the diary. Developer live acceptance uses the devkit polygon and installed pair under H5_WORKSPACE, then scripts/native-preview-check.py; it launches/closes the game and is not a unit test. Physical input remains a separate check.
