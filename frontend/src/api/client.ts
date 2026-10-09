import axios from 'axios';
import type { CampaignsResponse, DashboardRequest, DashboardResponse, ModelsListResponse, SuppressionResponse, CRResponse, ProfileCountResponse } from './types';

const API_BASE_URL = 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getCampaigns = async (timestamp?: string): Promise<CampaignsResponse> => {
  const url = timestamp ? `/campaigns?timestamp=${timestamp}` : '/campaigns';
  const response = await apiClient.get<CampaignsResponse>(url);
  return response.data;
};

export const getModelsList = async (): Promise<ModelsListResponse> => {
  const response = await apiClient.get<ModelsListResponse>('/models');
  return response.data;
};

export const getDashboardData = async (params: DashboardRequest, signal?: AbortSignal): Promise<DashboardResponse> => {
  const response = await apiClient.post<DashboardResponse>('/dashboard/check', params, { signal });
  return response.data;
};

export const getSuppressionData = async (params: { campaign_id: string, bundle_id: string, date: string }, signal?: AbortSignal): Promise<SuppressionResponse> => {
  const response = await apiClient.get<SuppressionResponse>('/suppression', { params, signal });
  return response.data;
};

export const getCRData = async (params: { campaign_id: string, bundle_id: string, start_date: string, end_date: string }, signal?: AbortSignal): Promise<CRResponse> => {
  const response = await apiClient.get<CRResponse>('/cr', { params, signal });
  return response.data;
};

export const getProfileCount = async (country: string, signal?: AbortSignal): Promise<ProfileCountResponse> => {
  const response = await apiClient.get<ProfileCountResponse>('/profile-counts', { params: { country }, signal });
  return response.data;
};
