import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { getCampaigns, getDashboardData, getModelsList, getSuppressionData, getCRData, getProfileCount } from '../api/client';
import type { CampaignMapping, DashboardRequest, DashboardResponse, ModelTimestampItem, ProfileCountResponse } from '../api/types';
import { FilterBar } from './FilterBar';
import { MetricCard } from './MetricCard';
import { Activity, Database, ShieldAlert, TrendingUp, Sun, Moon, Monitor, Users } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [campaigns, setCampaigns] = useState<CampaignMapping[]>([]);
  const [models, setModels] = useState<ModelTimestampItem[]>([]);
  const [isAppLoading, setIsAppLoading] = useState(true);
  const [theme, setTheme] = useState<'default' | 'light' | 'dark'>('default');
  
  useEffect(() => {
    if (theme === 'default') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
  }, [theme]);
  
  const [params, setParams] = useState<DashboardRequest>({
    campaign_id: '',
    bundle_id: '',
    input_date: new Date().toISOString().split('T')[0],
    training_start_date: undefined,
    training_end_date: undefined,
    validation_start_date: undefined,
    validation_end_date: undefined,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardResponse | null>(null);

  const [isCalculatingSuppression, setIsCalculatingSuppression] = useState(false);
  const [isCalculatingCR, setIsCalculatingCR] = useState(false);
  const [profileCountry, setProfileCountry] = useState<'india' | 'usa' | 'both'>('india');
  const [isCalculatingProfile, setIsCalculatingProfile] = useState(false);
  const [profileData, setProfileData] = useState<ProfileCountResponse | null>(null);

  const dashboardAbortCtrl = useRef<AbortController | null>(null);
  const suppressionAbortCtrl = useRef<AbortController | null>(null);
  const crAbortCtrl = useRef<AbortController | null>(null);
  const profileAbortCtrl = useRef<AbortController | null>(null);

  useEffect(() => {
    const init = async () => {
      try {
        const res = await getCampaigns();
        setCampaigns(res.campaigns);
        
        try {
          const modelsRes = await getModelsList();
          setModels(modelsRes.models);
        } catch (e) {
          console.warn("Failed to fetch models", e);
        }
        
        // Setup defaults based on today
        const today = new Date();
        const inputDate = today.toISOString().split('T')[0];
        
        const vEnd = new Date(today); vEnd.setDate(vEnd.getDate() - 1);
        const vStart = new Date(today); vStart.setDate(vStart.getDate() - 3);
        
        const tEnd = new Date(today); tEnd.setDate(tEnd.getDate() - 4);
        const tStart = new Date(today); tStart.setDate(tStart.getDate() - 28); // ~4 weeks

        if (res.campaigns.length > 0) {
          setParams({
            campaign_id: res.campaigns[0].campaign_id,
            bundle_id: res.campaigns[0].bundle_id,
            input_date: inputDate,
            training_start_date: undefined,
            training_end_date: undefined,
            validation_start_date: undefined,
            validation_end_date: undefined,
          });
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load campaigns');
      } finally {
        setIsAppLoading(false);
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (!params.model_timestamp) return;
    const fetchCampaigns = async () => {
      try {
        const res = await getCampaigns(params.model_timestamp);
        setCampaigns(res.campaigns);
        if (res.campaigns.length > 0) {
          const isValid = res.campaigns.some(c => c.campaign_id === params.campaign_id);
          if (!isValid) {
            setParams(prev => ({
              ...prev,
              campaign_id: res.campaigns[0].campaign_id,
              bundle_id: res.campaigns[0].bundle_id
            }));
          }
        }
      } catch (err) {
        console.error("Failed to fetch campaigns for model", err);
      }
    };
    fetchCampaigns();
  }, [params.model_timestamp]);

  const handleParamChange = (key: keyof DashboardRequest, value: string) => {
    setParams(prev => ({ ...prev, [key]: value }));
  };

  const handleRunChecks = async () => {
    setIsLoading(true);
    setError(null);
    dashboardAbortCtrl.current = new AbortController();
    try {
      const res = await getDashboardData(params, dashboardAbortCtrl.current.signal);
      setData(res);
    } catch (err: any) {
      if (axios.isCancel(err)) {
        console.log('Dashboard check canceled');
        setError('Dashboard check canceled by user');
      } else {
        setError(err.response?.data?.detail || err.message || 'Failed to fetch dashboard data');
      }
    } finally {
      setIsLoading(false);
      dashboardAbortCtrl.current = null;
    }
  };

  const handleCalculateSuppression = async () => {
    if (!data) return;
    setIsCalculatingSuppression(true);
    suppressionAbortCtrl.current = new AbortController();
    try {
      const supData = await getSuppressionData({
        campaign_id: params.campaign_id,
        bundle_id: params.bundle_id,
        date: params.input_date,
      }, suppressionAbortCtrl.current.signal);
      setData(prevData => prevData ? { ...prevData, suppression: supData } : null);
    } catch (err: any) {
      if (!axios.isCancel(err)) {
        alert(err.response?.data?.detail || err.message || 'Failed to calculate suppression');
      }
    } finally {
      setIsCalculatingSuppression(false);
      suppressionAbortCtrl.current = null;
    }
  };

  const handleCalculateCR = async () => {
    if (!data) return;
    setIsCalculatingCR(true);
    crAbortCtrl.current = new AbortController();
    try {
      const rawStartDate = data.validation.start_date || params.input_date;
      let formattedStartDate = rawStartDate.length === 8 && !rawStartDate.includes('-') 
        ? `${rawStartDate.slice(0,4)}-${rawStartDate.slice(4,6)}-${rawStartDate.slice(6,8)}` 
        : rawStartDate;

      // Cap the CR calculation to 7 days max to prevent Athena timeouts on massive date ranges
      const inputDateObj = new Date(params.input_date);
      const startObj = new Date(formattedStartDate);
      const diffDays = (inputDateObj.getTime() - startObj.getTime()) / (1000 * 3600 * 24);
      
      if (diffDays > 7) {
        const cappedDate = new Date(inputDateObj);
        cappedDate.setDate(cappedDate.getDate() - 7);
        formattedStartDate = cappedDate.toISOString().split('T')[0];
      }

      const crData = await getCRData({
        campaign_id: params.campaign_id,
        bundle_id: params.bundle_id,
        start_date: formattedStartDate,
        end_date: params.input_date,
      }, crAbortCtrl.current.signal);
      
      const cr_rows = crData.data;
      const total_clicks = cr_rows.reduce((sum, r) => sum + r.total_clicked_devices, 0);
      const total_installs = cr_rows.reduce((sum, r) => sum + r.total_organic_installs, 0);
      const total_intersected = cr_rows.reduce((sum, r) => sum + r.intersected_devices_24h, 0);
      const agg_cr = total_clicks > 0 ? (total_intersected / total_clicks) * 100 : 0.0;
      
      setData(prevData => prevData ? {
        ...prevData,
        cr: {
          total_clicked_devices: total_clicks,
          total_organic_installs: total_installs,
          intersected_devices_24h: total_intersected,
          conversion_rate_24h: agg_cr,
          daily_trend: cr_rows,
          formula: crData.formula,
        }
      } : null);
    } catch (err: any) {
      if (!axios.isCancel(err)) {
        alert(err.response?.data?.detail || err.message || 'Failed to calculate CR');
      }
    } finally {
      setIsCalculatingCR(false);
      crAbortCtrl.current = null;
    }
  };

  const handleCalculateProfile = async () => {
    setIsCalculatingProfile(true);
    profileAbortCtrl.current = new AbortController();
    try {
      const res = await getProfileCount(profileCountry, profileAbortCtrl.current.signal);
      setProfileData(res);
    } catch (err: any) {
      if (!axios.isCancel(err)) {
        alert(err.response?.data?.detail || err.message || 'Failed to calculate profile count');
      }
    } finally {
      setIsCalculatingProfile(false);
      profileAbortCtrl.current = null;
    }
  };

  if (isAppLoading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading Dashboard Initialization...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="header">
        <h1 className="header-title">
          <Activity color="var(--accent-blue)" size={32} />
          ML Monitor Dashboard
        </h1>
        <div style={{ display: 'flex', gap: '0.5rem', background: 'var(--surface-color)', padding: '0.25rem', borderRadius: '0.5rem', border: '1px solid var(--surface-border)' }}>
          <button 
            onClick={() => setTheme('default')}
            style={{ background: theme === 'default' ? 'var(--accent-blue)' : 'transparent', color: theme === 'default' ? 'white' : 'var(--text-muted)', border: 'none', padding: '0.5rem', borderRadius: '0.25rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            title="Default Theme"
          >
            <Monitor size={18} />
          </button>
          <button 
            onClick={() => setTheme('light')}
            style={{ background: theme === 'light' ? 'var(--accent-blue)' : 'transparent', color: theme === 'light' ? 'white' : 'var(--text-muted)', border: 'none', padding: '0.5rem', borderRadius: '0.25rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            title="Light Theme"
          >
            <Sun size={18} />
          </button>
          <button 
            onClick={() => setTheme('dark')}
            style={{ background: theme === 'dark' ? 'var(--accent-blue)' : 'transparent', color: theme === 'dark' ? 'white' : 'var(--text-muted)', border: 'none', padding: '0.5rem', borderRadius: '0.25rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            title="Dark Theme"
          >
            <Moon size={18} />
          </button>
        </div>
      </div>

      <FilterBar 
        campaigns={campaigns}
        models={models}
        params={params}
        onChange={handleParamChange}
        onSubmit={handleRunChecks}
        onCancel={() => dashboardAbortCtrl.current?.abort()}
        isLoading={isLoading}
      />

      {error && (
        <div className="error-container">
          <ShieldAlert size={24} />
          <span>{error}</span>
        </div>
      )}

      {isLoading && !data && (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Fetching Training & Validation data...</p>
        </div>
      )}

      {!isLoading && !error && !data && (
        <div className="empty-state">
          <h2>Ready to Check</h2>
          <p>Select your campaign, bundle, and date ranges above to run the ML Dashboard checks.</p>
        </div>
      )}

      {(data || isLoading) && (
        <div className="dashboard-grid" style={{ opacity: isLoading ? 0.6 : 1, pointerEvents: isLoading ? 'none' : 'auto' }}>
          
          <MetricCard
            title="Training Data"
            icon={<Database color="var(--accent-blue)" size={24} />}
            value={data ? data.training.size.toLocaleString() : "-"}
            unit={data ? "rows" : ""}
            details={data ? [
              { label: 'Start Date', value: data.training.start_date },
              { label: 'End Date', value: data.training.end_date },
              { label: "1's Count", value: data.training.label_1_count.toLocaleString() },
              { label: "0's Count", value: data.training.label_0_count.toLocaleString() }
            ] : undefined}
          />

          <MetricCard
            title="Validation Data"
            icon={<Database color="var(--accent-purple)" size={24} />}
            value={data ? data.validation.size.toLocaleString() : "-"}
            unit={data ? "rows" : ""}
            details={data ? [
              { label: 'Start Date', value: data.validation.start_date },
              { label: 'End Date', value: data.validation.end_date },
              { label: "1's Count", value: data.validation.label_1_count.toLocaleString() },
              { label: "0's Count", value: data.validation.label_0_count.toLocaleString() }
            ] : undefined}
          />

          <MetricCard
            title="Suppression Rate"
            icon={<ShieldAlert color="var(--warning)" size={24} />}
            value={data?.suppression ? `${data.suppression.suppression_rate.toFixed(2)}%` : "-"}
            statusBadge={data?.suppression ? {
              text: data.suppression.status,
              type: data.suppression.status === 'PASS' ? 'success' : 'danger'
            } : undefined}
            details={data?.suppression ? [
              { label: 'Total Devices', value: data.suppression.total_payload_devices.toLocaleString() },
              { label: 'Suppressed', value: data.suppression.suppressed_devices.toLocaleString() }
            ] : undefined}
            formula={data?.suppression?.formula}
            actionButton={data && !data.suppression && (
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button 
                  className="submit-btn" 
                  onClick={handleCalculateSuppression} 
                  disabled={isCalculatingSuppression}
                  style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                >
                  {isCalculatingSuppression ? 'Calculating...' : 'Calculate'}
                </button>
                {isCalculatingSuppression && (
                  <button 
                    className="submit-btn" 
                    onClick={() => suppressionAbortCtrl.current?.abort()} 
                    style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', background: 'var(--danger)', border: 'none', color: 'white', borderRadius: '0.25rem', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            )}
          />

          <MetricCard
            title="24h Conversion Rate"
            icon={<TrendingUp color="var(--success)" size={24} />}
            value={data?.cr ? `${data.cr.conversion_rate_24h.toFixed(2)}%` : "-"}
            details={data?.cr ? [
              { label: 'Total Clicks', value: data.cr.total_clicked_devices.toLocaleString() },
              { label: 'Organic Installs', value: data.cr.total_organic_installs.toLocaleString() },
              { label: 'Intersected', value: data.cr.intersected_devices_24h.toLocaleString() }
            ] : undefined}
            formula={data?.cr?.formula}
            actionButton={data && !data.cr && (
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button 
                  className="submit-btn" 
                  onClick={handleCalculateCR} 
                  disabled={isCalculatingCR}
                  style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                >
                  {isCalculatingCR ? 'Calculating...' : 'Calculate'}
                </button>
                {isCalculatingCR && (
                  <button 
                    className="submit-btn" 
                    onClick={() => crAbortCtrl.current?.abort()} 
                    style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', background: 'var(--danger)', border: 'none', color: 'white', borderRadius: '0.25rem', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            )}
          />
          
          <MetricCard
            title="Profile Count (Latest)"
            icon={<Users color="var(--accent-blue)" size={24} />}
            value={
              profileData 
                ? (profileData.country === 'both' ? "Both Regions" : 
                   (profileData.country === 'india' ? (profileData.india?.total || 0).toLocaleString() : (profileData.usa?.total || 0).toLocaleString()))
                : "-"
            }
            unit={profileData && profileData.country === 'both' ? "" : "profiles"}
            details={
              profileData && profileData.country === 'both'
                ? [
                    { label: 'India Total', value: (profileData.india?.total || 0).toLocaleString() },
                    { label: 'India Delta', value: (profileData.india?.delta || 0).toLocaleString() },
                    { label: 'India Purge', value: (profileData.india?.purge || 0).toLocaleString() },
                    { label: 'India Upload Audit', value: (profileData.india?.upload_audit || 0).toLocaleString() },
                    { label: 'USA Total', value: (profileData.usa?.total || 0).toLocaleString() },
                    { label: 'USA Delta', value: (profileData.usa?.delta || 0).toLocaleString() },
                    { label: 'USA Purge', value: (profileData.usa?.purge || 0).toLocaleString() },
                    { label: 'USA Upload Audit', value: (profileData.usa?.upload_audit || 0).toLocaleString() }
                  ]
                : profileData && profileData.country === 'india'
                ? [
                    { label: 'Delta Upsert', value: (profileData.india?.delta || 0).toLocaleString() },
                    { label: 'Purge Deletes', value: (profileData.india?.purge || 0).toLocaleString() },
                    { label: 'Upload Audit', value: (profileData.india?.upload_audit || 0).toLocaleString() }
                  ]
                : profileData && profileData.country === 'usa'
                ? [
                    { label: 'Delta Upsert', value: (profileData.usa?.delta || 0).toLocaleString() },
                    { label: 'Purge Deletes', value: (profileData.usa?.purge || 0).toLocaleString() },
                    { label: 'Upload Audit', value: (profileData.usa?.upload_audit || 0).toLocaleString() }
                  ]
                : undefined
            }
            footerNode={(
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', justifyContent: 'flex-start', flexWrap: 'wrap' }}>
                <select 
                  value={profileCountry}
                  onChange={(e) => {
                    setProfileCountry(e.target.value as 'india' | 'usa' | 'both');
                    setProfileData(null);
                  }}
                  style={{
                    padding: '0.5rem',
                    borderRadius: '0.25rem',
                    border: '1px solid var(--surface-border)',
                    background: 'var(--surface-color)',
                    color: 'var(--text-color)',
                    flex: '1',
                    maxWidth: '150px'
                  }}
                >
                  <option value="india">India</option>
                  <option value="usa">USA</option>
                  <option value="both">Both</option>
                </select>
                <button 
                  className="submit-btn" 
                  onClick={handleCalculateProfile} 
                  disabled={isCalculatingProfile}
                  style={{ padding: '0.5rem 1.5rem', fontSize: '0.875rem' }}
                >
                  {isCalculatingProfile ? 'Calculating...' : 'Calculate'}
                </button>
                {isCalculatingProfile && (
                  <button 
                    className="submit-btn" 
                    onClick={() => profileAbortCtrl.current?.abort()} 
                    style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', background: 'var(--danger)', border: 'none', color: 'white', borderRadius: '0.25rem', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            )}
          />
        </div>
      )}
    </div>
  );
};
