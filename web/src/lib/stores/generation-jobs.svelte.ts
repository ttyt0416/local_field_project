import { browser } from '$app/environment';
import { SERVER_URL } from '$lib/configs/constants';
import { apiJson, streamSse } from '$lib/utils/api';

export type GenerationJobKind = 'image' | 'video' | '3d';
export type GenerationJobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type GenerationJob = {
	key: string;
	kind: GenerationJobKind;
	promptId: string;
	clientId: string;
	generationId: string;
	mode?: 'i2v' | 'fl2v' | 'r2v';
	preset?: 'preview' | 'standard' | 'high';
	seed?: number | null;
	status: GenerationJobStatus;
	progress: number;
	queuePosition: number | null;
	elapsedSeconds: number;
	stage?: string;
	imageUrl?: string;
	videoUrl?: string;
	modelUrl?: string;
	modelFilename?: string;
	modelSizeBytes?: number | null;
	error?: string;
	createdAt: number;
};

type ActiveGenerationResponse = {
	kind: GenerationJobKind;
	prompt_id: string;
	client_id: string;
	generation_id: string;
	mode?: 'i2v' | 'fl2v' | 'r2v' | null;
	preset?: 'preview' | 'standard' | 'high' | null;
	seed?: number | null;
	status: 'queued' | 'processing';
	progress: number;
	queue_position?: number | null;
	stage?: string | null;
	created_at: string;
	elapsed_seconds: number;
};

const terminalStatuses = new Set<GenerationJobStatus>(['completed', 'failed', 'cancelled']);

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
	private initialization?: Promise<void>;
	private clock?: ReturnType<typeof setInterval>;
	now = $state(Date.now());

	get list() {
		return Object.values(this.jobs).sort((left, right) => right.createdAt - left.createdAt);
	}

	async initialize() {
		if (!browser || this.initialized) return;
		this.startClock();
		if (this.initialization) return this.initialization;
		this.initialization = this.restoreActiveJobs();
		return this.initialization;
	}

	track(input: Omit<GenerationJob, 'key' | 'status' | 'progress' | 'queuePosition' | 'createdAt' | 'elapsedSeconds'> & { status?: GenerationJobStatus; progress?: number; queuePosition?: number | null; createdAt?: number; elapsedSeconds?: number }) {
		this.startClock();
		const key = `${input.kind}:${input.promptId}`;
		this.jobs[key] = {
			...input,
			key,
			status: input.status ?? 'queued',
			progress: input.progress ?? 0,
			queuePosition: input.queuePosition ?? null,
			createdAt: input.createdAt ?? Date.now(),
			elapsedSeconds: input.elapsedSeconds ?? 0
		};
		void this.connect(key);
		return key;
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

	private async restoreActiveJobs() {
		try {
			const activeJobs = await apiJson<ActiveGenerationResponse[]>('generation/active');
			for (const active of activeJobs) {
				const key = `${active.kind}:${active.prompt_id}`;
				this.jobs[key] = {
					key,
					kind: active.kind,
					promptId: active.prompt_id,
					clientId: active.client_id,
					generationId: active.generation_id,
					mode: active.mode ?? undefined,
					preset: active.preset ?? undefined,
					seed: active.seed,
					status: active.status,
					progress: active.progress,
					queuePosition: active.queue_position ?? null,
					stage: active.stage ?? undefined,
					createdAt: Date.parse(active.created_at) || Date.now(),
					elapsedSeconds: active.elapsed_seconds
				};
				void this.connect(key);
			}
		} catch {
			// Authentication and page guards handle user-visible request errors.
		} finally {
			this.initialized = true;
		}
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
		if (job.kind === '3d') {
			return `generation/3d/${job.promptId}/events?client_id=${encodeURIComponent(job.clientId)}`;
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
		if (typeof data.elapsed_seconds === 'number') changes.elapsedSeconds = data.elapsed_seconds;
		if (typeof data.stage === 'string') changes.stage = data.stage;
		if (typeof data.created_at === 'string') changes.createdAt = Date.parse(data.created_at) || changes.createdAt;
		if ('queue_position' in data) changes.queuePosition = typeof data.queue_position === 'number' ? data.queue_position : null;
		if (eventName === 'completed' || status === 'completed') {
			const image = Array.isArray(data.images) ? (data.images[0] as { url?: unknown } | undefined) : undefined;
			const video = data.video as { url?: unknown } | null | undefined;
			const model = data.model as { url?: unknown; filename?: unknown; size_bytes?: unknown } | null | undefined;
			if (typeof image?.url === 'string') changes.imageUrl = new URL(image.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
			if (typeof video?.url === 'string') changes.videoUrl = new URL(video.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
			if (typeof model?.url === 'string') changes.modelUrl = new URL(model.url, `${SERVER_URL.replace(/\/+$/, '')}/`).toString();
			if (typeof model?.filename === 'string') changes.modelFilename = model.filename;
			if (typeof model?.size_bytes === 'number' || model?.size_bytes === null) changes.modelSizeBytes = model.size_bytes;
			changes.error = undefined;
		}
		if (eventName === 'failed') changes.error = typeof data.message === 'string' ? data.message : '생성에 실패했습니다.';
		if (eventName === 'error') changes.error = typeof data.message === 'string' ? data.message : 'SSE 연결이 끊어졌습니다.';
		this.update(key, changes);
	}

	private status(value: unknown): GenerationJobStatus | undefined {
		return value === 'queued' || value === 'processing' || value === 'completed' || value === 'failed' || value === 'cancelled' ? value : undefined;
	}

	async cancel(key: string) {
		const job = this.jobs[key];
		if (!job || isTerminal(job.status)) return;
		const path = job.kind === 'image'
			? `generation/image/${job.promptId}/cancel`
			: job.kind === '3d'
				? `generation/3d/${job.promptId}/cancel`
				: `generation/video/${job.mode}/${job.promptId}/cancel`;
		await apiJson(path, { method: 'POST' });
		this.update(key, { status: 'cancelled', queuePosition: null, error: undefined });
		this.streams.get(key)?.abort();
	}

	private update(key: string, changes: Partial<GenerationJob>) {
		const current = this.jobs[key];
		if (!current) return;
		this.jobs[key] = { ...current, ...changes };
		if (isTerminal(this.jobs[key].status)) {
			for (const resolve of this.waiters.get(key) ?? []) resolve();
			this.waiters.delete(key);
		}
	}

	private startClock() {
		if (!browser || this.clock) return;
		this.clock = setInterval(() => (this.now = Date.now()), 1000);
	}

	elapsedSeconds(job: GenerationJob, now = this.now) {
		if (isTerminal(job.status)) return job.elapsedSeconds;
		return Math.max(job.elapsedSeconds, (now - job.createdAt) / 1000);
	}
}

export const generationJobStore = new GenerationJobStore();
