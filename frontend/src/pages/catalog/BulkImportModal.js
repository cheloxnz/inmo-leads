import React, { useState, useRef } from 'react';
import axios from 'axios';
import { API } from '../../App';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { X, Upload, FileSpreadsheet, CheckCircle2, AlertCircle, Download, Loader2 } from 'lucide-react';

export default function BulkImportModal({ onClose, onImported }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [template, setTemplate] = useState(null);
  const fileRef = useRef(null);

  React.useEffect(() => {
    axios.get(`${API}/catalog/bulk-import/template`)
      .then(r => setTemplate(r.data))
      .catch(() => {});
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post(`${API}/catalog/bulk-import`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      if (res.data.imported > 0) {
        toast.success(`${res.data.imported} producto(s) importado(s)`);
        onImported?.();
      } else {
        toast.info('No se importó ningún producto. Revisá los errores.');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error importando CSV');
    } finally {
      setUploading(false);
    }
  };

  const downloadSampleCsv = () => {
    if (!template?.sample_row) return;
    const cols = template.columns;
    const sample = template.sample_row;
    const header = cols.join(',');
    const row = cols.map(c => {
      const v = sample[c] ?? '';
      return String(v).includes(',') ? `"${v}"` : v;
    }).join(',');
    const csv = `${header}\n${row}\n`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'inmobot-catalogo-sample.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="catalog-modal-backdrop" data-testid="bulk-import-modal">
      <div className="catalog-modal" style={{ maxWidth: 640 }}>
        <div className="catalog-modal-head">
          <div>
            <h3><FileSpreadsheet className="w-5 h-5" /> Importar catálogo desde CSV</h3>
            <p className="catalog-modal-sub">
              Subí un CSV con hasta 1000 productos. Formato UTF-8 recomendado, máx 2MB.
            </p>
          </div>
          <button onClick={onClose} className="catalog-modal-close"><X className="w-4 h-4" /></button>
        </div>
        <div className="catalog-modal-body">
          {!result ? (
            <>
              {template && (
                <div className="bulk-help">
                  <div className="bulk-help-head">
                    <strong>Columnas aceptadas:</strong>
                    <Button size="sm" variant="outline" onClick={downloadSampleCsv} data-testid="btn-download-sample">
                      <Download className="w-3 h-3 mr-1" /> Descargar CSV de ejemplo
                    </Button>
                  </div>
                  <div className="bulk-help-cols">
                    {template.columns.map(c => (
                      <span key={c} className={`bulk-col ${template.required.includes(c) ? 'bulk-col-req' : ''}`}>
                        {c}{template.required.includes(c) && ' *'}
                      </span>
                    ))}
                  </div>
                  <ul className="bulk-help-notes">
                    {template.notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                </div>
              )}
              <div
                className={`bulk-dropzone ${file ? 'bulk-dropzone-selected' : ''}`}
                onClick={() => fileRef.current?.click()}
                data-testid="bulk-dropzone"
              >
                <Upload className="w-8 h-8" />
                {file ? (
                  <>
                    <strong>{file.name}</strong>
                    <span>{(file.size / 1024).toFixed(1)} KB · Click para cambiar</span>
                  </>
                ) : (
                  <>
                    <strong>Seleccionar archivo CSV</strong>
                    <span>o arrastrar acá</span>
                  </>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.tsv"
                  style={{ display: 'none' }}
                  onChange={e => setFile(e.target.files?.[0] || null)}
                  data-testid="bulk-file-input"
                />
              </div>
            </>
          ) : (
            <div className="bulk-result" data-testid="bulk-result">
              <div className="bulk-result-stats">
                <div className="bulk-stat bulk-stat-ok">
                  <CheckCircle2 className="w-5 h-5" />
                  <div>
                    <strong data-testid="bulk-imported-count">{result.imported}</strong>
                    <span>importados</span>
                  </div>
                </div>
                {result.skipped > 0 && (
                  <div className="bulk-stat bulk-stat-warn">
                    <AlertCircle className="w-5 h-5" />
                    <div>
                      <strong>{result.skipped}</strong>
                      <span>omitidos</span>
                    </div>
                  </div>
                )}
              </div>
              {result.errors?.length > 0 && (
                <div className="bulk-errors">
                  <strong>Errores ({result.total_errors}):</strong>
                  <ul>
                    {result.errors.slice(0, 20).map((e, i) => (
                      <li key={i}>Fila {e.row}: {e.reason}</li>
                    ))}
                    {result.total_errors > 20 && (
                      <li className="bulk-error-more">… y {result.total_errors - 20} más</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="catalog-modal-foot">
          {result ? (
            <>
              <span className="catalog-modal-count">
                {result.imported} / {result.total_rows} procesados
              </span>
              <Button onClick={onClose} data-testid="btn-close-bulk">Listo</Button>
            </>
          ) : (
            <>
              <span className="catalog-modal-count">{file ? '1 archivo listo' : 'Sin archivo'}</span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button variant="outline" onClick={onClose}>Cancelar</Button>
                <Button onClick={handleUpload} disabled={!file || uploading} data-testid="btn-start-import">
                  {uploading ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Importando...</> : <><Upload className="w-3 h-3 mr-1" /> Importar</>}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
