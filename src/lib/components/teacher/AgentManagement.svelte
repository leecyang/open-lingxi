<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	
	import { user } from '$lib/stores';
	import { getAgents, createAgent, updateAgent, deleteAgent, toggleAgent, type Agent, type AgentForm, type AgentUpdateForm } from '$lib/apis/agents';
	
	import Button from '../common/Button.svelte';
	import LoadingSpinner from '../common/LoadingSpinner.svelte';
	import AgentFormModal from '../admin/AgentFormModal.svelte';
	import ConfirmDialog from '../common/ConfirmDialog.svelte';
	
	const i18n = getContext('i18n');
	
	// State
	let agents: Agent[] = [];
	let isLoading = false;
	let showCreateModal = false;
	let showEditModal = false;
	let showDeleteDialog = false;
	let selectedAgent: Agent | null = null;
	let searchQuery = '';
	
	// Filtered agents (only show user's own agents)
	$: filteredAgents = agents.filter(agent => 
		agent.owner_user_id === $user?.id &&
		(agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
		agent.api_host.toLowerCase().includes(searchQuery.toLowerCase()))
	);
	
	// Load agents
	async function loadAgents() {
		isLoading = true;
		try {
			agents = await getAgents($user?.token);
		} catch (error) {
			console.error('Failed to load agents:', error);
			toast.error($i18n.t('Failed to load agents'));
		} finally {
			isLoading = false;
		}
	}
	
	// Handle create agent
	async function handleCreateAgent(form: AgentForm) {
		try {
			const newAgent = await createAgent(form, $user?.token);
			agents = [...agents, newAgent];
			showCreateModal = false;
			toast.success($i18n.t('Agent created successfully'));
		} catch (error) {
			console.error('Failed to create agent:', error);
			toast.error($i18n.t('Failed to create agent'));
		}
	}
	
	// Handle edit agent
	async function handleEditAgent(form: AgentUpdateForm) {
		if (!selectedAgent) return;
		
		try {
			const updatedAgent = await updateAgent(selectedAgent.id, form, $user?.token);
			agents = agents.map(agent => 
				agent.id === selectedAgent.id ? updatedAgent : agent
			);
			showEditModal = false;
			selectedAgent = null;
			toast.success($i18n.t('Agent updated successfully'));
		} catch (error) {
			console.error('Failed to update agent:', error);
			toast.error($i18n.t('Failed to update agent'));
		}
	}
	
	// Handle toggle agent
	async function handleToggleAgent(agent: Agent) {
		try {
			const updatedAgent = await toggleAgent(agent.id, $user?.token);
			agents = agents.map(a => 
				a.id === agent.id ? updatedAgent : a
			);
			toast.success($i18n.t('Agent status updated'));
		} catch (error) {
			console.error('Failed to toggle agent:', error);
			toast.error($i18n.t('Failed to update agent status'));
		}
	}
	
	// Handle delete agent
	async function handleDeleteAgent() {
		if (!selectedAgent) return;
		
		try {
			await deleteAgent(selectedAgent.id, $user?.token);
			agents = agents.filter(agent => agent.id !== selectedAgent.id);
			showDeleteDialog = false;
			selectedAgent = null;
			toast.success($i18n.t('Agent deleted successfully'));
		} catch (error) {
			console.error('Failed to delete agent:', error);
			toast.error($i18n.t('Failed to delete agent'));
		}
	}
	
	// Open edit modal
	function openEditModal(agent: Agent) {
		selectedAgent = agent;
		showEditModal = true;
	}
	
	// Open delete dialog
	function openDeleteDialog(agent: Agent) {
		selectedAgent = agent;
		showDeleteDialog = true;
	}
	
	// Format date
	function formatDate(timestamp: number) {
		return new Date(timestamp * 1000).toLocaleString();
	}
	
	// Get model display name
	function getModelDisplayName(modelId: string) {
		const modelNames: Record<string, string> = {
			'jiutian-lan': '九天基础语言大模型',
			'jiutian-med': '九天医疗大模型',
			'jiutian-cus': '九天客服大模型',
			'jiutian-gov': '九天海算政务大模型'
		};
		return modelNames[modelId] || modelId;
	}
	
	onMount(() => {
		loadAgents();
	});
</script>

