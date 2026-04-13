import React, { useMemo } from 'react';
import { useStore } from '../store/useStore';
import { formatCurrency } from '../utils/helpers';
import { batchProcessProcurements } from '../services/wasm';

/**
 * Truncate text to the first N words, appending "…" if truncated.
 */
function firstWords(text, n) {
  if (!text) return '';
  const words = text.trim().split(/\s+/);
  if (words.length <= n) return text;
  return words.slice(0, n).join(' ') + '…';
}

function ProcurementSlider() {
  const { procurements, selectProcurement } = useStore();


  const handleCardClick = (procurement) => {
    selectProcurement(procurement.id);
  };

  if (procurements.length === 0) {
    return (
      <section className="procurement-slider">
        <h2 className="slider-title">Активные закупки</h2>
        <div className="slider-container">
          <div className="p-md text-muted">Нет активных закупок</div>
        </div>
      </section>
    );
  }

  return (
    <section className="procurement-slider">
      <h2 className="slider-title">Активные закупки</h2>
      <div className="slider-container">
        {procurements.map((procurement) => (
          <div
            key={procurement.id}
            className="procurement-card"
            onClick={() => handleCardClick(procurement)}
          >
            {procurement.image_url && (
              <img
                className="procurement-card-image"
                src={procurement.image_url}
                alt={procurement.title}
                loading="lazy"
              />
            )}
            <div className="procurement-title">
              {firstWords(procurement.title, 8)}
            </div>
            <div className="procurement-info">{procurement.city || 'Город не указан'}</div>
            <div className="procurement-progress">
              <div
                className="procurement-progress-bar"
                style={{ width: `${procurement.progress || 0}%` }}
              />
            </div>
            <div className="procurement-stats">
              <span>
                {procurement.formatted_current || formatCurrency(procurement.current_amount)} / {procurement.formatted_target || formatCurrency(procurement.target_amount)}
              </span>
              {procurement.days_left != null && <span>{procurement.days_left} дн.</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default ProcurementSlider;
