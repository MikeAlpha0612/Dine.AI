import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, foodImageFor, formatCost, formatRating } from '../api'
import Header from '../components/Header'
import Footer from '../components/Footer'

export default function RestaurantDetail() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const [restaurant, setRestaurant] = useState(null)
  const [error, setError] = useState('')
  const [cities, setCities] = useState([])
  const explanation = params.get('why') || ''

  useEffect(() => {
    api.cities().then((data) => setCities(data.cities || [])).catch(() => {})
  }, [])

  useEffect(() => {
    setError('')
    api
      .restaurant(id)
      .then(setRestaurant)
      .catch((err) => setError(err.message))
  }, [id])

  if (error) {
    return (
      <>
        <Header cities={cities} location="Bangalore" />
        <div className="container empty-state">{error}</div>
        <Footer />
      </>
    )
  }

  if (!restaurant) {
    return (
      <>
        <Header cities={cities} location="Bangalore" />
        <div className="container loading-state">Loading restaurant…</div>
        <Footer />
      </>
    )
  }

  const images = [
    foodImageFor(restaurant.id),
    foodImageFor(`${restaurant.id}-2`),
    foodImageFor(`${restaurant.id}-3`),
    foodImageFor(`${restaurant.id}-4`),
    foodImageFor(`${restaurant.id}-5`),
  ]

  return (
    <>
      <Header cities={cities} location={restaurant.location} showSearch={false} />

      <div className="container">
        <div className="breadcrumbs">
          <Link to="/">Home</Link> ›{' '}
          <Link to={`/recommend?location=${encodeURIComponent(restaurant.location)}`}>
            AI Recommendations
          </Link>{' '}
          › {restaurant.name}
        </div>

        <div className="gallery">
          <div className="gallery__main">
            <img src={images[0]} alt={restaurant.name} />
          </div>
          <div className="gallery__side">
            {images.slice(1).map((src) => (
              <div key={src}>
                <img src={src} alt="" />
              </div>
            ))}
          </div>
        </div>

        <div className="detail-head">
          <div>
            <h1>{restaurant.name}</h1>
            <p className="meta">{restaurant.cuisine}</p>
            <p className="meta">
              {restaurant.area}, {restaurant.location}
            </p>
            <p className="meta">{formatCost(restaurant.estimated_cost)}</p>
          </div>
          <div className="rating-boxes">
            <div className="rating-box">
              <div className="rating-box__score">{formatRating(restaurant.rating)}★</div>
              <span>
                {(restaurant.votes || 0).toLocaleString()} votes in dataset
              </span>
            </div>
          </div>
        </div>

        <div className="action-row">
          <Link
            className="btn btn-red"
            to={`/recommend?location=${encodeURIComponent(restaurant.location)}`}
          >
            Back to AI recommendations
          </Link>
        </div>

        <section className="explain-box" style={{ margin: '1.5rem 0 3rem' }}>
          <h2 style={{ marginTop: 0 }}>Why this place</h2>
          <p style={{ margin: 0, color: '#696969', lineHeight: 1.6 }}>
            {explanation ||
              `Highly rated ${restaurant.cuisine} option in ${restaurant.location}` +
                (restaurant.area ? ` (${restaurant.area})` : '') +
                `. Approximate cost ${formatCost(restaurant.estimated_cost)}.`}
          </p>
          {restaurant.address && (
            <p style={{ margin: '1rem 0 0', color: '#696969' }}>
              Address: {restaurant.address}
            </p>
          )}
        </section>
      </div>

      <Footer />
    </>
  )
}
