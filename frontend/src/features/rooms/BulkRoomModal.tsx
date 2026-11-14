import { useState } from 'react';
import * as XLSX from 'xlsx';
import { api, ApiError } from '../../lib/api/client';

interface RoomInput {
  room_code: string;
  area_m2: string;
  listed_rent: string;
}

interface Props {
  floorId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function BulkRoomModal({ floorId, onClose, onSuccess }: Props) {
  // 1. Khởi tạo với 1 dòng trống để nhập thủ công
  const [rooms, setRooms] = useState<RoomInput[]>([{ room_code: '', area_m2: '20', listed_rent: '2000000' }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 2. Hàm xử lý Upload Excel
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: 'binary' });
        const wsname = wb.SheetNames[0];
        const ws = wb.Sheets[wsname];
        
        // Đọc dữ liệu từ file Excel (A: Mã phòng, B: Diện tích, C: Giá thuê)
        const data = XLSX.utils.sheet_to_json<any>(ws, { header: 1 });
        
        if (data.length < 2) {
          throw new Error('File Excel phải có ít nhất 1 dòng dữ liệu (ngoài dòng tiêu đề).');
        }

        const parsed: RoomInput[] = [];
        const seenCodes = new Set<string>();
        const errors: string[] = [];

        // Bỏ qua dòng đầu tiên (header), duyệt từ dòng thứ 2
        for (let i = 1; i < data.length; i++) {
          const row = data[i];
          if (!row || row.length === 0) continue; // Bỏ qua dòng trống

          const code = String(row[0] || '').trim();
          const area = String(row[1] || '').trim();
          const rent = String(row[2] || '').trim();

          // Validate dữ liệu từng dòng
          if (!code) continue; // Bỏ qua nếu không có mã phòng
          if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(code)) {
            errors.push(`Dòng ${i + 1}: Mã phòng không hợp lệ ("${code}")`);
          }
          if (seenCodes.has(code.toUpperCase())) {
            errors.push(`Dòng ${i + 1}: Mã phòng bị trùng ("${code}")`);
          }
          seenCodes.add(code.toUpperCase());

          const numArea = Number(area);
          if (isNaN(numArea) || numArea <= 0) {
            errors.push(`Dòng ${i + 1}: Diện tích phải > 0 ("${area}")`);
          }

          const numRent = Number(rent);
          if (isNaN(numRent) || !Number.isInteger(numRent) || numRent < 0) {
            errors.push(`Dòng ${i + 1}: Giá thuê phải là số nguyên >= 0 ("${rent}")`);
          }

          parsed.push({
            room_code: code,
            area_m2: isNaN(numArea) || numArea <= 0 ? '20' : area, // Fallback nếu sai
            listed_rent: isNaN(numRent) || numRent < 0 ? '2000000' : rent,
          });
        }

        // Nếu có lỗi validate, hiển thị lên và KHÔNG ghi đè danh sách hiện tại
        if (errors.length > 0) {
          setError(`File Excel có lỗi:\n` + errors.slice(0, 5).join('\n') + (errors.length > 5 ? `\n... và ${errors.length - 5} lỗi khác.` : ''));
          return;
        }

        if (parsed.length === 0) {
          throw new Error('Không tìm thấy dữ liệu phòng hợp lệ trong file.');
        }

