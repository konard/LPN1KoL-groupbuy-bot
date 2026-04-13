/**
 * StatCard Component
 * Displays a single statistic with label and value
 */
import React from 'react';

export default function StatCard({ label, value, icon, color = 'primary', subtitle }) {
  return (
    <div className={`admin-stat-card admin-stat-${color}`}>
      {icon && <div className="admin-stat-icon">{icon}</div>}
      <div className="admin-stat-content">
        <div className="admin-stat-value">{value}</div>
        <div className="admin-stat-label">{label}</div>
        {subtitle && <div className="admin-stat-subtitle">{subtitle}</div>}
      </div>
    </div>
  );
}
