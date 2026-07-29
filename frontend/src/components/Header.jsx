import { Link, useNavigate } from 'react-router-dom'

export default function Header({
  cities = [],
  location = 'Bangalore',
  query = '',
  onLocationChange,
  onSearch,
  showSearch = true,
}) {
  const navigate = useNavigate()

  const submitSearch = (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const nextQuery = String(form.get('q') || '').trim()
    const nextLocation = String(form.get('location') || location)
    if (onSearch) {
      onSearch(nextQuery, nextLocation)
      return
    }
    const params = new URLSearchParams({
      location: nextLocation,
      ...(nextQuery ? { q: nextQuery } : {}),
    })
    navigate(`/recommend?${params.toString()}`)
  }

  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <Link to="/" className="logo">
          Dine.AI
        </Link>

        {showSearch && (
          <form className="header-search" onSubmit={submitSearch}>
            <div className="header-search__loc">
              <span className="pin">📍</span>
              <select
                name="location"
                value={location}
                onChange={(e) => onLocationChange?.(e.target.value)}
                aria-label="Location"
              >
                {(cities.length ? cities : [location]).map((city) => (
                  <option key={city} value={city}>
                    {city}
                  </option>
                ))}
              </select>
            </div>
            <div className="header-search__query">
              <span>✨</span>
              <input
                name="q"
                defaultValue={query}
                key={`${location}-${query}`}
                placeholder="Cuisine or preference (e.g. Italian, family-friendly)"
              />
            </div>
          </form>
        )}

        <div className="header-actions">
          <Link to="/" className="link-muted">
            Home
          </Link>
          <Link to="/recommend" className="btn btn-red">
            AI Recommend
          </Link>
        </div>
      </div>
    </header>
  )
}
