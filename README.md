# Heroes V Deployment Preview

## RU

Экспериментальный прогноз расстановки противника до Start. Обычный режим использует доступную игроку информацию. В проверенных обычных охранах «Разведка» или надетая «Корона всевидящего» разрешают точный исходный состав; иначе используются видимые диапазоны. Скрытые грейды и готовое разделение нейтралов в прогноз не поступают.

## EN

Experimental prediction of enemy placement before Start. Ordinary prediction uses player-visible information. For the tested ordinary guards, Scouting or an equipped Crown of the All-Seeing permits exact source composition; otherwise it uses visible quantity ranges. Hidden upgrades and the final neutral split do not enter the forecast.

## Документация / Documentation

- [Описание, установка и ограничения](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/) · [English](https://xaaalera.github.io/heroes5-knowledge/en/players/deployment-preview/).
- [Готовые выпуски / Releases](https://github.com/Xaaalera/heroes5-deployment-preview/releases).
- [SDK xkit](https://xaaalera.github.io/heroes5-knowledge/modding/devkit/).
- [Самостоятельный клон и зависимости / Standalone clone and dependencies](https://xaaalera.github.io/heroes5-knowledge/modding/native-projects/).
- [Команды SDK / SDK commands](https://xaaalera.github.io/heroes5-knowledge/reference/xkit-commands/).
- [Game API](https://xaaalera.github.io/heroes5-knowledge/reference/game-api/).
- [Карта исследований / Research index](https://xaaalera.github.io/heroes5-knowledge/reference/research-index/).

Предиктор собирается через xkit, а готовый [выпуск alpha.1](https://github.com/Xaaalera/heroes5-deployment-preview/releases/tag/v0.2.0-alpha.1) запускается обычным способом без SDK. До Start показывается приблизительная расстановка; после начала боя нативная кнопка «Расстановка» открывает прогноз и фактические позиции с пояснениями. Результаты проверок и ограничения выпуска находятся в [руководстве игрока](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/). Изменения рабочей ветки не меняют опубликованный архив. Обязательные границы — в [архитектурном контракте](https://xaaalera.github.io/heroes5-knowledge/modding/native-projects/#architecture-contract).

The predictor builds through xkit; the [alpha.1 release](https://github.com/Xaaalera/heroes5-deployment-preview/releases/tag/v0.2.0-alpha.1) uses the normal game launch without the SDK. Before Start it shows an approximate formation. Once combat starts, the native “Расстановка” button opens the forecast and actual positions with explanations. The [player guide](https://xaaalera.github.io/heroes5-knowledge/en/players/deployment-preview/) records the release's test results and limits. Working-branch changes do not alter the published archive. Follow the [required architecture contract](https://xaaalera.github.io/heroes5-knowledge/en/modding/native-projects/#architecture-contract).

Текущие инструкции находятся только на сайте. Каждый мод устанавливается отдельно с указанными общими зависимостями; исходники не являются готовым игровым пакетом.

The website owns the living instructions. Each mod installs independently with its stated shared dependencies; source downloads are not player packages.

## Standalone use / Работа вне мастерской

Закреплённые зависимости / Pinned dependencies: [xkit `1de5840`](https://github.com/Xaaalera/heroes5-mod-devkit/tree/1de5840eb0dbfd4d4a08612306874e3179883426) · [Game API `43af625`](https://github.com/Xaaalera/heroes5-game-api/tree/43af62523fa19fc93b8be60bff9ff6cf7888f134).

После клонирования выполни `git submodule update --init`. Глобальная мастерская не обязательна. Если ветка объявляет корневую `game-api`, путь `devkit/game-api` должен ссылаться на неё, а не содержать вторую копию; версии должны соответствовать закреплённым коммитам. Различия старых веток описаны в инструкции самостоятельного клона на сайте. В общей мастерской зависимости проверяет её `sync-subrepos`. Рабочие правила — в [AGENTS.md](AGENTS.md).

After cloning, run `git submodule update --init`. The global workshop is optional. Where the branch declares a root `game-api`, `devkit/game-api` must reference that checkout with consistent pins. The site's standalone-clone guide explains older branches; shared workshop checkouts use its canonical dependency synchronization.

## Проекты и контакты / Projects and contacts

- [Предиктор / Deployment predictor](https://github.com/Xaaalera/heroes5-deployment-preview).
- [Справочник / Bank reference](https://github.com/Xaaalera/heroes5-bank-reference).
- [SDK xkit](https://github.com/Xaaalera/heroes5-mod-devkit).
- [Game API source](https://github.com/Xaaalera/heroes5-game-api).
- [Исходники базы / Knowledge source](https://github.com/Xaaalera/heroes5-knowledge) · [сайт / website](https://xaaalera.github.io/heroes5-knowledge/).
- [Стандарты / Code standards](https://github.com/Xaaalera/claude-skills).
- [Universe / Heroes Lobby](https://h5lobby.com/).

[Xaaalera](https://github.com/Xaaalera) · [email](mailto:dampirsimpl@gmail.com) · [Telegram](https://t.me/Victima). Наши проекты не являются официальными продуктами Universe. / Our projects are unofficial Universe tools.
