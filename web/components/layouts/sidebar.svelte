<script lang="ts">
	import {
		Archive,
		Bookmark,
		Heart,
		ImagePlus,
		Sparkles,
		X
	} from '@lucide/svelte';
	import IconOutlinedButton from '../buttons/icon-outlined-button.svelte';
	import { APP_NAME } from '../../src/lib/configs/constants';

	type Props = {
		open?: boolean;
	};

	let { open = $bindable(false) }: Props = $props();

	function close() {
		open = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			close();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<button
		type="button"
		class="fixed inset-0 z-40 bg-black/60 lg:hidden"
		aria-label="메뉴 닫기"
		onclick={close}
	></button>
{/if}

<aside
	class={`fixed bottom-0 left-0 z-50 flex h-[min(78vh,34rem)] w-full flex-col rounded-t-3xl border border-border bg-card shadow-2xl transition-transform duration-300 lg:inset-y-0 lg:h-auto lg:w-72 lg:rounded-none lg:border-y-0 lg:border-l-0 lg:border-r ${open ? 'translate-y-0' : 'translate-y-full'} lg:translate-y-0`}
	aria-label="주요 메뉴"
>
	<div class="flex h-16 items-center justify-between border-b border-border px-5">
		<a href="/vault" class="flex items-center gap-3" onclick={close}>
			<span class="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
				<Sparkles size={18} strokeWidth={2} />
			</span>
			<span class="text-sm font-semibold tracking-tight">{APP_NAME}</span>
		</a>
		<IconOutlinedButton ariaLabel="메뉴 닫기" class="lg:hidden" onclick={close}>
			<X size={18} />
		</IconOutlinedButton>
	</div>

	<nav class="flex-1 space-y-1 overflow-y-auto px-3 py-5" aria-label="애플리케이션 메뉴">
		<a
			href="/vault"
			class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
			onclick={close}
		>
			<Archive size={18} strokeWidth={1.8} />
			<span>보관함</span>
		</a>
		<a
			href="/vault?favorites=true"
			class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
			onclick={close}
		>
			<Heart size={18} strokeWidth={1.8} />
			<span>즐겨찾기</span>
		</a>
		<a
			href="/generate/image"
			class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
			onclick={close}
		>
			<ImagePlus size={18} strokeWidth={1.8} />
			<span>이미지 생성</span>
		</a>
		<a
			href="/presets"
			class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
			onclick={close}
		>
			<Bookmark size={18} strokeWidth={1.8} />
			<span>프리셋 관리</span>
		</a>
	</nav>

</aside>
