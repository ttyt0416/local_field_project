<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { AudioLines, Music, Sparkles } from '@lucide/svelte';
	import Layout from '../../../../components/layouts/layout.svelte';
	import LoadingSpinner from '../../../../components/loadings/loading-spinner.svelte';
	import PrimaryButton from '../../../../components/buttons/primary-button.svelte';
	import Toast from '../../../../components/feedback/toast.svelte';
	import Typography from '../../../../components/typography/typography.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { apiJson } from '$lib/utils/api';

	type MusicGenerationOptions = {
		model: 'MiniMax-Music3';
		service_available: boolean;
		detail: string;
	};

	const textareaClass = 'w-full resize-y rounded-lg border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20';

	let ready = $state(false);
	let optionsLoading = $state(true);
	let model = $state<MusicGenerationOptions['model']>('MiniMax-Music3');
	let serviceAvailable = $state(false);
	let serviceDetail = $state('');
	let description = $state('');
	let lyrics = $state('');
	let error = $state('');

	onMount(() => {
		void initialize();
	});

	async function initialize() {
		await authStore.initialize();
		if (!authStore.isAuthenticated) {
			await goto('/login');
			return;
		}
		try {
			const options = await apiJson<MusicGenerationOptions>('generation/music/options');
			model = options.model;
			serviceAvailable = options.service_available;
			serviceDetail = options.detail;
		} catch (reason) {
			error = reason instanceof Error ? reason.message : '음악 생성 설정을 불러오지 못했습니다.';
		} finally {
			optionsLoading = false;
			ready = true;
		}
	}
</script>

<svelte:head>
	<title>음악 생성 · Local Field</title>
	<meta name="description" content="MiniMax Music 3 local music generation 준비 화면" />
</svelte:head>

{#if !ready}
	<div class="flex min-h-screen items-center justify-center bg-background"><LoadingSpinner size="lg" label="음악 생성 페이지를 불러오는 중" /></div>
{:else}
	<Layout>
		<div class="space-y-6">
			<Typography as="h1" variant="display">음악 생성</Typography>

			<div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="music-result-title">
					<div class="flex items-center justify-between gap-4"><div id="music-result-title"><Typography as="h2" variant="h2">생성 결과</Typography></div><AudioLines size={22} class="text-primary" strokeWidth={1.8} /></div>
					<div class="mt-6 flex min-h-[24rem] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-muted/30 px-6 text-center sm:min-h-[34rem]">
						<div class="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Music size={26} strokeWidth={1.7} /></div>
						{#if optionsLoading}<LoadingSpinner size="md" label="MiniMax Music 3 설정 확인 중" />{:else}<p class="text-sm font-medium">아직 생성된 음악이 없습니다.</p><p class="max-w-sm text-xs leading-5 text-muted-foreground">{serviceDetail || 'MiniMax Music 3 local service를 연결하면 생성 결과가 여기에 표시됩니다.'}</p>{/if}
					</div>
				</section>

				<section class="rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6" aria-labelledby="music-settings-title">
					<div id="music-settings-title"><Typography as="h2" variant="h2">음악 생성 설정</Typography></div>
					<div class="mt-5 space-y-5 pb-24 sm:pb-0">
						<div class="rounded-xl border border-border bg-muted/30 px-3 py-3"><span class="block text-xs font-medium text-muted-foreground">MODEL</span><span class="mt-1 block text-sm font-semibold text-foreground">{model}</span></div>
						<label class="block space-y-2" for="music-description"><span class="text-sm font-medium">음악 설명</span><textarea id="music-description" bind:value={description} rows="6" maxlength="5000" class={textareaClass} placeholder="장르, 분위기, 보컬, 악기, 곡 전개를 설명해 주세요."></textarea><span class="block text-right text-xs text-muted-foreground">{description.length.toLocaleString('ko-KR')} / 5,000</span></label>
						<label class="block space-y-2" for="music-lyrics"><span class="text-sm font-medium">가사</span><textarea id="music-lyrics" bind:value={lyrics} rows="10" maxlength="5000" class={textareaClass} placeholder={'[Verse]\n가사를 입력해 주세요.\n\n[Chorus]\n반복할 후렴을 입력해 주세요.'}></textarea><span class="block text-xs leading-5 text-muted-foreground">[Verse], [Chorus], [Bridge], [Instrumental] section tag를 줄 단위로 사용할 수 있습니다.</span><span class="block text-right text-xs text-muted-foreground">{lyrics.length.toLocaleString('ko-KR')} / 5,000</span></label>
						<!-- ponytail: no job is created until the local Music 3 service exists; add the durable submit and worker path together. -->
						<div class="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-lg sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:shadow-none"><PrimaryButton deactive={!serviceAvailable} disabled={!description.trim() || !lyrics.trim()} class="w-full"><Sparkles size={17} strokeWidth={1.9} /><span>{serviceAvailable ? '음악 생성' : 'MiniMax Music 3 연결 대기 중'}</span></PrimaryButton></div>
					</div>
				</section>
			</div>
		</div>
	</Layout>

	{#if error}<div class="fixed right-4 top-4 z-50"><Toast state="negative" title="음악 생성 설정을 불러오지 못했습니다" message={error} onclose={() => (error = '')} /></div>{/if}
{/if}
