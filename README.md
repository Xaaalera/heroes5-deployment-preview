# Heroes V Deployment Preview

## RU

Экспериментальный прогноз расстановки противника до Start. Обычный режим использует доступную игроку информацию; скрытые количества, грейды и готовую разбивку нейтралов не читает.

## EN

Experimental prediction of enemy placement before Start. Ordinary prediction uses player-visible information, without reading hidden counts, grades or the final neutral split.

## Документация / Documentation

- [Описание, установка и ограничения](https://xaaalera.github.io/heroes5-knowledge/players/deployment-preview/) · [English](https://xaaalera.github.io/heroes5-knowledge/en/players/deployment-preview/).
- [Готовые выпуски / Releases](https://github.com/Xaaalera/heroes5-deployment-preview/releases).
- [SDK xkit](https://xaaalera.github.io/heroes5-knowledge/modding/devkit/).
- [Самостоятельный клон и зависимости / Standalone clone and dependencies](https://xaaalera.github.io/heroes5-knowledge/modding/native-projects/).
- [Команды SDK / SDK commands](https://xaaalera.github.io/heroes5-knowledge/reference/xkit-commands/).
- [Game API](https://xaaalera.github.io/heroes5-knowledge/reference/game-api/).
- [Карта исследований / Research index](https://xaaalera.github.io/heroes5-knowledge/reference/research-index/).

Перенос предиктора на SDK xkit продолжается. Сохранность всех функций, точность новой сборки и готовность самостоятельного пакета проверяются отдельно; результаты прежних DLL не переносятся на неё. Обязательные границы — в [архитектурном контракте](https://xaaalera.github.io/heroes5-knowledge/modding/native-projects/#architecture-contract).

The xkit migration is in progress. Full feature parity, new-build accuracy and standalone-package readiness require separate checks; earlier DLL accuracy results do not transfer. Follow the [required architecture contract](https://xaaalera.github.io/heroes5-knowledge/en/modding/native-projects/#architecture-contract).

Текущие инструкции находятся только на сайте. Каждый мод устанавливается отдельно с указанными общими зависимостями; исходники не являются готовым игровым пакетом.

The website owns the living instructions. Each mod installs independently with its stated shared dependencies; source downloads are not player packages.

## Standalone use / Работа вне мастерской

Закреплённые зависимости / Pinned dependencies: [xkit `84bc5a1`](https://github.com/Xaaalera/heroes5-mod-devkit/tree/84bc5a10b1490e2e38470d85d8cf09d1d3bf151d) · [Game API `43af625`](https://github.com/Xaaalera/heroes5-game-api/tree/43af62523fa19fc93b8be60bff9ff6cf7888f134).

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
