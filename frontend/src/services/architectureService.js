import { API_V1_BASE_URL } from '../config/runtimeConfig';

const API_BASE_URL = API_V1_BASE_URL;

export const architectureService = {
  getSnapshot: async (force = false) => {
    const url = `${API_BASE_URL}/architecture/snapshot${force ? '?force=true' : ''}`;
    const response = await fetch(url);

    if (!response.ok) {
      let err = {};
      try {
        err = await response.json();
      } catch {
        err = {};
      }
      throw new Error(err.detail || `Architecture snapshot failed (${response.status})`);
    }

    return response.json();
  },
};
