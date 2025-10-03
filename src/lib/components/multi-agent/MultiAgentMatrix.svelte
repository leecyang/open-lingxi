<script lang="ts">
	import { onMount, onDestroy, getContext, tick } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';
	import { io, type Socket } from 'socket.io-client';
	
	import { user, config } from '$lib/stores';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { getAgents, getEnabledAgents } from '$lib/apis/agents';
	import { sendMultiChat } from '$lib/apis/multi-chat';
	
	import AgentCard from './AgentCard.svelte';
	import MessageBubble from './MessageBubble.svelte';
	import LoadingSpinner from '../common/LoadingSpinner.svelte';
	import Button from '../common/Button.svelte';
	import Textarea from '../common/Textarea.svelte';
	
	const i18n = getContext('i18n');
	
	// Component props
	export let convId: string = '';
	export let selectedAgentUids: string[] = [];
	export let autoConnect: boolean = true;
	
	// State variables
	let socket: Socket | null = null;
	let connected = false;
	let agents: any[] = [];
	let messages: any[] = [];
	let inputMessage = '';
	let isLoading = false;
	let isSending = false;
	let conversationHistory: string[][] = [];
	
	// UI state
	let messageContainer: HTMLElement;
	let inputElement: HTMLTextAreaElement;
	
	// Initialize conversation ID
	if (!convId) {
		convId = uuidv4();
	}
	
	// Load available agents
	async function loadAgents() {
		try {
			const response = await getEnabledAgents();
			agents = response || [];
		} catch (error) {
			console.error('Failed to load agents:', error);
			toast.error($i18n.t('Failed to load agents'));
		}
	}
	
	// Initialize WebSocket connection
	function initializeSocket() {
		if (!$user?.token) {
			console.error('No user token available');
			return;
		}
		
		try {
			socket = io(WEBUI_API_BASE_URL, {
				path: '/ws/socket.io',
				auth: {
					token: $user.token
				},
				transports: ['websocket', 'polling']
			});
			
			socket.on('connect', () => {
				console.log('Connected to WebSocket');
				connected = true;
				joinConversation();
			});
			
			socket.on('disconnect', () => {
				console.log('Disconnected from WebSocket');
				connected = false;
			});
			
			socket.on('multi-agent-message', handleAgentMessage);
			socket.on('multi-agent-system', handleSystemMessage);
			socket.on('multi-agent-error', handleError);
			socket.on('multi-agent-joined', handleJoined);
			socket.on('multi-agent-left', handleLeft);
			
		} catch (error) {
			console.error('Failed to initialize socket:', error);
			toast.error($i18n.t('Failed to connect to server'));
		}
	}
	
	// Join conversation room
	function joinConversation() {
		if (!socket || !connected) return;
		
		socket.emit('multi-agent-join', {
			auth: { token: $user.token },
			conv_id: convId,
			agent_uids: selectedAgentUids
		});
	}
	
	// Leave conversation room
	function leaveConversation() {
		if (!socket || !connected) return;
		
		socket.emit('multi-agent-leave', {
			conv_id: convId
		});
	}
	
	// Handle agent message
	function handleAgentMessage(data: any) {
		const { agent_id, timestamp, data: messageData } = data;
		
		// Find agent info
		const agent = agents.find(a => a.agent_uid === agent_id);
		const agentName = agent?.name || agent_id;
		
		// Create or update message
		const existingMessageIndex = messages.findIndex(
			m => m.agent_id === agent_id && m.type !== 'complete'
		);
		
		if (messageData.type === 'delta') {
			// Update existing message with delta
			if (existingMessageIndex >= 0) {
				messages[existingMessageIndex].content = messageData.accumulated || messageData.content;
				messages[existingMessageIndex].timestamp = timestamp;
			} else {
				// Create new message
				messages = [...messages, {
					id: uuidv4(),
					agent_id,
					agent_name: agentName,
					content: messageData.content,
					type: 'streaming',
					timestamp,
					references: messageData.references
				}];
			}
		} else if (messageData.type === 'complete') {
			// Finalize message
			if (existingMessageIndex >= 0) {
				messages[existingMessageIndex].content = messageData.content;
				messages[existingMessageIndex].type = 'complete';
				messages[existingMessageIndex].timestamp = timestamp;
				messages[existingMessageIndex].usage = messageData.usage;
				messages[existingMessageIndex].references = messageData.references;
			} else {
				messages = [...messages, {
					id: uuidv4(),
					agent_id,
					agent_name: agentName,
					content: messageData.content,
					type: 'complete',
					timestamp,
					usage: messageData.usage,
					references: messageData.references
				}];
			}
		} else if (messageData.type === 'error') {
			// Add error message
			messages = [...messages, {
				id: uuidv4(),
				agent_id,
				agent_name: agentName,
				content: messageData.content,
				type: 'error',
				timestamp
			}];
		} else if (messageData.type === 'status') {
			// Add status message
			messages = [...messages, {
				id: uuidv4(),
				agent_id,
				agent_name: agentName,
				content: messageData.content,
				type: 'status',
				timestamp
			}];
		}
		
		// Trigger reactivity
		messages = messages;
		
		// Scroll to bottom
		tick().then(() => {
			if (messageContainer) {
				messageContainer.scrollTop = messageContainer.scrollHeight;
			}
		});
	}
	
	// Handle system message
	function handleSystemMessage(data: any) {
		const { message_type, timestamp, data: messageData } = data;
		
		messages = [...messages, {
			id: uuidv4(),
			agent_id: 'system',
			agent_name: 'System',
			content: messageData.message,
			type: message_type,
			timestamp,
			agent_count: messageData.agent_count,
			agent_names: messageData.agent_names
		}];
		
		if (message_type === 'complete') {
			isSending = false;
		}
		
		// Scroll to bottom
		tick().then(() => {
			if (messageContainer) {
				messageContainer.scrollTop = messageContainer.scrollHeight;
			}
		});
	}
	
	// Handle error
	function handleError(data: any) {
		console.error('WebSocket error:', data);
		toast.error(data.error || $i18n.t('An error occurred'));
		isSending = false;
	}
	
	// Handle joined confirmation
	function handleJoined(data: any) {
		console.log('Joined conversation:', data);
		toast.success($i18n.t('Connected to conversation'));
	}
	
	// Handle left confirmation
	function handleLeft(data: any) {
		console.log('Left conversation:', data);
	}
	
	// Send message to agents
	async function sendMessage() {
		if (!inputMessage.trim() || isSending || selectedAgentUids.length === 0) {
			return;
		}
		
		const message = inputMessage.trim();
		inputMessage = '';
		isSending = true;
		
		// Add user message to display
		messages = [...messages, {
			id: uuidv4(),
			agent_id: 'user',
			agent_name: $user?.name || 'You',
			content: message,
			type: 'user',
			timestamp: Date.now()
		}];
		
		try {
			const response = await sendMultiChat({
				conv_id: convId,
				user_id: $user.id,
				message,
				agent_uids: selectedAgentUids,
				history: conversationHistory
			});
			
			if (response.status === 'accepted') {
				// Add to conversation history
				conversationHistory = [...conversationHistory, [message, '']];
				
				// Scroll to bottom
				tick().then(() => {
					if (messageContainer) {
						messageContainer.scrollTop = messageContainer.scrollHeight;
					}
				});
			} else {
				throw new Error('Request not accepted');
			}
		} catch (error) {
			console.error('Failed to send message:', error);
			toast.error($i18n.t('Failed to send message'));
			isSending = false;
		}
	}
	
	// Handle key press in input
	function handleKeyPress(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			sendMessage();
		}
	}
	
	// Toggle agent selection
	function toggleAgent(agentUid: string) {
		if (selectedAgentUids.includes(agentUid)) {
			selectedAgentUids = selectedAgentUids.filter(uid => uid !== agentUid);
		} else {
			selectedAgentUids = [...selectedAgentUids, agentUid];
		}
		
		// Update WebSocket room if connected
		if (connected) {
			leaveConversation();
			tick().then(() => {
				joinConversation();
			});
		}
	}
	
	// Clear conversation
	function clearConversation() {
		messages = [];
		conversationHistory = [];
		convId = uuidv4();
		
		if (connected) {
			leaveConversation();
			tick().then(() => {
				joinConversation();
			});
		}
	}
	
	// Component lifecycle
	onMount(async () => {
		isLoading = true;
		await loadAgents();
		
		if (autoConnect) {
			initializeSocket();
		}
		
		isLoading = false;
	});
	
	onDestroy(() => {
		if (socket) {
			leaveConversation();
			socket.disconnect();
		}
	});
