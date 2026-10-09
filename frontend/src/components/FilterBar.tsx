import React from 'react';
import type { CampaignMapping, DashboardRequest, ModelTimestampItem } from '../api/types';
import { Search } from 'lucide-react';

interface FilterBarProps {
  campaigns: CampaignMapping[];
  models: ModelTimestampItem[];
  params: DashboardRequest;
  onChange: (key: keyof DashboardRequest, value: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isLoading: boolean;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  campaigns,
  models,
  params,
  onChange,
  onSubmit,
  onCancel,
  isLoading
}) => {
  // Extract unique campaigns
  const uniqueCampaigns = Array.from(new Set(campaigns.map(c => c.campaign_id)));
  
  // Filter bundles based on selected campaign
  const availableBundles = campaigns
    .filter(c => c.campaign_id === params.campaign_id)
    .map(c => c.bundle_id);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form className="glass-panel" onSubmit={handleSubmit}>
      <div className="filter-grid" style={{ marginBottom: '1.5rem' }}>
        
        <div className="form-group">
          <label className="form-label">Campaign ID</label>
          <select 
            className="form-control" 
            value={params.campaign_id}
            onChange={(e) => {
              onChange('campaign_id', e.target.value);
              // Reset bundle when campaign changes
              const newBundles = campaigns.filter(c => c.campaign_id === e.target.value);
              if (newBundles.length > 0) {
                onChange('bundle_id', newBundles[0].bundle_id);
              }
            }}
            required
          >
            <option value="">Select Campaign</option>
            {uniqueCampaigns.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Bundle ID</label>
          <select 
            className="form-control" 
            value={params.bundle_id}
            onChange={(e) => onChange('bundle_id', e.target.value)}
            required
            disabled={!params.campaign_id}
          >
            <option value="">Select Bundle</option>
            {availableBundles.map(b => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Target Input Date</label>
          <input 
            type="date" 
            className="form-control" 
            value={params.input_date}
            onChange={(e) => onChange('input_date', e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Model Timestamp</label>
          <select 
            className="form-control" 
            value={params.model_timestamp || ''}
            onChange={(e) => onChange('model_timestamp', e.target.value)}
          >
            <option value="">Latest Model (Default)</option>
            {models.map(m => (
              <option key={m.timestamp} value={m.timestamp}>
                {m.timestamp.replace(/_/, ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>



      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
        {isLoading && onCancel && (
          <button type="button" className="btn-primary" onClick={onCancel} style={{ background: 'var(--danger)' }}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn-primary" disabled={isLoading}>
          <Search size={18} />
          {isLoading ? 'Checking...' : 'Run Dashboard Checks'}
        </button>
      </div>
    </form>
  );
};
