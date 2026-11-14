interface Props {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyText?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function PageState({ loading, error, empty, emptyText, onRetry, children }: Props) {
  if (loading) return <div className="loading-text">Đang tải…</div>;
  if (error) {
    return (
      <div className="page-error">
        <div>{error}</div>
        {onRetry && (
          <button className="btn-secondary" style={{ marginTop: 12 }} onClick={onRetry}>
            Thử lại
          </button>
        )}
      </div>
    );
  }
  if (empty) return <div className="empty-row">{emptyText ?? 'Không có dữ liệu.'}</div>;
  return <>{children}</>;
}