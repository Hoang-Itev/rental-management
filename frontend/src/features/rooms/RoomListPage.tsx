import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, PropertyOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { BuildingPanel } from '../properties/BuildingPanel';

export function RoomListPage() {
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyOut | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.get<Page<PropertyOut>>('/api/v1/properties?page=1&page_size=100');
      setProperties(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách khu trọ.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Quản lý Phòng theo Khu trọ</h1>
      </div>

      <PageState loading={loading} error={error} onRetry={load}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {properties.map((prop) => (
            <div key={prop.id} style={{ border: '1px solid var(--gold-3)', background: 'var(--night-2)' }}>
              <div 
                style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', borderBottom: '1px solid var(--gold-3)' }}
                onClick={() => setSelectedProperty(prop)}
              >
                <div>
                  <h3 style={{ margin: 0, color: 'var(--gold-2)' }}>{prop.name}</h3>
                  <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>{prop.address}</p>
                </div>
                <button className="btn-primary">Xem chi tiết / Thêm tầng</button>
              </div>
            </div>
          ))}
          {properties.length === 0 && <p className="text-muted">Chưa có khu trọ nào.</p>}
        </div>
      </PageState>

      {selectedProperty && (
        <BuildingPanel 
          property={selectedProperty} 
          onClose={() => {
            setSelectedProperty(null);
            load(); // Reload lại khi đóng
          }} 
        />
      )}
    </div>
  );
}