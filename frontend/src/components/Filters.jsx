export default function Filters({
  selectedCuisine,
  setSelectedCuisine,
  minRating,
  setMinRating,
  budget,
  setBudget,
  extra,
  setExtra,
  cuisines = [],
  onSubmit,
  loading,
}) {
  const ratingChips = [
    { label: 'Any', value: 0 },
    { label: '3.5+', value: 3.5 },
    { label: '4.0+', value: 4 },
    { label: '4.5+', value: 4.5 },
  ]

  return (
    <aside className="filters">
      <h3>Your preferences</h3>
      <p className="filters-hint">These drive the AI recommendation ranking.</p>

      <div className="filter-block">
        <strong>Budget</strong>
        {[
          ['low', 'Low'],
          ['medium', 'Medium'],
          ['high', 'High'],
        ].map(([value, label]) => (
          <label key={value}>
            <input
              type="radio"
              name="budget"
              checked={budget === value}
              onChange={() => setBudget(value)}
            />
            {label}
          </label>
        ))}
      </div>

      <div className="filter-block">
        <strong>Cuisine</strong>
        <label>
          <input
            type="radio"
            name="cuisine"
            checked={!selectedCuisine}
            onChange={() => setSelectedCuisine('')}
          />
          Any
        </label>
        {cuisines.slice(0, 10).map((cuisine) => (
          <label key={cuisine}>
            <input
              type="radio"
              name="cuisine"
              checked={selectedCuisine === cuisine}
              onChange={() => setSelectedCuisine(cuisine)}
            />
            {cuisine}
          </label>
        ))}
      </div>

      <div className="filter-block">
        <strong>Minimum rating</strong>
        <div className="chip-row" style={{ marginTop: '0.6rem' }}>
          {ratingChips.map((chip) => (
            <button
              key={chip.label}
              type="button"
              className={`chip ${minRating === chip.value ? 'active' : ''}`}
              onClick={() => setMinRating(chip.value)}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-block">
        <strong>Extra preferences</strong>
        <textarea
          className="filter-textarea"
          rows={3}
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          placeholder="e.g. family-friendly, romantic, quick service"
        />
      </div>

      <button
        type="button"
        className="btn btn-red"
        style={{ width: '100%', marginTop: '0.5rem' }}
        onClick={onSubmit}
        disabled={loading}
      >
        {loading ? 'Generating…' : 'Get AI recommendations'}
      </button>
    </aside>
  )
}
