<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	
	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');
	
	export let agent: any;
	export let selected: boolean = false;
	
	function handleToggle() {
		dispatch('toggle');
	}
	
	function getModelDisplayName(modelId: string) {
		const modelNames: Record<string, string> = {
			'jiutian-lan': '九天基础语言大模型',
			'jiutian-med': '九天医疗大模型',
			'jiutian-cus': '九天客服大模型',
			'jiutian-gov': '九天海算政务大模型'
		};
		return modelNames[modelId] || modelId;
	}
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
	class="relative p-3 rounded-lg border-2 cursor-pointer transition-all duration-200 {selected
		? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
		: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
	on:click={handleToggle}
>
	<!-- Selection indicator -->
	{#if selected}
		<div class="absolute top-2 right-2">
			<div class="w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
				<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
				</svg>
			</div>
		</div>
	{/if}
	
	<!-- Agent info -->
	<div class="pr-6">
		<h4 class="font-medium text-gray-900 dark:text-white truncate">
			{agent.name}
		</h4>
		
		<div class="mt-1 space-y-1">
			<!-- Model info -->
			{#if agent.config?.modelId}
				<div class="text-xs text-gray-600 dark:text-gray-400">
					<span class="font-medium">{$i18n.t('Model')}:</span>
					{getModelDisplayName(agent.config.modelId)}
				</div>
			{/if}
			
			<!-- Knowledge assistant -->
			{#if agent.config?.klAssistId}
				<div class="text-xs text-gray-600 dark:text-gray-400">
					<span class="font-medium">{$i18n.t('Knowledge Assistant')}:</span>
					{agent.config.klAssistId}
				</div>
			{/if}
			
			<!-- API host -->
			<div class="text-xs text-gray-500 dark:text-gray-500 truncate">
				{agent.api_host}
			</div>
		</div>
		
		<!-- Status -->
		<div class="mt-2 flex items-center gap-1">
			<div class="w-2 h-2 rounded-full {agent.enabled ? 'bg-green-500' : 'bg-red-500'}"></div>
			<span class="text-xs text-gray-600 dark:text-gray-400">
				{agent.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}
			</span>
		</div>
		
		<!-- Owner info -->
		{#if agent.owner}
			<div class="mt-1 text-xs text-gray-500 dark:text-gray-500">
				{$i18n.t('Owner')}: {agent.owner.name}
			</div>
		{/if}
	</div>
</div>