import {createContext, useState, useContext, useEffect} from "react";
import {getCookie} from "../utils/getCookie.js";

export const AuthContext = createContext();

export function AuthProvider({ children }) {
    const [accessToken, setAccessToken] = useState(null);

    async function getCSRFToken() {
        await fetch("/api/csrf/", {credentials: "include"});
    }

    async function refreshAccessToken() {
        console.log("Refreshing access token...")
        const res = await fetch("/api/token/refresh/", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify({})
        });

        console.log("Refresh response: ", res)

        if (res.ok) {
            const data = await res.json();
            setAccessToken(data.access);
            return data.access;
        } else {
            setAccessToken(null);
            return null;
        }
    }

    useEffect(() =>{
        getCSRFToken();
        refreshAccessToken();
        }, []);

    return (
        <AuthContext.Provider value={{accessToken, setAccessToken, refreshAccessToken}}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    return useContext(AuthContext)
}