export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface KnowledgeDocument {
  id: number;
  title: string;
  filename: string | null;
  file_type: string;
  file_size: number;
  file_hash: string | null;
  category: string;
  status: DocumentStatus;
  error_message: string | null;
  page_count: number;
  chunk_count: number;
  created_by_id: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  content_preview: string;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocument[];
  total: number;
}

export interface KnowledgeDeleteResponse {
  id: number;
  filename: string | null;
  deleted_chunks: number;
  message: string;
}

export interface SemanticSearchResultItem {
  chunk_id: string;
  document_id: number;
  source_filename: string;
  title: string;
  category: string;
  page_number: number;
  chunk_index: number;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SemanticSearchResponse {
  query: string;
  total: number;
  results: SemanticSearchResultItem[];
}
