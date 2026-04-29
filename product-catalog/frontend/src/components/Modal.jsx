const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  box: {
    background: '#fff', borderRadius: '12px', padding: '28px',
    minWidth: '340px', maxWidth: '560px', width: '100%',
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '90vh', overflowY: 'auto',
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  title: { fontSize: '18px', fontWeight: '700', color: '#1e293b' },
  close: {
    background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer',
    color: '#64748b', lineHeight: 1, padding: '0 4px',
  },
}

export default function Modal({ title, onClose, children }) {
  return (
    <div style={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={styles.box}>
        <div style={styles.header}>
          <span style={styles.title}>{title}</span>
          <button style={styles.close} onClick={onClose}>×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
