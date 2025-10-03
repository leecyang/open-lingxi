<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import type { Agent, AgentForm, AgentUpdateForm, AgentConfig } from '$lib/apis/agents';
	
	import Modal from '../common/Modal.svelte';
	import Button from '../common/Button.svelte';
	
	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');
	
	export let show = false;
	export let title = '';
	export let agent: Agent | null = null;
	
	// Form data
	let formData = {
		name: '',
		api_host: '',
		api_key: '',
		generated_token: '',
		enabled: true,
		config: {
			modelId: 'jiutian-lan',
			params: {
				temperature: 0.8,
				top_p: 0.95,
				max_gen_len: 256
			},
			klAssistId: '',
			timeout: 30,
			max_retries: 1
		}
	};
	
	// Available models
	const availableModels = [
		{ id: 'jiutian-lan', name: '九天基础语言大模型' },
		{ id: 'jiutian-med', name: '九天医疗大模型' },
		{ id: 'jiutian-cus', name: '九天客服大模型' },
		{ id: 'jiutian-gov', name: '九天海算政务大模型' }
	];
	
	// Reset form when modal opens/closes or agent changes
	$: if (show) {
		resetForm();
	}
	
	function resetForm() {
		if (agent) {
			// Edit mode - populate with existing data
			formData = {
				name: agent.name,
				api_host: agent.api_host,
				api_key: agent.api_key || '',
				generated_token: agent.generated_token || '',
				enabled: agent.enabled,
				config: {
					modelId: agent.config?.modelId || 'jiutian-lan',
					params: {
						temperature: agent.config?.params?.temperature || 0.8,
						top_p: agent.config?.params?.top_p || 0.95,
						max_gen_len: agent.config?.params?.max_gen_len || 256
					},
					klAssistId: agent.config?.klAssistId || '',
					timeout: agent.config?.timeout || 30,
					max_retries: agent.config?.max_retries || 1
				}
			};
		} else {
			// Create mode - use defaults
			formData = {
				name: '',
				api_host: 'https://jiutian.10086.cn',
				api_key: '',
				generated_token: '',
				enabled: true,
				config: {
					modelId: 'jiutian-lan',
					params: {
						temperature: 0.8,
						top_p: 0.95,
						max_gen_len: 256
					},
					klAssistId: '',
					timeout: 30,
					max_retries: 1
				}
			};
		}
		
		// Generate token if API key is provided
		if (formData.api_key) {
			generateToken();
		}
	}
	
	// Generate JWT token from API key
	function generateToken() {
		if (!formData.api_key.trim()) {
			formData.generated_token = '';
			return;
		}
		
		try {
			// Validate API key format
			const parts = formData.api_key.split('.');
			if (parts.length !== 2 || !parts[0] || !parts[1]) {
				throw new Error('Invalid API key format');
			}
			
			// Generate JWT token (simplified client-side generation for display)
			// In production, this should be done server-side for security
			const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT", sign_type: "SIGN" }));
			const payload = btoa(JSON.stringify({
				api_key: parts[0],
				exp: Math.floor(Date.now() / 1000) + 3600,
				timestamp: Math.floor(Date.now() / 1000)
			}));
			
			// Note: This is a simplified version for display purposes
			// The actual signing should be done server-side
			formData.generated_token = `${header}.${payload}.[SIGNATURE_GENERATED_SERVER_SIDE]`;
			
		} catch (error) {
			console.error('Error generating token:', error);
			formData.generated_token = '';
		}
	}
	
	// Watch for API key changes to regenerate token
	$: if (formData.api_key) {
		generateToken();
	}
	
	function handleSubmit() {
		// Validate required fields
		if (!formData.name.trim()) {
			alert($i18n.t('Agent name is required'));
			return;
		}
		
		if (!formData.api_host.trim()) {
			alert($i18n.t('API host is required'));
			return;
		}
		
		if (!formData.api_key.trim()) {
			alert($i18n.t('API key is required'));
			return;
		}
		
		// Validate API key format
		const parts = formData.api_key.split('.');
		if (parts.length !== 2 || !parts[0] || !parts[1]) {
			alert($i18n.t('Invalid API key format. Expected: id.secret'));
			return;
		}
		
		// Prepare submission data
		const submitData = {
			name: formData.name.trim(),
			api_host: formData.api_host.trim(),
			api_key: formData.api_key.trim(),
			enabled: formData.enabled,
			config: {
				...formData.config,
				klAssistId: formData.config.klAssistId.trim() || undefined
			}
		};
		
		// Remove empty klAssistId
		if (!submitData.config.klAssistId) {
			delete submitData.config.klAssistId;
		}
		
		dispatch('submit', submitData);
	}
	
	function handleCancel() {
		dispatch('cancel');
	}
</script>

