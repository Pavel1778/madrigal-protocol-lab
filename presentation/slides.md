---
theme: none
title: Лаборатория протоколов
info: |
  Восстановление недокументированного бинарного протокола поверх TCP.
  UMIRHack 2026, кейс #02, Мадригал.
class: text-left
highlighter: shiki
lineNumbers: false
drawings:
  persist: false
transition: fade
colorSchema: dark
mdc: true
fonts:
  sans: Inter
  mono: JetBrains Mono
---

<div class="title-slide">

<img src="/team-avatar.png" alt="Команда HTTP 418" class="title-avatar">

<div class="title-text">

# Лаборатория протоколов

<div class="title-line">Команда HTTP 418 · UMIRHack 2026 · кейс #02 · Мадригал</div>

</div>

</div>

---

<div class="cols">

<div>

# Нас двое

- **Сабадаш Павел** — архитектура, захват, интерфейс · @Pasha1778
- **Предков Никита** — правила, тесты · @petruan

</div>

<div class="center">

<img src="/team-avatar.png" alt="Команда HTTP 418" class="avatar-lg">

</div>

</div>

---

<div class="statement">

# TCP разрезает сообщения посередине

<div class="statement-sub">Границы пакета и границы сообщения — разные вещи</div>

</div>

---

# Дано и требуется

<div class="cols">

<div>

<div class="lead">Дано</div>

- Захваты pcap/pcapng и журнал действий устройства
- Спецификации протокола нет

</div>

<div>

<div class="lead">Требуется</div>

- Проверяемая интерпретация структуры сообщений
- Видно, где чтение верно, а где перестаёт работать

</div>

</div>

---

<div class="moment">

# Первые дни мы не понимали, где у протокола длина

<div class="moment-sub">Смещение поля длины оказалось на четыре байта позже, чем мы считали</div>

</div>

---

# Три модуля связаны форматами, а не вызовами

<img src="/assets/architecture.svg" alt="Поток данных: захват, протокол, интерфейс" class="diagram">

---

# Каждый байт знает свой пакет

<div class="figure"><img src="/screenshots/09_provenance.png" alt="Происхождение байта: пакет, номер последовательности, время"></div>

<div class="caption">Клик по байту: `packet 3 · seq 1001 · ts 1700000000.004`</div>

---

# Правило проверяется на всём корпусе сразу

<div class="cols">

<div>

<div class="figure"><img src="/screenshots/07_rule_editor.png" alt="Редактор правила"></div>

</div>

<div>

<div class="figure"><img src="/screenshots/05_validation.png" alt="Результат применения правила"></div>

</div>

</div>

<div class="caption">Одно правило описывает весь поток; сообщения не перечисляют вручную</div>

---

# Контрпример важнее метрики

<div class="cols">

<div>

<div class="figure"><img src="/screenshots/05_validation.png" alt="Контрпример, привязанный к байту"></div>

</div>

<div>

<div class="byte-card">

<div class="byte-mono">02 00 00 03 13 00 55</div>

<div class="byte-note">Команда `2` не входила в ожидаемый набор `[1]`</div>

</div>

</div>

</div>

<div class="caption">Один такой байт превратил 80 контрпримеров в ноль</div>

---

<div class="divider">

<div class="index">01</div>

# Что получилось

<div class="bar"></div>

</div>

---

<div class="metric">

# Точность правила: 0.43 → 1.00

<div class="bignum">1.00</div>

<div class="metric-note">Было 60 matched и 80 mismatched. Стало 140 matched и ноль контрпримеров</div>

</div>

---

<div class="metric">

# Набор организаторов разобран целиком

<div class="bignum">90</div>

<div class="metric-note">45 запросов и 45 ответов, все matched, покрытие байтов 100 %</div>

</div>

---

<div class="metric">

# 95 МиБ разбираются за 12 секунд

<div class="bignum">12 с</div>

<div class="metric-note">250 000 пакетов, 1000 сессий, 4 vCPU. Пик памяти 350 МиБ</div>

</div>

---

<div class="divider">

<div class="index">02</div>

# Демонстрация

<div class="bar"></div>

</div>

---

<div class="fullshot">

# Живое окно

<img src="/screenshots/01_main.png" alt="Главное окно: сессии, байты, интерпретация, диагностика">

<div class="caption">Сессии, байты, интерпретация, происхождение и диагностика в одном окне</div>

</div>

---

<div class="fullshot">

# Запись прогона на случай, если экран не поднимется

<video src="/screencast.mp4" controls muted loop playsinline class="cast"></video>

<div class="caption">Четыре минуты: шесть сцен референсного исследования</div>

</div>

---

<div class="divider">

<div class="index">03</div>

# Границы и итог

<div class="bar"></div>

</div>

---

# Что мы не утверждаем

<div class="cols">

<div>

- Смысл байта флагов не установлен: в корпусе он постоянен
- Поле значения остаётся гипотезой, а не фактом

</div>

<div>

- Альтернативные чтения берутся из заданного набора
- Интерпретация верна для проверенных захватов и молчит вне них

</div>

</div>

---

<div class="closing">

# Инструмент превращает байты в проверяемое знание

<div class="qr-row">

<div class="qr-item">
<img src="/qr_repo.png" alt="QR: репозиторий">
<div class="caption">Репозиторий</div>
</div>

<div class="qr-item">
<img src="/qr_release.png" alt="QR: релиз v1.0.0">
<div class="caption">Релиз v1.0.0</div>
</div>

</div>

<div class="closing-line">github.com/Pavel1778/madrigal-protocol-lab · @Pasha1778</div>

</div>
