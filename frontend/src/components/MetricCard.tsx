import React from 'react';
import { FormulaDisplay } from './FormulaDisplay';
import type { Formula } from '../api/types';

interface MetricDetail {
  label: string;
  value: string | number;
}

interface MetricCardProps {
  title: string;
  icon: React.ReactNode;
  value: string | number;
  unit?: string;
  details?: MetricDetail[];
  statusBadge?: {
    text: string;
    type: 'success' | 'danger';
  };
  formula?: Formula;
  actionButton?: React.ReactNode;
  footerNode?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  icon,
  value,
  unit,
  details,
  statusBadge,
  formula,
  actionButton,
  footerNode
}) => {
  return (
    <div className="glass-panel metric-card">
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      
      <div className="metric-value">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
        {statusBadge && (
          <span className={`badge ${statusBadge.type}`} style={{ marginLeft: 'auto' }}>
            {statusBadge.text}
          </span>
        )}
        {actionButton && (
          <div style={{ marginLeft: 'auto' }}>
            {actionButton}
          </div>
        )}
      </div>

      {details && details.length > 0 && (
        <div className="metric-details">
          {details.map((d, i) => (
            <div className="detail-row" key={i}>
              <span className="detail-label">{d.label}</span>
              <span className="detail-value">{d.value}</span>
            </div>
          ))}
        </div>
      )}

      {formula && <FormulaDisplay formula={formula} />}
      {footerNode && (
        <div style={{ marginTop: '1rem', borderTop: '1px solid var(--surface-border)', paddingTop: '1rem' }}>
          {footerNode}
        </div>
      )}
    </div>
  );
};
