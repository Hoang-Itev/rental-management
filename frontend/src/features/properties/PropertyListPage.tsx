import { useState, useEffect } from 'react';
import { api } from '../../lib/api/client';
import type { Page, PropertyOut } from '../../lib/api/types';

export function PropertyListPage() {
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Page<PropertyOut>>('/api/v1/properties?page=1&page_size=50')
      .then(res => setProperties(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-text">Đang tải cấu trúc...</div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Khu trọ & Cấu trúc</h1>
      </div>
      <div className="property-grid">
        {properties.map(p => (
          <div key={p.id} className="property-card">
            <h3>{p.name}</h3>
            <p>{p.address}</p>
            <span className="badge active">{p.status}</span>
            {/* Thực tế sẽ gọi API lấy buildings/floors ở đây */}
            <div className="property-tree">
              <p style={{ color: 'var(--ink-dim)', fontStyle: 'italic', fontSize: 12 }}>
                Tính năng xem Dãy/Tầng đang phát triển.
              </p>
            </div>
          </div>
        ))}
        {properties.length === 0 && <p>Chưa có khu trọ nào.</p>}
      </div>
    </div>
  );
}