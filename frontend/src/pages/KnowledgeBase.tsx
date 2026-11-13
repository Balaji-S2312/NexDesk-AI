import React, { useCallback, useEffect, useState } from 'react';
import {
  BookOpen,
  FileText,
  Upload,
  Trash2,
  RefreshCw,
  Sparkles,
  Layers,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  Search,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import {
  deleteKnowledgeDocumentApi,
  getKnowledgeDocumentApi,
  listKnowledgeDocumentsApi,
  reprocessKnowledgeDocumentApi,
  semanticSearchKnowledgeApi,
  uploadKnowledgeDocumentApi,
} from '../services/api';
import {
  DocumentStatus,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  SemanticSearchResultItem,
} from '../types/knowledge';
import { Modal } from '../components/Modal';
import { ConfirmationDialog } from '../components/ConfirmationDialog';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/LoadingSkeleton';
import { SearchBar } from '../components/SearchBar';

const CATEGORIES = [
  { label: 'All Documentation', value: 'all' },
  { label: 'General', value: 'general' },
  { label: 'Network', value: 'network' },
  { label: 'Hardware', value: 'hardware' },
  { label: 'Software', value: 'software' },
  { label: 'Security', value: 'security' },
  { label: 'Access Management', value: 'access_management' },
];

const formatBytes = (bytes: number): string => {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const StatusPill: React.FC<{ status: DocumentStatus }> = ({ status }) => {
  switch (status) {
    case 'completed':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3" /> Indexed
        </span>
      );
    case 'processing':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <RefreshCw className="w-3 h-3 animate-spin" /> Processing
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <AlertCircle className="w-3 h-3" /> Failed
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
          <Clock className="w-3 h-3" /> Pending
        </span>
      );
  }
};

