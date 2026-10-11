---
theme: none
title: Лаборатория протоколов
info: |
  Восстановление недокументированного бинарного протокола поверх TCP.
  UMIRHack 2026, кейс #02, Мадригал. Команда HTTP 418.
class: text-left
highlighter: shiki
lineNumbers: false
drawings:
  persist: false
transition: fade
colorSchema: dark
mdc: true
fonts:
  sans: Montserrat
  mono: JetBrains Mono
---

<div class="cover">

<div class="cover__brand">
<img src="/logo.svg" alt="Логотип проекта" class="cover__logo">
<span class="cover__name">madrigal-protocol-lab</span>
</div>

# Лаборатория протоколов

<div class="cover__sub">Восстановление недокументированного бинарного протокола поверх TCP</div>

<div class="cover__rule"></div>

<div class="cover__meta">
<span class="chip">UMIRHack 2026</span>
<span class="chip">кейс #02</span>
<span class="chip">Мадригал</span>
<span class="chip">команда HTTP 418</span>
</div>

</div>

---
layout: default
---

# Нас двое

<div class="team">

<div class="member" v-click>
<img src="/team-avatar-round.png" alt="Сабадаш Павел" class="member__photo">
<div class="member__info">
<div class="member__name">Сабадаш Павел</div>
<div class="member__role">Архитектура · захват · интерфейс</div>
<div class="member__handle">@Pasha1778</div>
</div>
<img src="/qr_telegram_pasha.png" alt="QR: @Pasha1778" class="member__qr">
</div>

<div class="member" v-click>
<img src="/team-avatar-round.png" alt="Предков Никита" class="member__photo">
<div class="member__info">
<div class="member__name">Предков Никита</div>
<div class="member__role">Правила · тесты · ревью</div>
<div class="member__handle">@petruan</div>
</div>
<img src="/qr_telegram_nikita.png" alt="QR: @petruan" class="member__qr">
</div>

</div>

---
layout: default
---

<div class="statement">

<div class="kicker">Постановка задачи</div>

# TCP разрезает сообщения посередине

<div class="statement__sub">Границы пакета и границы сообщения — разные вещи</div>

<div class="statement__figure" v-click>
<img src="/assets/tcp_framing.svg" alt="Пакет 1, 2, 3 и два сообщения: границы не совпадают">
</div>

</div>

---
layout: default
---

# Дано и требуется

<div class="given">

<div class="panel panel--accent">
<div class="lead">Дано</div>
<ul>
<li v-click>Захваты <code>pcap</code>/<code>pcapng</code> и журнал действий устройства</li>
<li v-click>Спецификации протокола нет</li>
</ul>
</div>

<div class="panel panel--accent">
<div class="lead">Требуется</div>
<ul>
<li v-click>Проверяемая интерпретация структуры сообщений</li>
<li v-click>Видно, где чтение верно, а где перестаёт работать</li>
</ul>
</div>

</div>

---
layout: default
---

<div class="moment">

<div class="kicker">Ход работы</div>

# Смещение поля длины оказалось на четыре байта позже, чем мы считали

<div class="moment__sub">Одно правило, два чтения: поле длины остаётся на offset 2</div>

<div class="moment__figure" v-click>
<img src="/assets/length_offset.svg" alt="Байты 01 00 00 03 13 00 55 и два конкурирующих чтения">
</div>

<div class="steps" v-click>
<span class="on">наблюдение</span>
<span class="on">гипотеза</span>
<span class="on">проверка</span>
<span class="on">контрпример</span>
<span class="on">уточнение</span>
</div>

</div>

---
layout: default
---

# Три модуля связаны форматами, а не вызовами

<div class="arch">

<div class="arch__box" v-click>
<div class="arch__name">capture</div>
<div class="arch__desc">pcap/pcapng → сессии<br>reassembly, provenance</div>
</div>

<div class="arch__arrow" v-click><span>JSON</span>→</div>

<div class="arch__box" v-click>
<div class="arch__name">protocol + hypothesis</div>
<div class="arch__desc">правила, фрейминг<br>контрпримеры, версии</div>
</div>

<div class="arch__arrow" v-click><span>JSON</span>→</div>

<div class="arch__box" v-click>
<div class="arch__name">ui</div>
<div class="arch__desc">окно PySide6<br>исследование и просмотр</div>
</div>

</div>

<div class="caption" v-click>Контракты между модулями зафиксированы схемами JSON; порядок вызовов не важен</div>

---
layout: default
---

# Каждый байт знает свой пакет

<div class="shot shot--side">

<div class="shot__frame" v-click>
<img src="/public/screenshot-provenance.png" alt="Дерево сессий, байты и панель происхождения">
</div>

<div class="shot__side">

<div class="panel" v-click>
<div class="lead">Происхождение</div>
<div>Клик по байту связывает его с пакетом, номером последовательности и временем.</div>
</div>

<div class="byte-card" v-click>
<div class="byte-mono">packet 3 · seq 1001</div>
<div class="byte-note">ts 1700000000.004, сессия <code>s1</code></div>
</div>

</div>

</div>

<div class="caption">От интерпретации можно вернуться к исходным данным. Повторные передачи одного сообщения — отдельная тема.</div>

---
layout: default
---

# Правило проверяется на всём корпусе сразу

<div class="pair">

<div class="shot__frame" v-click>
<img src="/public/screenshot-rule.png" alt="Редактор правила">
</div>

<div class="shot__frame" v-click>
<img src="/public/screenshot-validation.png" alt="Результат применения правила">
</div>

</div>

