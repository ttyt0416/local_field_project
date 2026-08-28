import { browser } from '$app/environment';
import { SERVER_URL } from '$lib/configs/constants';
import { streamSse } from '$lib/utils/api';

export type GenerationJobKind = 'image' | 'video';
export type GenerationJobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type GenerationJob = {
	key: string;
	kind: GenerationJobKind;
	promptId: string;
	clientId: string;
	generationId: string;
	mode?: 'i2v' | 'fl2v' | 'r2v';
	status: GenerationJobStatus;
	progress: number;
	queuePosition: number | null;
	imageUrl?: string;
	videoUrl?: string;
	error?: string;
	createdAt: number;
};

type PersistedJob = Pick<
	GenerationJob,
	| 'key'
	| 'kind'
	| 'promptId'
	| 'clientId'
	| 'generationId'
	| 'mode'
	| 'status'
	| 'progress'
	| 'queuePosition'
	| 'imageUrl'
	| 'videoUrl'
	| 'error'
	| 'createdAt'
>;

const STORAGE_KEY = 'local-field.generation-jobs';
const terminalStatuses = new Set<GenerationJobStatus>(['completed', 'failed']);

function isTerminal(status: GenerationJobStatus) {
	return terminalStatuses.has(status);
}

function wait(milliseconds: number) {
	return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

class GenerationJobStore {
	jobs = $state<Record<string, GenerationJob>>({});
	private streams = new Map<string, AbortController>();
	private waiters = new Map<string, Set<() => void>>();
	private initialized = false;

	get list() {
		return Object.values(this.jobs).sort((left, right) => right.createdAt - left.createdAt);
	}

	async initialize() {
		if (!browser || this.initialized) return;
		this.initialized = true;
		try {
			const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as PersistedJob[];
			for (const job of stored.slice(0, 20)) {
				if (!job?.key || !job.promptId || !job.clientId || !job.generationId) continue;
				this.jobs[job.key] = { ...job };
			}
		} catch {
			localStorage.removeItem(STORAGE_KEY);
		}
		for (const job of this.list) {
			if (!isTerminal(job.status)) void this.connect(job.key);
		}
	}

	track(input: Omit<GenerationJob, 'key' | 'status' | 'progress' | 'queuePosition' | 'createdAt'>) {
		const key = `${input.kind}:${input.promptId}`;
		this.jobs[key] = {
			...input,
			key,
			status: 'queued',
			progress: 0,
			queuePosition: null,
			createdAt: Date.now()
		};
		this.persist();
		void this.connect(key);
		return key;
	}

	latest(kind: GenerationJobKind) {
		return this.list.find((job) => job.kind === kind) ?? null;
	}

	waitForTerminal(key: string) {
		const job = this.jobs[key];
		if (!job || isTerminal(job.status)) return Promise.resolve();
		return new Promise<void>((resolve) => {
			const callbacks = this.waiters.get(key) ?? new Set<() => void>();
			callbacks.add(resolve);
			this.waiters.set(key, callbacks);
		});
	}

	dismiss(key: string) {
		delete this.jobs[key];
		this.persist();
	}

	private async connect(key: string) {
		if (!browser || this.streams.has(key)) return;
		const controller = new AbortController();
		this.streams.set(key, controller);
		let delay = 500;
		try {
			while (!controller.signal.aborted) {
				const job = this.jobs[key];
				if (!job || isTerminal(job.status)) return;
				try {
					await streamSse(this.path(job), (event) => this.applyEvent(key, event.event, event.data), {
						signal: controller.signal
					});
					delay = 500;
				} catch (error) {
					if (controller.signal.aborted) return;
					this.update(key, { error: error instanceof Error ? error.message : 'SSE 연결이 끊어졌습니다.' });
				}
				if (isTerminal(this.jobs[key]?.status ?? 'failed')) return;
				await wait(delay);
				delay = Math.min(delay * 2, 10_000);
			}
		} finally {
			this.streams.delete(key);
		}
	}

	private path(job: GenerationJob) {
		if (job.kind === 'image') {
			return `generation/image/${job.promptId}/events?client_id=${encodeURIComponent(job.clientId)}`;
		}
		return `generation/video/${job.mode}/${job.promptId}/events?client_id=${encodeURIComponent(job.clientId)}`;
	}

	private applyEvent(key: string, eventName: string, rawData: string) {
		let data: Record<string, unknown> = {};
		try {
			data = JSON.parse(rawData) as Record<string, unknown>;
		} catch {
			return;
		}
		const status = this.status(data.status ?? eventName);
		const changes: Partial<GenerationJob> = {};
		if (status) changes.status = status;
		if (typeof data.progress === 'number') changes.progress = data.progress;
		if ('queue_position' in data) changes.queuePosition = typeof data.queue_position === 'number' ? data.queue_position : null;
		if (eventName === 'completed') {
			const image = Array.isArray(data.images) ? (data.images[0] as { url?: unknown } | undefined) : undefined;
			const video = data.video as { url?: unknown } | null | undefined;
			if (typeof image?.url === 'string') changes.imageUrl = new URL(image.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
			if (typeof video?.url === 'string') changes.videoUrl = new URL(video.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
			changes.error = undefined;
		}
		if (eventName === 'failed') changes.error = typeof data.message === 'string' ? data.message : '생성에 실패했습니다.';
		if (eventName === 'error') changes.error = typeof data.message === 'string' ? data.message : 'SSE 연결이 끊어졌습니다.';
		this.update(key, changes);
	}

	private status(value: unknown): GenerationJobStatus | undefined {
		return value === 'queued' || value === 'processing' || value === 'completed' || value === 'failed' ? value : undefined;
	}

	private update(key: string, changes: Partial<GenerationJob>) {
		const current = this.jobs[key];
		if (!current) return;
		this.jobs[key] = { ...current, ...changes };
		this.persist();
		if (isTerminal(this.jobs[key].status)) {
			for (const resolve of this.waiters.get(key) ?? []) resolve();
			this.waiters.delete(key);
		}
	}

	private persist() {
		if (!browser) return;
		const jobs: PersistedJob[] = this.list.slice(0, 20).map(({ key, kind, promptId, clientId, generationId, mode, status, progress, queuePosition, imageUrl, videoUrl, error, createdAt }) => ({
			key,
			kind,
			promptId,
			clientId,
			generationId,
			mode,
			status,
			progress,
			queuePosition,
			imageUrl,
			videoUrl,
			error,
			createdAt
		}));
		localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
	}
}

export const generationJobStore = new GenerationJobStore();
