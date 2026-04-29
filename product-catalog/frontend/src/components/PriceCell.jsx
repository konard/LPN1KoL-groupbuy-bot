import { useState, useRef } from 'react'
import { convertToUsd } from '../api'

const styles = {
  wrapper: { position: 'relative', display: 'inline-flex', alignItems: 'center', gap: '4px' },
  star: {
    cursor: 'pointer',
    color: '#f59e0b',
    fontWeight: 'bold',
    fontSize: '14px',
    userSelect: 'none',
  },
  tooltip: {
    position: 'absolute',
    bottom: '130%',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#1e293b',
    color: '#fff',
    padding: '8px 12px',
    borderRadius: '8px',
    fontSize: '13px',
    whiteSpace: 'nowrap',
    zIndex: 100,
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
    minWidth: '160px',
    textAlign: 'center',
  },
  arrow: {
    position: 'absolute',
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    border: '6px solid transparent',
    borderTopColor: '#1e293b',
  },
}

export default function PriceCell({ price }) {
  const [tooltip, setTooltip] = useState(null)
  const [loading, setLoading] = useState(false)
  const timeoutRef = useRef(null)

  async function handleMouseEnter() {
    if (loading) return
    setLoading(true)
    try {
      const { data } = await convertToUsd(price)
      setTooltip(`$${data.price_usd.toFixed(2)} (курс ${data.rate} BYN/USD)`)
    } catch {
      setTooltip('Ошибка получения курса')
    } finally {
      setLoading(false)
    }
  }

  function handleMouseLeave() {
    timeoutRef.current = setTimeout(() => setTooltip(null), 300)
  }

  return (
    <span style={styles.wrapper}>
      <span>{price.toFixed(3)}</span>
      <span
        style={styles.star}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        title="Наведите для курса USD"
      >
        *
      </span>
      {(tooltip || loading) && (
        <span style={styles.tooltip}>
          {loading ? 'Загрузка...' : tooltip}
          <span style={styles.arrow} />
        </span>
      )}
    </span>
  )
}
