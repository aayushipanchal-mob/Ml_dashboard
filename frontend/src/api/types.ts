export interface CampaignMapping {
  campaign_id: string;
  bundle_id: string;
}

export interface CampaignsResponse {
  campaigns: CampaignMapping[];
}

export interface Formula {
  name: string;
  expression: string;
  numerator: string;
  denominator: string;
  numerator_value?: number;
  denominator_value?: number;
}

export interface DashboardRequest {
  campaign_id: string;
  bundle_id: string;
  input_date: string;
  training_start_date?: string;
  training_end_date?: string;
  validation_start_date?: string;
  validation_end_date?: string;
  model_timestamp?: string;
  include_suppression?: boolean;
  include_cr?: boolean;
}

export interface ModelTimestampItem {
  timestamp: string;
  s3_path: string;
}

export interface ModelsListResponse {
  total: number;
  models: ModelTimestampItem[];
}

export interface DashboardResponse {
  input: {
    campaign_id: string;
    bundle_id: string;
    input_date: string;
  };
  training: {
    size: number;
    start_date: string;
    end_date: string;
    label_1_count: number;
    label_0_count: number;
  };
  validation: {
    size: number;
    start_date: string;
    end_date: string;
    label_1_count: number;
    label_0_count: number;
  };
  suppression?: {
    total_payload_devices: number;
    suppressed_devices: number;
    suppression_rate: number;
    status: string;
    formula?: Formula;
  };
  cr?: {
    total_clicked_devices: number;
    total_organic_installs: number;
    intersected_devices_24h: number;
    conversion_rate_24h: number;
    daily_trend?: any[];
    formula?: Formula;
  };
}

export interface SuppressionResponse {
  campaign_id: string;
  bundle_id: string;
  check_date: string;
  total_payload_devices: number;
  suppressed_devices: number;
  suppression_rate: number;
  status: string;
  formula?: Formula;
}

export interface CRResponse {
  campaign_id: string;
  bundle_id: string;
  start_date: string;
  end_date: string;
  data: any[];
  formula?: Formula;
}

export interface RegionCounts {
  total: number;
  delta: number;
  purge: number;
  upload_audit: number;
}

export interface ProfileCountResponse {
  country: string;
  india?: RegionCounts;
  usa?: RegionCounts;
}
