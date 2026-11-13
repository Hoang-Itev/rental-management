// ===== Auth =====
export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
}

// ===== Room =====
export interface PropertyOut {
  id: string;
  name: string;
  address: string;
  description: string | null;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface RoomOut {
  id: string;
  property_id: string;
  floor_id: string;
  room_code: string;
  area_m2: number;
  listed_rent: number;
  status: 'ACTIVE' | 'INACTIVE';
  occupancy_contract_id: string | null;
  display_occupancy: 'VACANT' | 'OCCUPIED' | 'INACTIVE';
  occupancy_updated_at: string | null;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

// ===== Tenant =====
export interface TenantOut {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  note: string | null;
}

export type ContractStatus =
  | 'DRAFT'
  | 'SCHEDULED'
  | 'ACTIVE'
  | 'EXPIRED_PENDING'
  | 'ENDED'
  | 'CANCELLED';

export interface ContractOut {
  id: string;
  contract_code: string;
  room_id: string;
  room_code_snapshot: string;
  representative_tenant_id: string;
  start_date: string;
  end_date: string;
  actual_end_date: string | null;
  status: ContractStatus;
  deposit_amount: number | null;
  end_reason: string | null;
}

// ===== Contract Terms =====
export interface TermOut {
  id: string;
  contract_id: string;
  effective_from: string;
  effective_to: string | null;
  monthly_rent: number;
  electricity_unit_price: number;
  water_unit_price: number;
  monthly_service_fee: number;
}

// ===== Meter =====
export interface MeterOut {
  id: string;
  room_id: string;
  meter_code: string;
  meter_type: 'ELECTRICITY' | 'WATER';
  unit: string;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface RoomMeterList {
  items: MeterOut[];
}

export interface CutoffReasonOut {
  contract_id: string;
  reason_type: 'CONTRACT_START' | 'CONTRACT_END';
}

export interface CutoffOut {
  id: string;
  meter_id: string;
  contract_id: string | null;
  cutoff_type: 'CONTRACT_START' | 'CONTRACT_END' | 'MONTHLY';
  cutoff_at: string;
  reading_value: string | number | null;
  source: 'AUTOMATIC' | 'MANUAL';
  source_reading_at: string | null;
  manual_reason: string | null;
  status: 'PENDING' | 'CONFIRMED' | 'SUPERSEDED';
  confirmed_at: string | null;
  confirmed_by: string | null;
  supersedes_id: string | null;
  created_at: string;
  reasons: CutoffReasonOut[];
}

// ===== Invoice =====
export type InvoiceStatus = 'DRAFT' | 'ISSUED' | 'PAID' | 'VOID';

export interface InvoiceItemView {
  id: string;
  invoice_id: string;
  item_type: 'RENT' | 'ELECTRICITY' | 'WATER' | 'SERVICE';
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
  period_start: string | null;
  period_end: string | null;
  meter_start_value: number | null;
  meter_end_value: number | null;
  source_term_id: string | null;
  source_cutoff_start_id: string | null;
  source_cutoff_end_id: string | null;
}

export interface InvoiceDetail {
  id: string;
  invoice_code: string;
  contract_id: string;
  room_id: string;
  invoice_type: 'PERIODIC' | 'FINAL';
  billing_month: string | null;
  period_start: string;
  period_end: string;
  status: InvoiceStatus;
  blocked_reason: string | null;
  revision: number;
  replaces_invoice_id: string | null;
  void_reason: string | null;
  voided_at: string | null;
  total_amount: number;
  due_date: string;
  issued_at: string | null;
  paid_at: string | null;
  tenant_name_snapshot: string;
  tenant_email_snapshot: string | null;
  room_code_snapshot: string;
  items: InvoiceItemView[];
}

// ===== Public invoice / SePay =====
export interface PublicInvoiceItem {
  item_type: 'RENT' | 'ELECTRICITY' | 'WATER' | 'SERVICE';
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
}

export interface PublicInvoiceView {
  invoice_code: string;
  room_code: string;
  tenant_name: string;
  period_start: string;
  period_end: string;
  status: 'ISSUED' | 'PAID';
  total_amount: number;
  due_date: string;
  items: PublicInvoiceItem[];
}

export interface SePayCheckoutSession {
  payment_attempt_id: string;
  status: 'PENDING' | 'SUCCESS';
  reused_pending_attempt: boolean;
  checkout_status: 'READY' | 'PAID';
  action_url: string | null;
  method: 'POST';
  fields: Record<string, string> | null;
}