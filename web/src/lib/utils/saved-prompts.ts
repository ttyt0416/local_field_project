export type PromptKind = 'image' | 'video';
export type SavedPrompt = { id: string; kind: PromptKind; name: string; content: string; created_at: string; updated_at: string };

export function appendPrompt(current: string, saved: string, kind: PromptKind): string {
	const addition = saved.trim();
	if (!addition) return current;
	const separator = !current.trim() || /\s$/.test(current) ? '' : kind === 'video' ? '\n' : /,$/.test(current) ? ' ' : ', ';
	const result = current.trim() ? `${current}${separator}${addition}` : addition;
	if (result.length > 5000) throw new Error('추가한 프롬프트가 5,000자를 초과합니다. 내용을 줄인 뒤 다시 불러와 주세요.');
	return result;
}
