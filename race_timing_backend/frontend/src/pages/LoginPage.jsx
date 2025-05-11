import {useState, useEffect} from "react";
import {useNavigate} from "react-router-dom";
import {useAuth} from "../context/AuthContext.jsx"
import ExternalNavbar from "../components/external-narbar.jsx";
import {getCookie} from "../utils/getCookie.js";

export default function LoginPage({ dashboardPath, heading }) {
    const navigate = useNavigate();
    const {accessToken, setAccessToken} = useAuth();
    const [form, setForm] = useState({username: "", password: ""});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (accessToken) {
            navigate(dashboardPath);
        }
    }, [accessToken]);

    const handleChange = (e) => {
        const {name, value} = e.target;
        setForm((prev) => ({ ...prev, [name]: value}));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        const res = await fetch("/api/login/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            credentials: "include",
            body: JSON.stringify(form),
        })

        const data = await res.json()
        setLoading(false);

        if (res.ok) {
            setAccessToken(data.access);
            navigate(dashboardPath);
        } else {
            setError(data.Error || "Login failed");
        }
    };

    return (
        <div
            className={"min-h-screen bg-cover bg-center bg-no-repeat flex flex-col font-sans"}
            style={{backgroundImage: 'url(/assets/register-background.jpg)'}}
        >
            {/* Navbar */}
            <ExternalNavbar />

            <div className={"flex flex-1 items-center justify-center px-4"}>
                <div className={"bg-white text-black rounded-xl shadow-xl w-full max-w-md p-8 space-y-4"}>
                    <h2 className={"text-2xl font-bold mb-6 text-center"}>{heading}</h2>
                    <form onSubmit={handleSubmit} className={"space-y-4"}>
                        <input
                            name="username"
                            value={form.username}
                            onChange={handleChange}
                            placeholder="Username"
                            className="w-full p-3 border border-gray-300 rounded"
                            required
                        />
                        <input
                            name="password"
                            type="password"
                            value={form.password}
                            onChange={handleChange}
                            placeholder="Password"
                            className="w-full p-3 border border-gray-300 rounded"
                            required
                        />
                        {error && <p className="text-red-500 text-sm">{error}</p>}
                        <button
                            type="submit"
                            className="w-full bg-blue-600 text-white py-3 rounded hover:bg-blue-700 transition"
                            disabled={loading}
                        >
                            {loading ? "Logging in..." : "Log In"}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    )
}