<script setup lang="ts">
import { computed } from 'vue'
import { useSlideContext } from '@slidev/client'

const { $slidev } = useSlideContext()
const page = computed(() => $slidev.nav.currentPage)
const total = computed(() => $slidev.nav.total)
const isCover = computed(() => page.value === 1)
const isClosing = computed(() => page.value === total.value)

// Секция меняется вместе с разделителем, чтобы зритель всегда знал, где мы.
const SECTIONS: Array<[number, string]> = [
  [1, 'Постановка и метод'],
  [10, 'Результаты'],
  [12, 'Демонстрация'],
  [13, 'Границы и итог'],
]
const section = computed(() => {
  let name = SECTIONS[0][1]
  for (const [start, label] of SECTIONS) {
    if (page.value >= start) name = label
  }
  return name
})
</script>

<template>
  <footer v-if="!isCover && !isClosing" class="deck-footer">
    <span>Команда HTTP 418 · кейс #02 · Мадригал</span>
    <span class="deck-footer__section">{{ section }}</span>
    <span class="deck-footer__page">{{ page }} / {{ total }}</span>
  </footer>
</template>
