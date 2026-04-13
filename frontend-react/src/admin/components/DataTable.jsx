/**
 * DataTable Component
 * Reusable table component for admin panel
 */
import React from 'react';

export default function DataTable({
  columns,
  data,
  loading,
  onRowClick,
  selectedIds = [],
  onSelect,
  pagination,
  onPageChange,
  emptyMessage = 'Нет данных',
}) {
  const handleSelectAll = (e) => {
    if (onSelect) {
      if (e.target.checked) {
        onSelect(data.map((item) => item.id));
      } else {
        onSelect([]);
      }
    }
  };

  const handleSelectOne = (id) => {
    if (onSelect) {
      if (selectedIds.includes(id)) {
        onSelect(selectedIds.filter((i) => i !== id));
      } else {
        onSelect([...selectedIds, id]);
      }
    }
  };

  const allSelected = data.length > 0 && data.every((item) => selectedIds.includes(item.id));

  return (
    <div className="admin-table-wrapper">
      {loading ? (
        <div className="admin-loading">Загрузка...</div>
      ) : data.length === 0 ? (
        <div className="admin-empty">{emptyMessage}</div>
      ) : (
        <>
          <table className="admin-table">
            <thead>
              <tr>
                {onSelect && (
                  <th className="admin-table-checkbox">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={handleSelectAll}
                    />
                  </th>
                )}
                {columns.map((col) => (
                  <th key={col.key} style={col.width ? { width: col.width } : {}}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => onRowClick && onRowClick(item)}
                  className={onRowClick ? 'clickable' : ''}
                >
                  {onSelect && (
                    <td
                      className="admin-table-checkbox"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.id)}
                        onChange={() => handleSelectOne(item.id)}
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td key={col.key}>
                      {col.render ? col.render(item[col.key], item) : item[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          {pagination && pagination.count > 0 && (
            <div className="admin-pagination">
              <span className="admin-pagination-info">
                Всего: {pagination.count}
              </span>
              <div className="admin-pagination-buttons">
                <button
                  disabled={!pagination.previous}
                  onClick={() => onPageChange && onPageChange('prev')}
                >
                  Назад
                </button>
                <button
                  disabled={!pagination.next}
                  onClick={() => onPageChange && onPageChange('next')}
                >
                  Вперед
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