<div class="caption" v-click>Одно правило описывает весь поток; сообщения не перечисляют вручную</div>

---
layout: default
---

# Контрпример важнее метрики

<div class="kicker">4 независимых сессии + журнал действий устройства</div>

<div class="shot shot--side">

<div class="shot__frame" v-click>
<img src="/public/screenshot-counterexamples.png" alt="Список контрпримеров, привязанных к байту">
</div>

<div class="shot__side">

<div class="byte-card" v-click>
<div class="byte-mono">02 00 00 03 13 00 55</div>
<div class="byte-note">Команда <code>2</code> вне ожидаемого набора <code>[1]</code></div>
</div>

<div class="panel" v-click>
<div class="lead">Один байт — 80 контрпримеров</div>
<div>Все 80 несоответствий v1 сидели на offset 0 в сессиях <code>s2</code> и <code>s3</code>.</div>
</div>

</div>

</div>

---
transition: slide-left
layout: default
---

<div class="divider">

<div class="index">01</div>

# Что получилось

<div class="bar"></div>

<div class="divider__note">Точность, покрытие корпуса организаторов, ресурсы</div>

</div>

---
layout: default
---

<div class="metric">

# Уточнили правило: 60/140 → 140/140

<div class="metric__grid">

<div>
<div class="bignum" v-click>1.00</div>
<div class="metric__note" v-click>Было 60 matched из 140 и 80 контрпримеров. Стало 140 matched из 140 и ноль контрпримеров</div>
</div>

<div class="bars" v-click>
<div class="bars__row">
<span class="bars__label">v1</span>
<span class="bars__track"><i class="bars__fill bars__fill--bad" style="width: 43%"></i></span>
<span class="bars__value">0.43</span>
</div>
<div class="bars__row">
<span class="bars__label">v2</span>
<span class="bars__track"><i class="bars__fill bars__fill--good" style="width: 100%"></i></span>
<span class="bars__value">1.00</span>
</div>
</div>

</div>

</div>

---
layout: default
---

<div class="metric">

# Набор организаторов разобран целиком

<div class="metric__grid">

<div>
<div class="bignum" v-click>90</div>
<div class="metric__note" v-click>45 запросов и 45 ответов, все matched, покрытие байтов 100 %</div>
</div>

<div class="metric__figure" v-click>
<img src="/assets/coverage_donut.svg" alt="Пончик: 45 запросов и 45 ответов, 0 неприменимых">
</div>

</div>

</div>

---
layout: default
---

<div class="metric">

# 95 МиБ разбираются за 12 секунд

<div class="metric__grid">

<div>
<div class="bignum" v-click>12 с</div>
<div class="metric__note" v-click>Условия замера: 95.66 МиБ, 250 000 пакетов, 1000 сессий, 4 vCPU / 16 ГиБ</div>
</div>

<div class="metric__figure" v-click>
<img src="/assets/memory_sweep.svg" alt="Свип памяти: regular и streaming">
</div>

</div>

<div class="metric-row">
<span v-click><b>12.1 с</b> общее время</span>
<span v-click><b>350 МиБ</b> пик памяти</span>
<span v-click><b>4 ГиБ</b> бюджет</span>
</div>

</div>

---
transition: slide-left
layout: default
---

<div class="divider">

<div class="index">02</div>

# Демонстрация

<div class="bar"></div>

<div class="divider__note">Живое окно и запись прогона</div>

</div>

---
layout: default
---

<div class="live">

# Живое окно

<div class="live__frame" v-click>
<img src="/public/screenshot-main.png" alt="Главное окно: сессии, байты, интерпретация, диагностика">
</div>

<div class="caption" v-click>Сессии, байты, интерпретация, происхождение и диагностика в одном окне</div>

</div>

---
layout: default
---

# Запись прогона на случай, если экран не поднимется

<video src="/screencast.mp4" controls muted loop playsinline class="cast"></video>

<div class="caption">Четыре минуты: шесть сцен референсного исследования</div>

---
transition: slide-left
layout: default
---

<div class="divider">

<div class="index">03</div>

# Границы и итог

<div class="bar"></div>

<div class="divider__note">Что мы не утверждаем и что осталось за рамками</div>

</div>

---
layout: default
---

# Что мы не утверждаем

<div class="limits">

<div>
<ul>
<li v-click>Смысл байта флагов не установлен: в корпусе он постоянен</li>
<li v-click>Поле значения остаётся гипотезой, а не фактом</li>
</ul>
</div>

<div>
<ul>
<li v-click>Альтернативные чтения берутся из заданного набора</li>
<li v-click>Интерпретация верна для проверенных захватов и молчит вне них</li>
</ul>
</div>

</div>

---
layout: default
---

<div class="closing">

# Инструмент превращает байты в проверяемое знание

<div class="qr-grid">

<div class="qr-item" v-click>
<img src="/qr_repo.png" alt="QR: репозиторий">
<div class="caption">Репозиторий</div>
</div>

<div class="qr-item" v-click>
<img src="/qr_release.png" alt="QR: релиз v1.0.0">
<div class="caption">Релиз v1.0.0</div>
</div>

<div class="qr-item" v-click>
<img src="/qr_telegram_pasha.png" alt="QR: Telegram Павла">
<div class="caption">@Pasha1778</div>
</div>

<div class="qr-item" v-click>
<img src="/qr_telegram_nikita.png" alt="QR: Telegram Никиты">
<div class="caption">@petruan</div>
</div>

</div>

<div class="closing__line">github.com/Pavel1778/madrigal-protocol-lab</div>

</div>
