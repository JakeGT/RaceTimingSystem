import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ExternalNavbar from "../components/external-narbar.jsx";
import {useAuth} from "../context/AuthContext.jsx";

export default function RegisterPage() {
    const navigate = useNavigate();
    const {setAccessToken} = useAuth();
    const [form, setForm] = useState({
        username: '',
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        is_runner: false,
        is_organiser: false,
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [registered, setRegistered] = useState(false);
    const [roles, setRoles] = useState({is_runner: false, is_organiser: false})

    const handleChange = (e) => {
        const {name, value, type, checked} = e.target;
        setForm({ ...form, [name]: type==="checkbox" ? checked:value});
    };

    const validate = () => {
        const newErrors = {};
        if (!form.username.trim()) newErrors.username = "Username is required";
        if (!form.email.includes("@")) newErrors.email = "Enter a valid email address.";
        if (form.password.length < 6) newErrors.password = "Password must be at least 6 characters";
        if (!form.last_name.trim()) newErrors.last_name = "Last name is required";
        if (!form.first_name.trim()) newErrors.first_name = "First name is requried";
        if (!form.is_runner && !form.is_organiser) newErrors.role = "Select at least one role";
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    }

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validate()) return;
        setLoading(true);

        const res = await fetch("/api/register/", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            credentials: "include",
            body: JSON.stringify(form),
        });

        const data = await res.json();
        setLoading(false);

        if (res.ok) {
            setAccessToken(data.access)
            setRoles({is_runner: data.is_runner, is_organiser: data.is_organiser});

            if (data.is_runner && data.is_organiser) {
                setRegistered(true);
            } else if (data.is_organiser) {
                navigate("/organiser/dashboard");
            } else if (data.is_runner) {
                navigate("/runner/dashboard");
            }
        } else {
            alert("Registration failed: " + JSON.stringify(data));
        }
    };

    const handleContinue = (role) => {
        if (role === "runner") navigate("/runner/dashboard");
        if (role === "organiser") navigate("organiser/dashboard");
    }

    return (
        <div
            className={"min-h-screen bg-cover bg-center bg-no-repeat flex flex-col font-sans"}
            style={{backgroundImage: 'url(/assets/register-background.jpg)'}}
        >
            {/* NavBar */}
            <ExternalNavbar />

            {/* Form Container */}

            <div className={"flex flex-1 items-center justify-center px-4"}>
                <div className={"bg-white text-black rounded-xl shadow-xl w-full max-w-md p-8 space-y-4"}>
                    {loading ? (
                        <div className="flex items-center justify-center h-40">
                            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                        </div>
                    ) : registered ? (
                        <div className={"flex flex-col items-center space-y-4"}>
                            <p className={"text-center font-semibold"}>Registration successful!</p>
                            {roles.is_runner && (
                                <button
                                    className={"w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 transition duration-300"}
                                    onClick={() => handleContinue("runner")}
                                >
                                    Continue as Runner
                                </button>
                            )}
                            {roles.is_organiser && (
                                <button
                                    className={"w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 transition duration-300"}
                                    onClick={() => handleContinue("organiser")}
                                >
                                    Continue as Organiser
                                </button>
                            )}
                        </div>
                    ) : (
                        <form
                            onSubmit={handleSubmit}
                            className={"space-y-4"}
                        >
                            <h2 className={"text-2xl font-bold text-center mb-4"}>Create Your Account</h2>

                            <div className={"flex gap-2"}>
                                <div className={"w-1/2"}>
                                    <input
                                type={"text"}
                                name={"first_name"}
                                placeholder={"First name"}
                                value={form.first_name}
                                onChange={handleChange}
                                className={"w-full border rounded px-3 py-2"}
                            />
                            {errors.first_name && <p className={"text-red-500 text-sm"}>{errors.first_name}</p>}
                                </div>
                                <div className={"w-1/2"}>
                            <input
                                type={"text"}
                                name={"last_name"}
                                placeholder={"Last name"}
                                value={form.last_name}
                                onChange={handleChange}
                                className={"w-full border rounded px-3 py-2"}
                            />
                            {errors.last_name && <p className={"text-red-500 text-sm"}>{errors.last_name}</p>}
                                </div>
                            </div>

                            <input
                                type={"text"}
                                name={"username"}
                                placeholder={"Username"}
                                value={form.username}
                                onChange={handleChange}
                                className={"w-full border rounded px-3 py-2"}
                            />
                            {errors.username && <p className={"text-red-500 text-sm"}>{errors.username}</p>}
                            <input
                                type={"email"}
                                name={"email"}
                                placeholder={"Email"}
                                value={form.email}
                                onChange={handleChange}
                                className={"w-full border rounded px-3 py-2"}
                            />
                            {errors.email && <p className={"text-red-500 text-sm"}>{errors.email}</p>}
                            <input
                                type={"password"}
                                name={"password"}
                                placeholder={"Password"}
                                value={form.password}
                                onChange={handleChange}
                                className={"w-full border rounded px-3 py-2"}
                            />
                            {errors.password && <p className={"text-red-500 text-sm"}>{errors.password}</p>}

                            <div className={"flex flex-col md:flex-row md:items-center md:gap-6"}>
                                <label className={"flex items-center"}>
                                    <input
                                        type={"checkbox"}
                                        name={"is_runner"}
                                        checked={form.is_runner}
                                        onChange={handleChange}
                                        className={"mr-2"}
                                    />
                                    Register as Runner
                                </label>
                                <label className={"flex items-center"}>
                                    <input
                                        type={"checkbox"}
                                        name={"is_organiser"}
                                        checked={form.is_organiser}
                                        onChange={handleChange}
                                        className={"mr-2"}
                                    />
                                    Register as Organiser
                                </label>
                                {errors.role && <p className={"text-red-500 text-sm"}>{errors.role}</p>}
                            </div>
                            <button
                                type={"submit"}
                                className={"w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 transition duration-300 cursor-pointer"}
                            >
                                Register
                            </button>
                        </form>
                    )}
                </div>
            </div>
        </div>
    )
}