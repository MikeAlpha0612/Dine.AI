const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  cities: () => request('/cities'),
  localities: (location) =>
    request(`/localities?location=${encodeURIComponent(location)}`),
  cuisines: (location) =>
    request(`/cuisines${location ? `?location=${encodeURIComponent(location)}` : ''}`),
  restaurants: (params) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        qs.set(key, String(value))
      }
    })
    return request(`/restaurants?${qs.toString()}`)
  },
  restaurant: (id) => request(`/restaurants/${encodeURIComponent(id)}`),
  recommend: (body) =>
    request('/recommend', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

const FOOD_IMAGES = [
  'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1565958011703-44f9829ba187?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1476224203421-9ac39bcb3327?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80',
  'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=800&q=80',
]

export function foodImageFor(idOrName = '') {
  let hash = 0
  const key = String(idOrName)
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash + key.charCodeAt(i) * (i + 1)) % FOOD_IMAGES.length
  }
  return FOOD_IMAGES[hash]
}

export function formatCost(value) {
  if (!value || value === 'unknown') return 'Cost N/A'
  const text = String(value)
  if (text.startsWith('₹')) return text.includes('for') ? text : `${text} for two`
  return `₹${text} for two`
}

export function formatRating(rating) {
  if (!rating || rating <= 0) return 'New'
  return Number(rating).toFixed(1)
}
