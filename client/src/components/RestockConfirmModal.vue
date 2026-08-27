<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">{{ t('restocking.confirmTitle') }}</h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <p class="confirm-intro">{{ t('restocking.confirmBody') }}</p>

            <div class="summary-grid">
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.confirmItems') }}</div>
                <div class="summary-value">{{ items.length }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.confirmUnits') }}</div>
                <div class="summary-value">{{ totalUnits }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.confirmTotal') }}</div>
                <div class="summary-value">{{ formatCurrency(total, currentCurrency) }}</div>
              </div>
              <div class="summary-item">
                <div class="summary-label">{{ t('restocking.destination') }}</div>
                <div class="summary-value">{{ warehouse }}</div>
              </div>
            </div>

            <div class="line-items">
              <div v-for="item in items" :key="item.sku" class="line-item">
                <span class="line-name">{{ item.name }}</span>
                <span class="line-meta">{{ item.quantity }} &times; {{ formatCurrency(item.unit_price, currentCurrency) }}</span>
                <span class="line-total">{{ formatCurrency(item.quantity * item.unit_price, currentCurrency) }}</span>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" @click="close">{{ t('common.cancel') }}</button>
            <button class="btn-primary" :disabled="submitting" @click="$emit('confirm')">
              {{ t('restocking.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const { t, currentCurrency } = useI18n()

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  items: {
    type: Array,
    default: () => []
  },
  total: {
    type: Number,
    default: 0
  },
  warehouse: {
    type: String,
    default: ''
  },
  submitting: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'confirm'])

const totalUnits = computed(() => {
  return props.items.reduce((sum, item) => sum + item.quantity, 0)
})

const close = () => {
  emit('close')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 560px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.confirm-intro {
  color: #64748b;
  font-size: 0.938rem;
  margin-bottom: 1.5rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.875rem 1rem;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.375rem;
}

.summary-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.line-items {
  border-top: 1px solid #e2e8f0;
  padding-top: 1rem;
}

.line-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 1rem;
  align-items: center;
  padding: 0.5rem 0;
  font-size: 0.875rem;
}

.line-item + .line-item {
  border-top: 1px solid #f1f5f9;
}

.line-name {
  color: #0f172a;
  font-weight: 500;
}

.line-meta {
  color: #64748b;
}

.line-total {
  color: #0f172a;
  font-weight: 600;
  text-align: right;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary {
  padding: 0.625rem 1.25rem;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #3b82f6;
  border: 1px solid #3b82f6;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
