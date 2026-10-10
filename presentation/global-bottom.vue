<script setup lang="ts">
import { computed } from 'vue'
import { useSlideContext } from '@slidev/client'

const { $slidev } = useSlideContext()
const page = computed(() => $slidev.nav.currentPage)
const total = computed(() => $slidev.nav.total)
const isCover = computed(() => page.value === 1)
const isClosing = computed(() => page.value === total.value)
</script>

<template>
  <footer v-if="!isCover && !isClosing" class="deck-footer">
    <span>Команда HTTP 418 · UMIRHack 2026 · {{ page }} / {{ total }}</span>
  </footer>
</template>