<div class="p-6">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-white">
				{$i18n.t('My Agents')}
			</h1>
			<p class="text-gray-600 dark:text-gray-400 mt-1">
				{$i18n.t('Manage your agents')}
			</p>
		</div>
		
		<Button on:click={() => showCreateModal = true}>
			{$i18n.t('Create Agent')}
		</Button>
	</div>
	
	<!-- Search -->
	<div class="mb-6">
		<input
			type="text"
			bind:value={searchQuery}
			placeholder={$i18n.t('Search your agents...')}
			class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
		/>
	</div>
	
	<!-- Loading -->
	{#if isLoading}
		<div class="flex justify-center py-12">
			<LoadingSpinner />
		</div>
	{:else if filteredAgents.length === 0}
		<!-- Empty state -->
		<div class="text-center py-12">
			<div class="text-gray-400 dark:text-gray-600 mb-4">
				<svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
				</svg>
			</div>
			<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">
				{searchQuery ? $i18n.t('No agents found') : $i18n.t('No agents yet')}
			</h3>
			<p class="text-gray-500 dark:text-gray-400 mb-4">
				{searchQuery 
					? $i18n.t('Try adjusting your search terms') 
					: $i18n.t('Create your first agent to get started')}
			</p>
			{#if !searchQuery}
				<Button on:click={() => showCreateModal = true}>
					{$i18n.t('Create Agent')}
				</Button>
			{/if}
		</div>
	{:else}
		<!-- Agents grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#each filteredAgents as agent (agent.id)}
				<div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
					<!-- Header -->
					<div class="flex items-start justify-between mb-4">
						<div class="flex-1">
							<h3 class="text-lg font-medium text-gray-900 dark:text-white truncate">
								{agent.name}
							</h3>
							<p class="text-sm text-gray-500 dark:text-gray-400 truncate">
								{agent.api_host}
							</p>
						</div>
						
						<div class="flex items-center gap-1 ml-2">
							<div class="w-2 h-2 rounded-full {agent.enabled ? 'bg-green-500' : 'bg-red-500'}"></div>
							<span class="text-xs text-gray-600 dark:text-gray-400">
								{agent.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}
							</span>
						</div>
					</div>
					
					<!-- Configuration -->
					<div class="space-y-2 mb-4">
						<div class="text-sm">
							<span class="font-medium text-gray-700 dark:text-gray-300">{$i18n.t('Model')}:</span>
							<span class="text-gray-600 dark:text-gray-400 ml-1">
								{agent.config?.modelId ? getModelDisplayName(agent.config.modelId) : '-'}
							</span>
						</div>
						
						{#if agent.config?.klAssistId}
							<div class="text-sm">
								<span class="font-medium text-gray-700 dark:text-gray-300">{$i18n.t('Knowledge Assistant')}:</span>
								<span class="text-gray-600 dark:text-gray-400 ml-1 truncate block">
									{agent.config.klAssistId}
								</span>
							</div>
						{/if}
						
						<div class="text-sm">
							<span class="font-medium text-gray-700 dark:text-gray-300">{$i18n.t('API Key')}:</span>
							<span class="text-gray-600 dark:text-gray-400 ml-1">
								{agent.api_key_env}
							</span>
						</div>
					</div>
					
					<!-- Parameters -->
					{#if agent.config?.params}
						<div class="bg-gray-50 dark:bg-gray-900 rounded-md p-3 mb-4">
							<div class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
								{$i18n.t('Parameters')}
							</div>
							<div class="grid grid-cols-3 gap-2 text-xs">
								<div>
									<span class="text-gray-500 dark:text-gray-400">Temp:</span>
									<span class="text-gray-700 dark:text-gray-300 ml-1">
										{agent.config.params.temperature}
									</span>
								</div>
								<div>
									<span class="text-gray-500 dark:text-gray-400">Top-p:</span>
									<span class="text-gray-700 dark:text-gray-300 ml-1">
										{agent.config.params.top_p}
									</span>
								</div>
								<div>
									<span class="text-gray-500 dark:text-gray-400">Max:</span>
									<span class="text-gray-700 dark:text-gray-300 ml-1">
										{agent.config.params.max_gen_len}
									</span>
								</div>
							</div>
						</div>
					{/if}
					
					<!-- Footer -->
					<div class="flex items-center justify-between">
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{formatDate(agent.created_at)}
						</div>
						
						<div class="flex items-center gap-1">
							<Button
								variant="outline"
								size="sm"
								on:click={() => handleToggleAgent(agent)}
								class="text-xs"
							>
								{agent.enabled ? $i18n.t('Disable') : $i18n.t('Enable')}
							</Button>
							
							<Button
								variant="outline"
								size="sm"
								on:click={() => openEditModal(agent)}
								class="text-xs"
							>
								{$i18n.t('Edit')}
							</Button>
							
							<Button
								variant="outline"
								size="sm"
								class="text-xs text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
								on:click={() => openDeleteDialog(agent)}
							>
								{$i18n.t('Delete')}
							</Button>
						</div>
					</div>
				</div>
			{/each}
		</div>
		
		<!-- Summary -->
		<div class="mt-6 text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Showing')} {filteredAgents.length} {$i18n.t('of your agents')}
		</div>
	{/if}
</div>

<!-- Create Agent Modal -->
<AgentFormModal
	bind:show={showCreateModal}
	title={$i18n.t('Create Agent')}
	on:submit={(e) => handleCreateAgent(e.detail)}
	on:cancel={() => showCreateModal = false}
/>

<!-- Edit Agent Modal -->
<AgentFormModal
	bind:show={showEditModal}
	title={$i18n.t('Edit Agent')}
	agent={selectedAgent}
	on:submit={(e) => handleEditAgent(e.detail)}
	on:cancel={() => {
		showEditModal = false;
		selectedAgent = null;
	}}
/>

<!-- Delete Confirmation Dialog -->
<ConfirmDialog
	bind:show={showDeleteDialog}
	title={$i18n.t('Delete Agent')}
	message={$i18n.t('Are you sure you want to delete this agent? This action cannot be undone.')}
	confirmText={$i18n.t('Delete')}
	confirmClass="bg-red-600 hover:bg-red-700 text-white"
	on:confirm={handleDeleteAgent}
	on:cancel={() => {
		showDeleteDialog = false;
		selectedAgent = null;
	}}
/>