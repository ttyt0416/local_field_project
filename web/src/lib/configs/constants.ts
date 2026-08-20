import { env } from '$env/dynamic/public';

export const APP_NAME = 'Local Field';
export const API_DOCS_PATH = '/docs';
export const DEFAULT_SERVER_HOST = 'localhost';
export const DEFAULT_SERVER_PORT = '8080';

const serverHost = env.PUBLIC_SERVER_HOST || DEFAULT_SERVER_HOST;
const serverPort = env.PUBLIC_SERVER_PORT || DEFAULT_SERVER_PORT;
export const SERVER_URL = env.PUBLIC_SERVER_URL || `http://${serverHost}:${serverPort}`;
export const SERVER_DOCS_URL = `${SERVER_URL}${API_DOCS_PATH}`;
