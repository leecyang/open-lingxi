import { WEBUI_API_BASE_URL } from '$lib/constants';

export interface MultiChatRequest {
	conv_id: string;
	user_id: string;
	message: string;
	agent_uids: string[];
	history?: string[][];
}

export interface MultiChatResponse {
	conv_id: string;
	status: string;
	message: string;
}

export interface ConversationStatus {
	conv_id: string;
	user_id: string;
	agent_uids: string[];
	active_sessions: number;
	created_at: number;
	last_activity: number;
}

export interface ActiveConversationsResponse {
	conversations: ConversationStatus[];
	total: number;
}

// Send multi-chat request
export const sendMultiChat = async (
	request: MultiChatRequest,
	token: string = ''
): Promise<MultiChatResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/multi-chat`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(request)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get conversation status
export const getConversationStatus = async (
	convId: string,
	token: string = ''
): Promise<ConversationStatus> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/conversations/${convId}/status`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Get active conversations (admin only)
export const getActiveConversations = async (
	token: string = ''
): Promise<ActiveConversationsResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/conversations/active`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};