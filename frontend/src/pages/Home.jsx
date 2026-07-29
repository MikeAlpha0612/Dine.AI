import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Header from '../components/Header'
import Footer from '../components/Footer'

export default function Home() {
  const navigate = useNavigate()
  const [cities, setCities] = useState([])
  const [location, setLocation] = useState('Bangalore')
  const [cuisine, setCuisine] = useState('')
  const [budget, setBudget] = useState('medium')
  const [minRating, setMinRating] = useState(0)
  const [extra, setExtra] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .cities()
      .then((data) => {
        const list = data.cities || []
        setCities(list)
        const preferred = ['Bangalore', 'New Delhi', 'Mumbai', 'Hyderabad', 'Chennai']
        setLocation(preferred.find((c) => list.includes(c)) || list[0] || 'Bangalore')
      })
      .catch((err) => setError(err.message))
  }, [])

  const orderedCities = useMemo(() => {
    const preferred = ['Bangalore', 'New Delhi', 'Mumbai', 'Hyderabad', 'Chennai', 'Pune']
    return [
      ...preferred.filter((city) => cities.includes(city)),
      ...cities.filter((city) => !preferred.includes(city)),
    ]
  }, [cities])

  const goRecommend = (event) => {
    event?.preventDefault()
    const params = new URLSearchParams({
      location,
      budget,
      ...(cuisine ? { cuisine } : {}),
      ...(minRating ? { min_rating: String(minRating) } : {}),
      ...(extra ? { extra } : {}),
    })
    navigate(`/recommend?${params.toString()}`)
  }

  return (
    <>
      <Header
        cities={orderedCities}
        location={location}
        onLocationChange={setLocation}
        onSearch={(q, loc) => {
          const params = new URLSearchParams({
            location: loc || location,
            budget,
            ...(q ? { cuisine: q } : {}),
          })
          navigate(`/recommend?${params.toString()}`)
        }}
      />

      <section className="hero">
        <div className="hero__content">
          <div className="logo logo--white" style={{ fontSize: '2.4rem' }}>
            Dine.AI
          </div>
          <h1>AI restaurant recommendations in {location}</h1>
          <p className="hero-sub">
            Tell us your city, budget, and taste — we rank real restaurants and explain why they fit.
          </p>

          <form className="hero-prefs" onSubmit={goRecommend}>
            <div className="hero-prefs__row">
              <label>
                <span>Location</span>
                <select value={location} onChange={(e) => setLocation(e.target.value)}>
                  {orderedCities.map((city) => (
                    <option key={city} value={city}>
                      {city}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Budget</span>
                <select value={budget} onChange={(e) => setBudget(e.target.value)}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label>
                <span>Cuisine</span>
                <input
                  value={cuisine}
                  onChange={(e) => setCuisine(e.target.value)}
                  placeholder="Italian, Chinese…"
                />
              </label>
            </div>
            <div className="hero-prefs__row">
              <label>
                <span>Min rating</span>
                <select
                  value={minRating}
                  onChange={(e) => setMinRating(Number(e.target.value))}
                >
                  <option value={0}>Any</option>
                  <option value={3.5}>3.5+</option>
                  <option value={4}>4.0+</option>
                  <option value={4.5}>4.5+</option>
                </select>
              </label>
              <label className="grow">
                <span>Extra preferences</span>
                <input
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder="family-friendly, romantic, quick bites…"
                />
              </label>
              <button type="submit" className="btn btn-red hero-cta">
                Get AI recommendations
              </button>
            </div>
          </form>
          {error && <p style={{ marginTop: '1rem' }}>{error}</p>}
        </div>
      </section>

      <div className="container">
        <section className="section">
          <div className="section__head">
            <div>
              <h2>How it works</h2>
              <p>Same look as a restaurant discovery site — powered by your AI recommendation engine.</p>
            </div>
          </div>
          <div className="category-row">
            <div className="category-card">
              <img
                src="https://images.unsplash.com/photo-1526367790994-0e5c0f0b0a0f?auto=format&fit=crop&w=800&q=80"
                alt="Preferences"
                onError={(e) => {
                  e.currentTarget.src =
                    'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=800&q=80'
                }}
              />
              <div className="category-card__body">
                <h3>1. Share preferences</h3>
                <p>Location, budget, cuisine, rating, and extras</p>
              </div>
            </div>
            <div className="category-card">
              <img
                src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80"
                alt="AI ranking"
              />
              <div className="category-card__body">
                <h3>2. AI ranks matches</h3>
                <p>We filter real restaurant data, then rank with an LLM</p>
              </div>
            </div>
            <div className="category-card">
              <img
                src="https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=80"
                alt="Results"
              />
              <div className="category-card__body">
                <h3>3. Get clear reasons</h3>
                <p>See why each place fits — not just a generic list</p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <Footer />
    </>
  )
}