        // Ghi đè danh sách hiện tại bằng dữ liệu từ Excel
        setRooms(parsed);
        setError(null);
        alert(`Đã tải lên thành công ${parsed.length} phòng. Vui lòng kiểm tra lại danh sách bên dưới trước khi bấm "Xác nhận tạo".`);
      } catch (err: any) {
        setError(err.message || 'Lỗi đọc file Excel. Hãy chắc chắn file có 3 cột: Mã phòng, Diện tích, Giá.');
      }
    };
    reader.readAsBinaryString(file);
    // Reset input file để có thể upload lại cùng 1 file nếu muốn
    e.target.value = '';
  }

  // 3. Hàm thêm dòng thủ công
  function addRow() {
    setRooms([...rooms, { room_code: '', area_m2: '20', listed_rent: '2000000' }]);
  }

  // 4. Hàm xoá dòng
  function removeRow(idx: number) {
    setRooms(rooms.filter((_, i) => i !== idx));
  }

  // 5. Cập nhật dữ liệu ô nhập
  function updateRow(idx: number, field: keyof RoomInput, value: string) {
    const newRooms = [...rooms];
    newRooms[idx][field] = value;
    setRooms(newRooms);
  }

  // 6. Submit lên API
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    
    // Validate lại toàn bộ danh sách trước khi gửi
    const validRooms = rooms.filter(r => r.room_code.trim());
    if (validRooms.length === 0) { setError('Chưa có phòng nào.'); return; }

    const seen = new Set<string>();
    for (const r of validRooms) {
      if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(r.room_code)) { setError(`Mã phòng không hợp lệ: ${r.room_code}`); return; }
      if (seen.has(r.room_code.toUpperCase())) { setError(`Mã phòng bị trùng: ${r.room_code}`); return; }
      seen.add(r.room_code.toUpperCase());
      if (!(Number(r.area_m2) > 0)) { setError(`Diện tích phải > 0: ${r.room_code}`); return; }
      if (!(Number.isInteger(Number(r.listed_rent)) && Number(r.listed_rent) >= 0)) { setError(`Giá thuê không hợp lệ: ${r.room_code}`); return; }
    }

    setSubmitting(true);
    try {
      await api.postIdempotent(`/api/v1/floors/${floorId}/rooms/bulk`, {
        rooms: validRooms.map(r => ({
          room_code: r.room_code.trim(),
          area_m2: Number(r.area_m2),
          listed_rent: Number(r.listed_rent),
        }))
      });
      onSuccess();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Lỗi khi tạo phòng.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal" style={{ width: 'min(900px, 96vw)' }}>
        <button className="modal-close" onClick={onClose}>×</button>
        <h2 className="modal-title">Thêm phòng (Tối đa 100)</h2>
        
        {/* KHU VỰC UPLOAD EXCEL */}
        <div style={{ padding: 16, background: 'var(--night-1)', marginBottom: 16, border: '1px dashed var(--gold-3)' }}>
          <label style={{ display: 'block', marginBottom: 8, color: 'var(--gold-2)' }}>Tải lên từ Excel (Tự động điền vào bảng bên dưới)</label>
          <input type="file" accept=".xlsx, .xls" onChange={handleFileUpload} style={{ padding: 6, background: 'transparent', border: 'none', color: 'var(--ink)' }} />
          <p className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
            * File Excel cần có 3 cột theo thứ tự: <b>Mã phòng</b> | <b>Diện tích (m²)</b> | <b>Giá thuê (VNĐ)</b>. Dòng đầu tiên là tiêu đề.
          </p>
        </div>

        {error && <div className="login-error" style={{ whiteSpace: 'pre-wrap' }}>{error}</div>}

        <form onSubmit={submit}>
          <div style={{ maxHeight: '40vh', overflowY: 'auto', border: '1px solid var(--gold-3)' }}>
            <table className="data-table" style={{ margin: 0 }}>
              <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                <tr><th>Mã phòng *</th><th>Diện tích (m²) *</th><th>Giá thuê (VNĐ) *</th><th style={{ width: 60 }}></th></tr>
              </thead>
              <tbody>
                {rooms.map((r, idx) => (
                  <tr key={idx}>
                    <td>
                      <input 
                        value={r.room_code} 
                        onChange={(e) => updateRow(idx, 'room_code', e.target.value)} 
                        required 
                        placeholder="VD: A101"
                        style={{ padding: 6, width: '100%', background: 'transparent', border: '1px solid var(--gold-3)' }} 
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        step="0.01" 
                        min="0.01" 
                        value={r.area_m2} 
                        onChange={(e) => updateRow(idx, 'area_m2', e.target.value)} 
                        required 
                        style={{ padding: 6, width: '100%', background: 'transparent', border: '1px solid var(--gold-3)' }} 
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        min="0" 
                        step="1000" 
                        value={r.listed_rent} 
                        onChange={(e) => updateRow(idx, 'listed_rent', e.target.value)} 
                        required 
                        style={{ padding: 6, width: '100%', background: 'transparent', border: '1px solid var(--gold-3)' }} 
                      />
                    </td>
                    <td>
                      <button 
                        type="button" 
                        className="btn-secondary" 
                        onClick={() => removeRow(idx)} 
                        disabled={rooms.length <= 1}
                        title="Xoá dòng này"
                      >
                        X
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
            <button type="button" className="btn-secondary" onClick={addRow} disabled={rooms.length >= 100}>
              + Thêm dòng thủ công
            </button>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="modal-btn" onClick={onClose} disabled={submitting}>Hủy</button>
              <button type="submit" className="modal-btn primary" disabled={submitting}>
                {submitting ? 'Đang tạo…' : 'Xác nhận tạo'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}