<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successOrder" class="success-banner">
        <div class="success-title">{{ t('restocking.successTitle') }}</div>
        <div class="success-body">
          {{ t('restocking.successBody', { orderNumber: successOrder.orderNumber, date: successOrder.date }) }}
          <router-link to="/orders" class="success-link">{{ t('restocking.viewInOrders') }}</router-link>
        </div>
      </div>

      <div class="card budget-card">
        <div class="budget-header">
          <div class="budget-label">{{ t('restocking.budget') }}</div>
          <div class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        </div>
        <input
          type="range"
          class="budget-slider"
          :min="0"
          :max="maxBudget"
          :step="budgetStep"
          v-model.number="budget"
        />
        <div class="budget-range-labels">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ formatCurrency(maxBudget, currentCurrency) }}</span>
        </div>
        <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.budgetUsed') }}</div>
          <div class="stat-value">{{ formatCurrency(budgetUsedTotal, currentCurrency) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.budgetRemaining') }}</div>
          <div class="stat-value">{{ formatCurrency(budgetRemaining, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ selectedItems.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.totalUnits') }}</div>
          <div class="stat-value">{{ totalUnits }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommended') }}</h3>
          <span class="recommended-count">
            {{ t('restocking.recommendedCount', { count: recommendations.length, total: candidates.length }) }}
          </span>
        </div>

        <div v-if="candidates.length === 0" class="empty-state">
          {{ t('restocking.noShortfall') }}
        </div>
        <div v-else-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <template v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th class="col-check"></th>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.itemName') }}</th>
                  <th>{{ t('restocking.table.category') }}</th>
                  <th>{{ t('restocking.table.shortfall') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineTotal') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recommendations" :key="item.sku">
                  <td class="col-check">
                    <input
                      type="checkbox"
                      :checked="isSelected(item.sku)"
                      @change="toggleSelection(item.sku)"
                    />
                  </td>
                  <td><strong>{{ item.sku }}</strong></td>
                  <td>{{ translateProductName(item.name) }}</td>
                  <td>{{ categoryLabel(item.category) }}</td>
                  <td>{{ item.shortfall }}</td>
                  <td>{{ formatCurrency(item.unit_cost, currentCurrency) }}</td>
                  <td><strong>{{ formatCurrency(item.lineTotal, currentCurrency) }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="submitError" class="error">{{ submitError }}</div>

          <div class="order-footer">
            <div class="destination">
              {{ t('restocking.destination') }}: <strong>{{ translatedWarehouse }}</strong>
            </div>
            <div class="place-order-area">
              <button
                class="btn-primary"
                :disabled="selectedItems.length === 0"
                @click="openConfirm"
              >
                {{ t('restocking.placeOrder') }}
              </button>
              <p v-if="selectedItems.length === 0" class="hint">{{ t('restocking.nothingSelected') }}</p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <RestockConfirmModal
      :is-open="showConfirm"
      :items="confirmItems"
      :total="budgetUsedTotal"
      :warehouse="translatedWarehouse"
      :submitting="submitting"
      @close="showConfirm = false"
      @confirm="confirmOrder"
    />
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'
import RestockConfirmModal from '../components/RestockConfirmModal.vue'

const BUDGET_STEP = 250
const CATEGORY_KEY_MAP = {
  'Circuit Boards': 'circuitBoards',
  'Sensors': 'sensors',
  'Actuators': 'actuators',
  'Controllers': 'controllers',
  'Power Supplies': 'powerSupplies'
}

export default {
  name: 'Restocking',
  components: { RestockConfirmModal },
  setup() {
    const { t, currentCurrency, translateProductName, translateWarehouse } = useI18n()
    const { selectedLocation, selectedCategory } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])

    const budget = ref(0)
    const budgetInitialized = ref(false)
    const deselected = ref(new Set())

    const showConfirm = ref(false)
    const submitting = ref(false)
    const submitError = ref(null)
    const successOrder = ref(null)

    const candidates = computed(() => {
      let items = forecasts.value
        .filter(f => (f.forecasted_demand - f.current_demand) > 0)
        .map(f => {
          const shortfall = f.forecasted_demand - f.current_demand
          return {
            sku: f.item_sku,
            name: f.item_name,
            category: f.category,
            unit_cost: f.unit_cost,
            shortfall,
            lineTotal: shortfall * f.unit_cost
          }
        })

      if (selectedCategory.value !== 'all') {
        items = items.filter(i => i.category.toLowerCase() === selectedCategory.value.toLowerCase())
      }

      return items.sort((a, b) => {
        if (b.shortfall !== a.shortfall) return b.shortfall - a.shortfall
        return b.lineTotal - a.lineTotal
      })
    })

    const maxBudget = computed(() => {
      const total = candidates.value.reduce((sum, c) => sum + c.lineTotal, 0)
      if (total <= 0) return 1000
      return Math.ceil(total / 1000) * 1000
    })

    const recommendations = computed(() => {
      const list = []
      let running = 0
      for (const item of candidates.value) {
        if (running + item.lineTotal <= budget.value) {
          list.push(item)
          running += item.lineTotal
        }
      }
      return list
    })

    const isSelected = (sku) => !deselected.value.has(sku)

    const toggleSelection = (sku) => {
      if (deselected.value.has(sku)) {
        deselected.value.delete(sku)
      } else {
        deselected.value.add(sku)
      }
    }

    const selectedItems = computed(() => recommendations.value.filter(i => isSelected(i.sku)))

    const budgetUsedTotal = computed(() => selectedItems.value.reduce((sum, i) => sum + i.lineTotal, 0))
    const budgetRemaining = computed(() => budget.value - budgetUsedTotal.value)
    const totalUnits = computed(() => selectedItems.value.reduce((sum, i) => sum + i.shortfall, 0))

    const destinationWarehouse = computed(() => {
      return selectedLocation.value !== 'all' ? selectedLocation.value : 'San Francisco'
    })
    const translatedWarehouse = computed(() => translateWarehouse(destinationWarehouse.value))

    const confirmItems = computed(() => selectedItems.value.map(i => ({
      sku: i.sku,
      name: translateProductName(i.name),
      quantity: i.shortfall,
      unit_price: i.unit_cost
    })))

    const categoryLabel = (category) => {
      const key = CATEGORY_KEY_MAP[category]
      return key ? t(`categories.${key}`) : category
    }

    const formatDate = (dateString) => {
      const { currentLocale } = useI18n()
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    const loadForecasts = async () => {
      loading.value = true
      error.value = null
      try {
        forecasts.value = await api.getDemandForecasts()
        if (!budgetInitialized.value) {
          const half = Math.floor((maxBudget.value / 2) / BUDGET_STEP) * BUDGET_STEP
          budget.value = half
          budgetInitialized.value = true
        }
      } catch (err) {
        error.value = 'Failed to load demand forecasts: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Prune stale deselections when an item drops out of the recommendation list
    watch(recommendations, (newRecs) => {
      const skus = new Set(newRecs.map(i => i.sku))
      Array.from(deselected.value).forEach(sku => {
        if (!skus.has(sku)) deselected.value.delete(sku)
      })
    })

    // Keep budget within the current max
    watch(maxBudget, (newMax) => {
      if (budget.value > newMax) budget.value = newMax
    })

    watch([selectedLocation, selectedCategory], () => {
      successOrder.value = null
      submitError.value = null
    })

    const openConfirm = () => {
      if (selectedItems.value.length === 0) return
      submitError.value = null
      showConfirm.value = true
    }

    const confirmOrder = async () => {
      if (submitting.value) return
      submitting.value = true
      submitError.value = null
      try {
        const order = await api.createRestockingOrder({
          items: selectedItems.value.map(i => ({
            sku: i.sku,
            name: i.name,
            quantity: i.shortfall,
            unit_price: i.unit_cost
          })),
          budget: budget.value,
          warehouse: destinationWarehouse.value
        })
        showConfirm.value = false
        deselected.value = new Set()
        successOrder.value = {
          orderNumber: order.order_number,
          date: formatDate(order.expected_delivery)
        }
      } catch (err) {
        const detail = err.response?.data?.detail
        submitError.value = detail ? `${t('restocking.submitFailed')}: ${detail}` : t('restocking.submitFailed')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadForecasts)

    return {
      t,
      currentCurrency,
      translateProductName,
      formatCurrency,
      loading,
      error,
      budget,
      budgetStep: BUDGET_STEP,
      maxBudget,
      candidates,
      recommendations,
      selectedItems,
      isSelected,
      toggleSelection,
      budgetUsedTotal,
      budgetRemaining,
      totalUnits,
      translatedWarehouse,
      confirmItems,
      categoryLabel,
      showConfirm,
      submitting,
      submitError,
      successOrder,
      openConfirm,
      confirmOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
}

.budget-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
  margin: 0.5rem 0;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.3), 0 0 0 1px #3b82f6;
  cursor: pointer;
  transition: box-shadow 0.15s ease;
}

.budget-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1), 0 0 0 1px #3b82f6;
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
}

.budget-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #3b82f6;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.3), 0 0 0 1px #3b82f6;
  cursor: pointer;
}

.budget-range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 0.75rem;
}

.budget-hint {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

.card-header {
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.recommended-count {
  font-size: 0.875rem;
  color: #64748b;
}

.col-check {
  width: 40px;
}

.empty-state {
  text-align: center;
  padding: 2.5rem 1rem;
  color: #94a3b8;
  font-size: 0.938rem;
}

.order-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid #e2e8f0;
}

.destination {
  color: #334155;
  font-size: 0.938rem;
}

.place-order-area {
  text-align: right;
}

.btn-primary {
  padding: 0.625rem 1.5rem;
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

.hint {
  font-size: 0.813rem;
  color: #94a3b8;
  margin: 0.375rem 0 0 0;
}

.success-banner {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #15803d;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
}

.success-title {
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.success-body {
  font-size: 0.938rem;
}

.success-link {
  color: #15803d;
  font-weight: 600;
  text-decoration: underline;
  margin-left: 0.5rem;
}

.success-link:hover {
  color: #166534;
}
</style>
