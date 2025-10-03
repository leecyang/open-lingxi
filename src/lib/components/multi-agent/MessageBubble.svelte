<script lang="ts">
	import { getContext } from 'svelte';
	import { marked } from 'marked';
	
	const i18n = getContext('i18n');
	
	export let message: any;
	
	function formatTimestamp(timestamp: number) {
		return new Date(timestamp).toLocaleTimeString();
	}
	
	function getMessageTypeColor(type: string) {
		switch (type) {
			case 'user':
				return 'bg-blue-500 text-white';
			case 'complete':
				return 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white';
			case 'streaming':
				return 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white border-l-4 border-blue-500';
			case 'error':
				return 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-200 border-l-4 border-red-500';
			case 'status':
				return 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-900 dark:text-yellow-200 border-l-4 border-yellow-500';
			case 'start':
			case 'complete':
				return 'bg-green-50 dark:bg-green-900/20 text-green-900 dark:text-green-200 border-l-4 border-green-500';
			default:
				return 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white';
		}
	}
	
	function getAgentIcon(agentId: string) {
		if (agentId === 'user') {
			return '👤';
		} else if (agentId === 'system') {
			return '⚙️';
		} else {
			return '🤖';
		}
	}
	
	function renderMarkdown(content: string) {
		try {
			return marked(content, { breaks: true, gfm: true });
		} catch (error) {
			return content;
		}
	}
</script>

<div class="flex gap-3 {message.agent_id === 'user' ? 'flex-row-reverse' : ''}">
	<!-- Avatar -->
	<div class="flex-shrink-0">
		<div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-sm">
			{getAgentIcon(message.agent_id)}
		</div>
	</div>
	
	<!-- Message content -->
	<div class="flex-1 max-w-3xl">
		<!-- Header -->
		<div class="flex items-center gap-2 mb-1 {message.agent_id === 'user' ? 'flex-row-reverse' : ''}">
			<span class="text-sm font-medium text-gray-900 dark:text-white">
				{message.agent_name}
			</span>
			
			<span class="text-xs text-gray-500 dark:text-gray-400">
				{formatTimestamp(message.timestamp)}
			</span>
			
			{#if message.type === 'streaming'}
				<div class="flex items-center gap-1">
					<div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
					<span class="text-xs text-blue-600 dark:text-blue-400">
						{$i18n.t('Typing...')}
					</span>
				</div>
			{/if}
		</div>
		
		<!-- Message bubble -->
		<div class="rounded-lg p-3 {getMessageTypeColor(message.type)} {message.agent_id === 'user' ? 'ml-auto' : ''}">
			<!-- Content -->
			<div class="prose prose-sm max-w-none dark:prose-invert">
				{@html renderMarkdown(message.content)}
			</div>
			
			<!-- System message details -->
			{#if message.agent_id === 'system' && message.agent_names}
				<div class="mt-2 text-xs opacity-75">
					{$i18n.t('Agents')}: {message.agent_names.join(', ')}
				</div>
			{/if}
			
			<!-- Usage information -->
			{#if message.usage}
				<div class="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 text-xs opacity-75">
					<div class="flex gap-4">
						<span>{$i18n.t('Prompt tokens')}: {message.usage.prompt_tokens}</span>
						<span>{$i18n.t('Completion tokens')}: {message.usage.completion_tokens}</span>
						<span>{$i18n.t('Total tokens')}: {message.usage.total_tokens}</span>
					</div>
				</div>
			{/if}
			
			<!-- References -->
			{#if message.references && message.references.length > 0}
				<div class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600">
					<div class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
						{$i18n.t('References')}:
					</div>
					<div class="space-y-2">
						{#each message.references as ref, index}
							<div class="bg-white dark:bg-gray-900 rounded p-2 text-xs">
								<div class="font-medium text-gray-800 dark:text-gray-200 mb-1">
									{$i18n.t('Reference')} {index + 1}
									{#if ref.file_name}
										- {ref.file_name}
									{/if}
								</div>
								<div class="text-gray-600 dark:text-gray-400 line-clamp-3">
									{ref.text}
								</div>
								{#if ref.hit_rate && ref.hit_rate !== '0.00%'}
									<div class="mt-1 text-gray-500 dark:text-gray-500">
										{$i18n.t('Hit rate')}: {ref.hit_rate}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.line-clamp-3 {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	
	.prose {
		color: inherit;
	}
	
	.prose :where(p):not(:where([class~="not-prose"] *)) {
		margin-top: 0;
		margin-bottom: 0.5rem;
	}
	
	.prose :where(p):last-child:not(:where([class~="not-prose"] *)) {
		margin-bottom: 0;
	}
	
	.prose :where(code):not(:where([class~="not-prose"] *)) {
		background-color: rgba(0, 0, 0, 0.1);
		padding: 0.125rem 0.25rem;
		border-radius: 0.25rem;
		font-size: 0.875em;
	}
	
	.dark .prose :where(code):not(:where([class~="not-prose"] *)) {
		background-color: rgba(255, 255, 255, 0.1);
	}
</style>