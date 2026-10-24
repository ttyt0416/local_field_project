import type { ModelType } from './model-storage';

export type DownloadProvider = 'civitai' | 'hugging_face';
export type DownloadJob = {
	id: string;
	provider: DownloadProvider;
	version_id: number | null;
	source_repo: string | null;
	source_revision: string | null;
	source_filename: string | null;
	model_type: ModelType;
	subfolder: string;
	filename: string;
	status: 'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled';
	downloaded_bytes: number;
	total_bytes: number | null;
	created_at: string;
	error_message: string | null;
};
