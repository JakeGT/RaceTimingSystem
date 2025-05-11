import {getCookie} from "./getCookie";
import {useAuth} from "../context/AuthContext";

export async function fetchWithAuth(url, options = {}, accessToken, refreshAccessToken) {
    let headers = {
        ...(options.headers || {}),
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
    };

    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    const res = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
    });

    if (res.status === 401 && refreshAccessToken) {
        const newToken = await refreshAccessToken();
        if (newToken) {
            headers["Authorization"] = `Bearer ${newToken}`;
            const retryRes = await fetch(url, {
                ...options,
                headers,
                credentials: "include",
            });
            return retryRes;
        }
    }

    return res;
}