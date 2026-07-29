import { Link } from 'react-router-dom'
import { foodImageFor, formatCost, formatRating } from '../api'

export default function RestaurantCard({ restaurant, index = 0, explanation }) {
  const image = foodImageFor(restaurant.id || restaurant.name || restaurant.restaurant_id)
  const id = restaurant.id || restaurant.restaurant_id

  const detailTo = id
    ? `/restaurant/${id}${
        explanation || restaurant.explanation
          ? `?why=${encodeURIComponent(explanation || restaurant.explanation)}`
          : ''
      }`
    : '#'

  return (
    <article className="restaurant-card">
      <Link to={detailTo} className="restaurant-card__link">
        <div className="restaurant-card__media">
          <img src={image} alt={restaurant.name} loading="lazy" />
          {restaurant.rating > 0 && (
            <span className="badge-rating">{formatRating(restaurant.rating)} ★</span>
          )}
          {restaurant.rank && (
            <span className="badge-promo">AI #{restaurant.rank}</span>
          )}
        </div>
        <div className="restaurant-card__body">
          <div className="restaurant-card__top">
            <h3>{restaurant.name}</h3>
            <span className="price">{formatCost(restaurant.estimated_cost)}</span>
          </div>
          <div className="restaurant-card__sub">
            <span>{restaurant.cuisine || 'Multi Cuisine'}</span>
            <span>{restaurant.area || restaurant.location || ''}</span>
          </div>
          {(explanation || restaurant.explanation) && (
            <div className="restaurant-card__foot ai-explain">
              {explanation || restaurant.explanation}
            </div>
          )}
        </div>
      </Link>
    </article>
  )
}