</script>

<div class="flex flex-col h-full max-h-screen">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-700 p-4">
		<div class="flex items-center justify-between">
			<h2 class="text-xl font-semibold text-gray-900 dark:text-white">
				{$i18n.t('Multi-Agent Chat')}
			</h2>
			
			<div class="flex items-center gap-2">
				<div class="flex items-center gap-1">
					<div class="w-2 h-2 rounded-full {connected ? 'bg-green-500' : 'bg-red-500'}"></div>
					<span class="text-sm text-gray-600 dark:text-gray-400">
						{connected ? $i18n.t('Connected') : $i18n.t('Disconnected')}
					</span>
				</div>
				
				<Button
					variant="outline"
					size="sm"
					on:click={clearConversation}
					disabled={isSending}
				>
					{$i18n.t('Clear')}
				</Button>
			</div>
		</div>
		
		<!-- Agent Selection -->
		<div class="mt-4">
			<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
				{$i18n.t('Select Agents')} ({selectedAgentUids.length})
			</h3>
			
			{#if isLoading}
				<div class="flex justify-center py-4">
					<LoadingSpinner />
				</div>
			{:else if agents.length === 0}
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{$i18n.t('No agents available')}
				</p>
			{:else}
				<div class="flex flex-wrap gap-2">
					{#each agents as agent (agent.agent_uid)}
						<AgentCard
							{agent}
							selected={selectedAgentUids.includes(agent.agent_uid)}
							on:toggle={() => toggleAgent(agent.agent_uid)}
						/>
					{/each}
				</div>
			{/if}
		</div>
	</div>
	
	<!-- Messages -->
	<div 
		class="flex-1 overflow-y-auto p-4 space-y-4"
		bind:this={messageContainer}
	>
		{#if messages.length === 0}
			<div class="flex flex-col items-center justify-center h-full text-center">
				<div class="text-gray-400 dark:text-gray-600 mb-4">
					<svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
					</svg>
				</div>
				<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">
					{$i18n.t('Start a conversation')}
				</h3>
				<p class="text-gray-500 dark:text-gray-400">
					{$i18n.t('Select agents and send a message to begin')}
				</p>
			</div>
		{:else}
			{#each messages as message (message.id)}
				<MessageBubble {message} />
			{/each}
		{/if}
	</div>
	
	<!-- Input -->
	<div class="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 p-4">
		<div class="flex gap-2">
			<div class="flex-1">
				<Textarea
					bind:value={inputMessage}
					bind:element={inputElement}
					placeholder={selectedAgentUids.length > 0 
						? $i18n.t('Type your message...') 
						: $i18n.t('Select agents first...')}
					disabled={!connected || selectedAgentUids.length === 0 || isSending}
					rows={2}
					on:keydown={handleKeyPress}
					class="resize-none"
				/>
			</div>
			
			<Button
				on:click={sendMessage}
				disabled={!connected || !inputMessage.trim() || selectedAgentUids.length === 0 || isSending}
				class="self-end"
			>
				{#if isSending}
					<LoadingSpinner size="sm" />
				{:else}
					{$i18n.t('Send')}
				{/if}
			</Button>
		</div>
		
		{#if selectedAgentUids.length > 0}
			<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('Sending to')} {selectedAgentUids.length} {selectedAgentUids.length === 1 ? $i18n.t('agent') : $i18n.t('agents')}
			</div>
		{/if}
	</div>
</div>

<style>
	/* Custom scrollbar for message container */
	.overflow-y-auto::-webkit-scrollbar {
		width: 6px;
	}
	
	.overflow-y-auto::-webkit-scrollbar-track {
		background: transparent;
	}
	
	.overflow-y-auto::-webkit-scrollbar-thumb {
		background-color: rgba(156, 163, 175, 0.5);
		border-radius: 3px;
	}
	
	.overflow-y-auto::-webkit-scrollbar-thumb:hover {
		background-color: rgba(156, 163, 175, 0.7);
	}
</style>