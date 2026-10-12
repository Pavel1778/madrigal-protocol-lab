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
colorSchema: light
mdc: true
fonts:
  sans: Montserrat
  mono: JetBrains Mono
---

<div class="cover">

<div class="cover__brand">
<img src="/logo.svg" alt="Логотип проекта" class="cover__logo">
<span class="cover__name">madrigal-protocol-lab</span>
<img src="/madrigal-logo.png" alt="Мадригал" class="cover__client">
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

<div class="member">
<img src="/avatar_pavel_round.png" alt="Сабадаш Павел" class="member__photo" v-click>
<div class="member__info">
<div class="member__name">Сабадаш Павел</div>
<div class="member__role">Архитектура · захват · интерфейс</div>
<div class="member__contact">
<span class="member__handle">@Pasha1778</span>
<img src="/qr_telegram_pasha.png" alt="QR: @Pasha1778" class="member__qr">
</div>
</div>
</div>

<div class="member">
<img src="/avatar_nikita_round.png" alt="Предков Никита" class="member__photo" v-click>
<div class="member__info">
<div class="member__name">Предков Никита</div>
<div class="member__role">Правила · тесты · ревью</div>
<div class="member__contact">
<span class="member__handle">@petruan</span>
<img src="/qr_telegram_nikita.png" alt="QR: @petruan" class="member__qr">
</div>
</div>
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
<img src="/assets/tcp_framing-light.svg" alt="Пакет 1, 2, 3 и два сообщения: границы не совпадают">
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
<li>Спецификации протокола нет</li>
</ul>
</div>

<div class="panel panel--accent">
<div class="lead">Требуется</div>
<ul>
<li v-click>Проверяемая интерпретация структуры сообщений</li>
<li>Видно, где чтение верно, а где перестаёт работать</li>
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
<img src="/assets/length_offset-light.svg" alt="Байты 01 00 00 03 13 00 55 и два конкурирующих чтения">
</div>

<div class="steps" v-click>
<span class="on">наблюдение</span>
<span class="on">гипотеза</span>
<span class="on">проверка</span>
<span class="on">контрпример</span>
<span class="on">уточнение</span>
<span class="on">повторная проверка</span>
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

<div class="arch__arrow"><span>JSON</span>→</div>

<div class="arch__box" v-click>
<div class="arch__name">protocol + hypothesis</div>
<div class="arch__desc">правила, фрейминг<br>контрпримеры, версии</div>
</div>

<div class="arch__arrow"><span>JSON</span>→</div>

<div class="arch__box" v-click>
<div class="arch__name">ui</div>
<div class="arch__desc">окно PySide6<br>исследование и просмотр</div>
</div>

</div>

<div class="caption">Контракты между модулями зафиксированы схемами JSON; порядок вызовов не важен</div>

---
layout: default
---

# От интерпретации можно вернуться к исходным данным

<div class="shot__frame">
<img class="shot--full" src="/screenshot-provenance.png" alt="Байты сообщения и панель происхождения: пакет, последовательность, время">
</div>

<div class="byte-line">packet 3 · seq 1001 · сессия <code>s1</code></div>

---
layout: default
---

# Правило проверяется на всём корпусе сразу

<div class="pair">

<div class="shot__frame">
<img src="/screenshot-rule.png" alt="Правило в редакторе: JSON крупным планом">
</div>

<div class="shot__frame">
<img src="/screenshot-validation.png" alt="Результат применения правила к потоку">
</div>

</div>

---
layout: default
---

# Контрпример важнее метрики

<div class="kicker">4 независимые сессии в корпусе + журнал действий устройства</div>

<div class="shot shot--side">

<div class="shot__col">

<div class="shot__frame" v-click>
<img src="/screenshot-counterexamples.png" alt="Список контрпримеров, привязанных к байту">
</div>

<div class="caption">Значение <code>2</code> повторяется в независимых сессиях корпуса и связано с действием «изменить настройку» в журнале</div>