export const KnowledgeBase: React.FC = () => {
  const { isAdmin } = useAuth();
  const { showToast } = useToast();

  // Document list state
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [nameSearch, setNameSearch] = useState('');
  const [debouncedName, setDebouncedName] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');

  // Semantic search state
  const [semanticQuery, setSemanticQuery] = useState('');
  const [searchingVector, setSearchingVector] = useState(false);
  const [semanticResults, setSemanticResults] = useState<SemanticSearchResultItem[] | null>(null);

  // Upload modal state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadCategory, setUploadCategory] = useState('general');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Inspect, reprocess, delete state
  const [detailDoc, setDetailDoc] = useState<KnowledgeDocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeDocument | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedName(nameSearch.trim()), 250);
    return () => clearTimeout(t);
  }, [nameSearch]);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listKnowledgeDocumentsApi({
        q: debouncedName || undefined,
        category: activeCategory,
      });
      setDocuments(res.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load knowledge documents';
      showToast({ type: 'error', title: 'Load Failed', message: msg });
    } finally {
      setLoading(false);
    }
  }, [debouncedName, activeCategory, showToast]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError('Please select a PDF, DOCX, or TXT file.');
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      const created = await uploadKnowledgeDocumentApi(selectedFile, uploadCategory, uploadTitle);
      showToast({
        type: 'success',
        title: 'Document Indexed',
        message: `'${created.filename || created.title}' processed (${created.page_count} page(s), ${created.chunk_count} chunk(s)).`,
      });
      setUploadOpen(false);
      setSelectedFile(null);
      setUploadTitle('');
      setUploadCategory('general');
      await fetchDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Document upload failed';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleInspect = async (doc: KnowledgeDocument) => {
    setDetailLoading(true);
    setDetailDoc({ ...doc, content_preview: '' });
    try {
      const full = await getKnowledgeDocumentApi(doc.id);
      setDetailDoc(full);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load document details';
      showToast({ type: 'error', title: 'Error', message: msg });
      setDetailDoc(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleReprocess = async (doc: KnowledgeDocument) => {
    setReprocessingId(doc.id);
    try {
      const updated = await reprocessKnowledgeDocumentApi(doc.id);
      showToast({
        type: 'success',
        title: 'Reprocessing Complete',
        message: `'${updated.filename || updated.title}' re-indexed (${updated.chunk_count} chunks).`,
      });
      await fetchDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reprocessing failed';
      showToast({ type: 'error', title: 'Reprocess Failed', message: msg });
    } finally {
      setReprocessingId(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await deleteKnowledgeDocumentApi(deleteTarget.id);
      showToast({
        type: 'success',
        title: 'Document Deleted',
        message: res.message,
      });
      setDeleteTarget(null);
      await fetchDocuments();
      if (semanticResults) {
        setSemanticResults((prev) =>
          prev ? prev.filter((r) => r.document_id !== res.id) : null
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Delete failed';
      showToast({ type: 'error', title: 'Delete Failed', message: msg });
    } finally {
      setDeleting(false);
    }
  };

  const handleSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = semanticQuery.trim();
    if (!q) {
      setSemanticResults(null);
      return;
    }
    setSearchingVector(true);
    try {
      const res = await semanticSearchKnowledgeApi({
        q,
        top_k: 6,
        category: activeCategory,
      });
      setSemanticResults(res.results);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Semantic search failed';
      showToast({ type: 'error', title: 'Search Error', message: msg });
    } finally {
      setSearchingVector(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-[#087E8B] uppercase tracking-wider mb-1">
            <BookOpen className="w-3.5 h-3.5" />
            <span>RAG Knowledge Base & Vector Store</span>
          </div>
          <h1 className="text-2xl font-bold text-[#172B3A] tracking-tight">Enterprise Runbooks & Documents</h1>
          <p className="text-xs text-[#526773] mt-1">
            Indexed PDF, DOCX, and TXT documentation chunked and embedded in ChromaDB (all-MiniLM-L6-v2).
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={fetchDocuments}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-white hover:bg-[#EFF3F1] text-[#172B3A] border border-[#DCE4E3] text-xs font-semibold shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#087E8B]' : 'text-[#718096]'}`} />
            <span>Refresh</span>
          </button>

          {isAdmin && (
            <button
              onClick={() => {
                setUploadError(null);
                setUploadOpen(true);
              }}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-[#087E8B] hover:bg-[#075C66] text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Document</span>
            </button>
          )}
        </div>
      </div>

      {/* Semantic Vector Search Box */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#087E8B]" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#172B3A]">
              Semantic Vector Search
            </h2>
          </div>
          {semanticResults !== null && (
            <button
              onClick={() => {
                setSemanticQuery('');
                setSemanticResults(null);
              }}
              className="text-xs font-semibold text-[#526773] hover:text-[#172B3A]"
            >
              Clear vector results
            </button>
          )}
        </div>

        <form onSubmit={handleSemanticSearch} className="flex flex-col sm:flex-row gap-2.5">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[#718096] absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={semanticQuery}
              onChange={(e) => setSemanticQuery(e.target.value)}
              placeholder="Ask a technical question or describe a symptom to retrieve matching chunks from ChromaDB..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#DCE4E3] rounded-lg text-xs text-[#172B3A] placeholder-[#718096] focus:outline-none focus:ring-2 focus:ring-[#087E8B] focus:border-[#087E8B]"
            />
          </div>
          <button
            type="submit"
            disabled={searchingVector || !semanticQuery.trim()}
            className="px-4 py-2 bg-[#087E8B] hover:bg-[#075C66] disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs shrink-0 transition-colors"
          >
            {searchingVector ? 'Searching Vectors...' : 'Search Knowledge'}
          </button>
        </form>

        {semanticResults !== null && (
          <div className="pt-2 space-y-2.5">
            {semanticResults.length === 0 ? (
              <div className="text-xs text-[#526773] bg-[#EFF3F1] border border-[#DCE4E3] rounded-xl p-4 text-center">
                No matching chunks found in ChromaDB. Upload relevant documentation first.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {semanticResults.map((hit) => (
                  <div
                    key={hit.chunk_id}
                    className="p-4 rounded-xl border border-blue-100 bg-blue-50/30 space-y-1.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-900">{hit.title}</span>
                        <span className="text-[11px] font-mono text-slate-500">
                          ({hit.source_filename})
                        </span>
                        <span className="px-2 py-0.5 rounded bg-white border border-slate-200 text-[10px] font-semibold text-slate-600">
                          Page {hit.page_number}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-[11px] font-bold">
                        {(hit.score * 100).toFixed(1)}% match
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                      {hit.text}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Document Library Filter & Search */}
      <div className="bg-white rounded-2xl border border-[#DCE4E3] p-4 shadow-xs space-y-4">
        <SearchBar
          value={nameSearch}
          onChange={setNameSearch}
          placeholder="Filter documents by filename or title..."
        />

        <div className="flex items-center space-x-2 overflow-x-auto pb-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setActiveCategory(cat.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 transition-colors ${
                activeCategory === cat.value
                  ? 'bg-[#087E8B] text-white shadow-xs'
                  : 'bg-[#EFF3F1] text-[#172B3A] hover:bg-[#DCEFF0]'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Document List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-36 w-full rounded-xl" />
          <Skeleton className="h-36 w-full rounded-xl" />
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          title="No knowledge documents found"
          description={
            debouncedName || activeCategory !== 'all'
              ? 'No indexed documents match your current search or category filter.'
              : 'Upload PDF, DOCX, or TXT runbooks to populate the RAG vector knowledge base.'
          }
          actionText={isAdmin && !debouncedName && activeCategory === 'all' ? 'Upload First Document' : undefined}
          onAction={isAdmin ? () => setUploadOpen(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="bg-white rounded-xl border border-[#DCE4E3] p-5 shadow-xs hover:border-[#087E8B] transition-all flex flex-col justify-between gap-4"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-2 rounded-lg bg-[#DCEFF0] text-[#087E8B] shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-[#172B3A] truncate">{doc.title}</h3>
                      <div className="text-[11px] font-mono text-[#718096] truncate">
                        {doc.filename || `doc_${doc.id}.${doc.file_type}`}
                      </div>
                    </div>
                  </div>
                  <StatusPill status={doc.status} />
                </div>

                {doc.error_message && (
                  <div className="text-[11px] text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-2.5 py-1.5">
                    {doc.error_message}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-600">
                  <span className="px-2 py-0.5 rounded bg-slate-100 font-semibold uppercase">
                    {doc.file_type}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-100 capitalize">
                    {doc.category.replace('_', ' ')}
                  </span>
                  <span>{formatBytes(doc.file_size)}</span>
                  <span>&bull;</span>
                  <span>{doc.page_count} page{doc.page_count === 1 ? '' : 's'}</span>
                  <span>&bull;</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-blue-700">
                    <Layers className="w-3 h-3" /> {doc.chunk_count} chunk{doc.chunk_count === 1 ? '' : 's'}
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2 text-xs">
                <span className="text-[11px] text-slate-400">
                  Added {new Date(doc.created_at).toLocaleDateString()}
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleInspect(doc)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View</span>
                  </button>

                  {isAdmin && (
                    <>
                      <button
                        onClick={() => handleReprocess(doc)}
                        disabled={reprocessingId === doc.id}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:opacity-50 transition-colors"
                        title="Reprocess document chunks & embeddings"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${reprocessingId === doc.id ? 'animate-spin' : ''}`} />
                        <span>{reprocessingId === doc.id ? 'Reprocessing...' : 'Reprocess'}</span>
                      </button>

                      <button
                        onClick={() => setDeleteTarget(doc)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        title="Delete document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal (Admin) */}
      <Modal
        isOpen={uploadOpen}
        onClose={() => !uploading && setUploadOpen(false)}
        title="Upload Knowledge Document"
        description="Supported formats: PDF, DOCX, TXT (max 15 MB). Automatically chunked and embedded into ChromaDB."
        footer={
          <>
            <button
              type="button"
              disabled={uploading}
              onClick={() => setUploadOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="upload-doc-form"
              disabled={uploading}
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 rounded-lg shadow-xs"
            >
              {uploading ? 'Processing & Embedding...' : 'Upload & Index'}
            </button>
          </>
        }
      >
        <form id="upload-doc-form" onSubmit={handleUpload} className="space-y-4 text-xs">
          {uploadError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700">
              {uploadError}
            </div>
          )}

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Select File (.pdf, .docx, .txt)</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setSelectedFile(file);
                setUploadError(null);
              }}
              className="w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 border border-slate-200 rounded-lg p-1.5"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Document Title (optional)</label>
            <input
              type="text"
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
              placeholder="Defaults to filename if left blank"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Category</label>
            <select
              value={uploadCategory}
              onChange={(e) => setUploadCategory(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white"
            >
              {CATEGORIES.filter((c) => c.value !== 'all').map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </form>
      </Modal>

      {/* Document Details Modal */}
      <Modal
        isOpen={!!detailDoc}
        onClose={() => setDetailDoc(null)}
        title={detailDoc?.title || 'Document Details'}
        description={
          detailDoc
            ? `${detailDoc.filename || ''} • ${detailDoc.page_count} page(s) • ${detailDoc.chunk_count} vector chunk(s)`
            : ''
        }
        maxWidth="2xl"
        footer={
          <button
            onClick={() => setDetailDoc(null)}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-xs"
          >
            Close
          </button>
        }
      >
        {detailLoading ? (
          <div className="space-y-3 py-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : (
          detailDoc && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div>
                  <span className="text-slate-400 block text-[11px]">Status</span>
                  <StatusPill status={detailDoc.status} />
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Size / Format</span>
                  <span className="font-semibold text-slate-800 uppercase">
                    {detailDoc.file_type} • {formatBytes(detailDoc.file_size)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Pages / Chunks</span>
                  <span className="font-semibold text-slate-800">
                    {detailDoc.page_count}p / {detailDoc.chunk_count}c
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Uploaded By</span>
                  <span className="font-semibold text-slate-800">{detailDoc.created_by || 'Admin'}</span>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-slate-900 mb-1.5">Extracted Text Preview</h4>
                <div className="max-h-72 overflow-y-auto p-4 bg-slate-50 border border-slate-200 rounded-xl font-mono text-[11px] text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {detailDoc.content_preview || 'No preview available.'}
                </div>
              </div>
            </div>
          )
        )}
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmationDialog
        isOpen={!!deleteTarget}
        onClose={() => !deleting && setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Knowledge Document?"
        message={`This will permanently delete '${deleteTarget?.filename || deleteTarget?.title}' from SQLite and remove all ${deleteTarget?.chunk_count ?? 0} associated embedding chunks from ChromaDB.`}
        confirmText="Delete Document"
        isDestructive
        confirmLoading={deleting}
      />
    </div>
  );
};
