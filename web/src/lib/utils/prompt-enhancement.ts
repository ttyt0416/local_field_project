import { apiJson } from './api';

type ImagePromptFamily = 'anima' | 'illustrious' | 'moss' | 'qwen_image_2_1';

export async function enhanceImagePrompt(modelFamily: ImagePromptFamily, prompt: string): Promise<string> {
	const result = await apiJson<{ improved_prompt: { contents: string } }>('generation/image/enhance-prompt', {
		method: 'POST',
		timeout: 600_000,
		json: { model_family: modelFamily, prompt: prompt.trim() }
	});
	const improved = result.improved_prompt.contents.trim();
	if (!improved) throw new Error('개선된 프롬프트가 비어 있습니다.');
	return improved;
}