<Modal bind:show size="lg">
	<div slot="title">{title}</div>
	
	<div slot="content" class="space-y-6">
		<!-- Basic Information -->
		<div class="space-y-4">
			<h3 class="text-lg font-medium text-gray-900 dark:text-white">
				{$i18n.t('Basic Information')}
			</h3>
			
			<!-- Agent Name -->
			<div>
				<label for="agent-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('Agent Name')} *
				</label>
				<input
					id="agent-name"
					type="text"
					bind:value={formData.name}
					placeholder={$i18n.t('Enter agent name')}
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					required
				/>
			</div>
			
			<!-- API Host -->
			<div>
				<label for="api-host" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('API Host')} *
				</label>
				<input
					id="api-host"
					type="url"
					bind:value={formData.api_host}
					placeholder="https://jiutian.10086.cn"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					required
				/>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Each agent can have its own API endpoint')}
				</p>
			</div>
			
			<!-- API Key -->
			<div>
				<label for="api-key" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('API Key')} *
				</label>
				<input
					id="api-key"
					type="password"
					bind:value={formData.api_key}
					placeholder="646ae749bcf5bc1a1498aeaf.IbIpYGawQ8VwQ2HYTohDCKJP/aGgGaC"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					required
				/>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('Format: api_key_id.secret (from Jiutian platform)')}
				</p>
			</div>
			
			<!-- Token (Auto-generated) -->
			<div>
				<label for="token-display" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('JWT Token')} ({$i18n.t('Auto-generated')})
				</label>
				<div class="relative">
					<input
						id="token-display"
						type="text"
						value={formData.generated_token || $i18n.t('Token will be generated automatically')}
						readonly
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-900 text-gray-600 dark:text-gray-400 text-sm"
					/>
					{#if formData.generated_token}
						<button
							type="button"
							on:click={() => navigator.clipboard.writeText(formData.generated_token)}
							class="absolute right-2 top-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
							title={$i18n.t('Copy token')}
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
							</svg>
						</button>
					{/if}
				</div>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					{$i18n.t('JWT token is automatically generated from the API key')}
				</p>
			</div>
			
			<!-- Enabled -->
			<div class="flex items-center">
				<input
					id="agent-enabled"
					type="checkbox"
					bind:checked={formData.enabled}
					class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
				/>
				<label for="agent-enabled" class="ml-2 block text-sm text-gray-900 dark:text-white">
					{$i18n.t('Enabled')}
				</label>
			</div>
		</div>
		
		<!-- Model Configuration -->
		<div class="space-y-4">
			<h3 class="text-lg font-medium text-gray-900 dark:text-white">
				{$i18n.t('Model Configuration')}
			</h3>
			
			<!-- Model Selection -->
			<div>
				<label for="model-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('Model')}
				</label>
				<select
					id="model-id"
					bind:value={formData.config.modelId}
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
				>
					{#each availableModels as model}
						<option value={model.id}>{model.name}</option>
					{/each}
				</select>
			</div>
			
			<!-- Knowledge Assistant ID -->
			<div>
				<label for="kl-assist-id" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					{$i18n.t('Knowledge Assistant ID')}
				</label>
				<input
					id="kl-assist-id"
					type="text"
					bind:value={formData.config.klAssistId}
					placeholder={$i18n.t('Optional knowledge assistant ID')}
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
				/>
			</div>
			
			<!-- Model Parameters -->
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
				<!-- Temperature -->
				<div>
					<label for="temperature" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$i18n.t('Temperature')}
					</label>
					<input
						id="temperature"
						type="number"
						min="0.1"
						max="1.0"
						step="0.1"
						bind:value={formData.config.params.temperature}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
				
				<!-- Top P -->
				<div>
					<label for="top-p" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$i18n.t('Top P')}
					</label>
					<input
						id="top-p"
						type="number"
						min="0.1"
						max="1.0"
						step="0.05"
						bind:value={formData.config.params.top_p}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
				
				<!-- Max Generation Length -->
				<div>
					<label for="max-gen-len" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$i18n.t('Max Length')}
					</label>
					<input
						id="max-gen-len"
						type="number"
						min="1"
						max="4096"
						bind:value={formData.config.params.max_gen_len}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
			</div>
		</div>
		
		<!-- Advanced Settings -->
		<div class="space-y-4">
			<h3 class="text-lg font-medium text-gray-900 dark:text-white">
				{$i18n.t('Advanced Settings')}
			</h3>
			
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<!-- Timeout -->
				<div>
					<label for="timeout" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$i18n.t('Timeout (seconds)')}
					</label>
					<input
						id="timeout"
						type="number"
						min="5"
						max="300"
						bind:value={formData.config.timeout}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
				
				<!-- Max Retries -->
				<div>
					<label for="max-retries" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$i18n.t('Max Retries')}
					</label>
					<input
						id="max-retries"
						type="number"
						min="0"
						max="5"
						bind:value={formData.config.max_retries}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
			</div>
		</div>
	</div>
	
	<div slot="footer" class="flex justify-end gap-2">
		<Button variant="outline" on:click={handleCancel}>
			{$i18n.t('Cancel')}
		</Button>
		<Button on:click={handleSubmit}>
			{agent ? $i18n.t('Update') : $i18n.t('Create')}
		</Button>
	</div>
</Modal>