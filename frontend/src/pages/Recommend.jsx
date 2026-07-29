import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Header from '../components/Header'
import Footer from '../components/Footer'
import Filters from '../components/Filters'
import RestaurantCard from '../components/RestaurantCard'

export default function Recommend() {
  const [params, setParams] = useSearchParams()
  const location = params.get('location') || 'Bangalore'
  const initialCuisine = params.get('cuisine') || params.get('q') || ''
  const initialBudget = params.get('budget') || 'medium'
  const initialRating = Number(params.get('min_rating') || 0)
  const initialExtra = params.get('extra') || ''

  const [cities, setCities] = useState([])
  const [cuisines, setCuisines] = useState([])
  const [selectedCuisine, setSelectedCuisine] = useState(initialCuisine)
  const [minRating, setMinRating] = useState(initialRating)
  const [budget, setBudget] = useState(initialBudget)
  const [extra, setExtra] = useState(initialExtra)

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [requestKey, setRequestKey] = useState(0)

  useEffect(() => {
    api.cities().then((data) => setCities(data.cities || [])).catch(() => {})
  }, [])

  useEffect(() => {
    api
      .cuisines(location)
      .then((data) => setCuisines(data.cuisines || []))
      .catch(() => setCuisines([]))
  }, [location])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

    api
      .recommend({
        location,
        budget,
        cuisine: selectedCuisine || undefined,
        min_rating: minRating,
        extra_preferences: extra || undefined,
      })
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message)
          setResult(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [location, budget, selectedCuisine, minRating, extra, requestKey])

  const orderedCities = useMemo(() => {
    const preferred = ['Bangalore', 'New Delhi', 'Mumbai', 'Hyderabad', 'Chennai', 'Pune']
    return [
      ...preferred.filter((city) => cities.includes(city)),
      ...cities.filter((city) => !preferred.includes(city)),
    ]
  }, [cities])

  const syncParams = () => {
    const next = new URLSearchParams({
      location,
      budget,
      ...(selectedCuisine ? { cuisine: selectedCuisine } : {}),
      ...(minRating ? { min_rating: String(minRating) } : {}),
      ...(extra ? { extra } : {}),
    })
    setParams(next)
    setRequestKey((k) => k + 1)
  }

  const titleBits = [
    selectedCuisine || null,
    budget ? `${budget} budget` : null,
  ].filter(Boolean)

  return (
    <>
      <Header
        cities={orderedCities}
        location={location}
        query={selectedCuisine}
        onLocationChange={(next) => {
          const p = new URLSearchParams(params)
          p.set('location', next)
          setParams(p)
        }}
        onSearch={(q, loc) => {
          const p = new URLSearchParams(params)
          p.set('location', loc || location)
          if (q) p.set('cuisine', q)
          else p.delete('cuisine')
          setParams(p)
          setSelectedCuisine(q || '')
        }}
      />

      <div className="container">
        <div className="breadcrumbs">
          Home › AI Recommendations › {location}
        </div>
        <h1 className="page-title">
          AI picks{titleBits.length ? ` for ${titleBits.join(' · ')}` : ''} in {location}
        </h1>

        <div className="search-layout">
          <Filters
            cuisines={cuisines}
            selectedCuisine={selectedCuisine}
            setSelectedCuisine={setSelectedCuisine}
            minRating={minRating}
            setMinRating={setMinRating}
            budget={budget}
            setBudget={setBudget}
            extra={extra}
            setExtra={setExtra}
            onSubmit={syncParams}
            loading={loading}
          />

          <div>
            {loading && (
              <div className="loading-state">Generating AI recommendations…</div>
            )}
            {error && <div className="empty-state">{error}</div>}

            {!loading && result && (
              <>
                {result.summary && (
                  <div className="ai-banner">
                    <strong>AI summary:</strong> {result.summary}
                    {result.used_fallback
                      ? ' (fallback ranking — AI unavailable)'
                      : ''}
                  </div>
                )}
                {result.message && (
                  <p style={{ color: '#696969', marginTop: 0 }}>{result.message}</p>
                )}
                {!result.recommendations?.length && (
                  <div className="empty-state">
                    No matches for these preferences. Try another city, cuisine, or budget.
                  </div>
                )}
                <div className="restaurant-grid">
                  {result.recommendations?.map((rec, index) => (
                    <RestaurantCard
                      key={`${rec.name}-${rec.rank}`}
                      restaurant={{
                        ...rec,
                        id: rec.restaurant_id,
                      }}
                      index={index}
                      explanation={rec.explanation}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <Footer />
    </>
  )
}
