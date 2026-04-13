/**
 * SearchFilters Component
 * Reusable search and filter controls for admin tables
 */
import React, { useState, useEffect } from 'react';

export default function SearchFilters({ filters, values, onChange, onSearch }) {
  const [searchText, setSearchText] = useState(values.search || '');

  useEffect(() => {
    setSearchText(values.search || '');
  }, [values.search]);

  const handleSearch = (e) => {
    e.preventDefault();
    onSearch(searchText);
  };

  return (
    <div className="admin-filters">
      <form className="admin-search-form" onSubmit={handleSearch}>
        <input
          type="text"
          placeholder="Поиск..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="admin-search-input"
        />
        <button type="submit" className="admin-search-btn">
          Найти
        </button>
      </form>

      <div className="admin-filter-controls">
        {filters.map((filter) => (
          <div key={filter.key} className="admin-filter-item">
            <label>{filter.label}:</label>
            <select
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
            >
              <option value="">Все</option>
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}
