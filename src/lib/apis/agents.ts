import { WEBUI_API_BASE_URL } from '$lib/constants';

export interface AgentConfig {
	modelId: string;
	params?: {
		temperature?: number;
		top_p?: number;
		max_gen_len?: number;
	};
	klAssistId?: string;
	timeout?: number;
	max_retries?: number;
}

export interface Agent {
	id: string;
	agent_uid: string;
	name: string;
	owner_user_id: string;
	api_host: string;
	api_key_env: string;
	enabled: boolean;
	config?: AgentConfig;
	owner?: {
		id: string;
		name: string;
		email: string;
		role: string;
		profile_image_url: string;
	};
	updated_at: number;
	created_at: number;
}

export interface AgentForm {
	name: string;
	api_host: string;
	api_key_env: string;
	config?: AgentConfig;
	enabled?: boolean;
}

export interface AgentUpdateForm {
	name?: string;
	api_host?: string;
	api_key_env?: string;
	config?: AgentConfig;
	enabled?: boolean;
}

// Get all agents (based on user role)
export const getAgents = async (token: string = ''): Promise<Agent[]> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/`, {
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

// Get enabled agents for chat
export const getEnabledAgents = async (token: string = ''): Promise<Agent[]> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/enabled/list`, {
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

// Get agent by ID
export const getAgentById = async (id: string, token: string = ''): Promise<Agent> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/${id}`, {
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

// Create new agent
export const createAgent = async (form: AgentForm, token: string = ''): Promise<Agent> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
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

// Update agent
export const updateAgent = async (
	id: string,
	form: AgentUpdateForm,
	token: string = ''
): Promise<Agent> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/${id}`, {
		method: 'PUT',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
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

// Toggle agent enabled/disabled
export const toggleAgent = async (id: string, token: string = ''): Promise<Agent> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/${id}/toggle`, {
		method: 'POST',
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

// Delete agent
export const deleteAgent = async (id: string, token: string = ''): Promise<boolean> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/agents/${id}`, {
		method: 'DELETE',
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