</div>

<div class="shot__side">

<div class="byte-card" v-click>
<div class="byte-mono">02 00 00 03 13 00 55</div>
<div class="byte-note">Команда <code>2</code> вне ожидаемого набора <code>[1]</code></div>
</div>

<div class="panel" v-click>
<div class="lead">Один байт — 80 контрпримеров</div>
<div>80 несоответствий v1 — на offset 0 в сессиях <code>s2</code> и <code>s3</code>.</div>
</div>

</div>

</div>

---
layout: default
---

<div class="metric">

# Что получилось

<div class="metric__sub">140 / 140 на корпусе уточнения. Отдельно проверено на наборе организаторов: 45 + 45, precision 1.00</div>

<div class="bars">
<div class="bars__row" v-click>
<span class="bars__label">v1</span>
<span class="bars__track"><i class="bars__fill bars__fill--bad" style="width: 43%"></i></span>
<span class="bars__value">0.43</span>
</div>
<div class="bars__row" v-click>
<span class="bars__label">v2</span>
<span class="bars__track"><i class="bars__fill bars__fill--good" style="width: 100%"></i></span>
<span class="bars__value">1.00</span>
</div>
</div>

<div class="caption">Было 60 matched из 140 и 80 контрпримеров. Стало 140 matched из 140 и ноль контрпримеров</div>

</div>

---
layout: default
---

<div class="metric">

# 95 МиБ разбираются за 12 секунд

<div class="metric__grid">

<div>
<div class="bignum">12 с</div>
<div class="metric__note" v-click>Пик памяти 350 МиБ — 9% бюджета 4 ГиБ на машине 16 ГиБ</div>
</div>

<div class="metric__figure" v-click>
<img src="/assets/memory_sweep-light.svg" alt="Свип памяти: regular и streaming">
</div>

</div>

<div class="metric-row">
<span v-click><b>12 с</b> общее время</span>
<span><b>350 МиБ</b> пик памяти</span>
<span><b>250k</b> пакетов</span>
</div>

<div class="caption">Условия замера: 95.66 МиБ, 250 000 пакетов, 1000 сессий, 4 vCPU / 16 ГиБ</div>

</div>

---
layout: default
---

<div class="live">

<div class="kicker">Демонстрация</div>

# Живое окно

<div class="live__frame">
<img class="shot--live" src="/screenshot-main.png" alt="Главное окно: сессии, байты, интерпретация, диагностика">
</div>

<div class="caption">Сессии, байты, интерпретация, происхождение и диагностика в одном окне</div>

</div>

---
layout: default
---

# Что мы не утверждаем

<div class="limits">

<div>
<ul>
<li>Смысл байта флагов не установлен: в корпусе он постоянен</li>
<li>Поле значения остаётся гипотезой, а не фактом</li>
</ul>
</div>

<div>
<ul>
<li>Альтернативные чтения берутся из заданного набора</li>
<li>Интерпретация верна для проверенных захватов и молчит вне них</li>
</ul>
</div>

</div>

---
layout: default
---

<div class="closing">

# Инструмент превращает байты в проверяемое знание

<div class="qr-grid">

<div class="qr-item">
<img src="/qr_repo.png" alt="QR: репозиторий">
<div class="caption">Репозиторий</div>
</div>

<div class="qr-item">
<img src="/qr_release.png" alt="QR: релиз v1.0.0">
<div class="caption">Релиз v1.0.0</div>
</div>

<div class="qr-item">
<img src="/qr_telegram_pasha.png" alt="QR: Telegram Павла">
<div class="caption">@Pasha1778</div>
</div>

<div class="qr-item">
<img src="/qr_telegram_nikita.png" alt="QR: Telegram Никиты">
<div class="caption">@petruan</div>
</div>

</div>

<div class="closing__line">github.com/Pavel1778/madrigal-protocol-lab</div>

<img src="/madrigal-logo.png" alt="Мадригал" class="closing__client">

</div>
