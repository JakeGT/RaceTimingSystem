import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function RegisterPage() {
    const navigate = useNavigate();
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

        const res = await fetch("/api/register/", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(form),
        });
        if (res.ok) {
            navigate("/login");
        } else {
            const data = await res.json();
            alert("Registration failed: " + JSON.stringify(data))
        }
    };

    return (
        <div
            className={"min-h-screen bg-cover bg-center bg-no-repeat flex flex-col font-sans"}
            style={{backgroundImage: 'url(/assets/register-background.jpg)'}}
        >
            {/* NavBar */}
            <nav className={"text-white bg-black/80 backdrop-blur-sm fixed top-0 w-full z-50 px-4 py-3 flex items-center justify-between shadow-md"}>
                <div className={"text-xl font-bold cursor-pointer"} onClick={() => navigate("/")}>RaceTiming</div>
                <div className={"space-x-4 hidden md:flex"}>
                    <button
                        onClick={() => navigate("/register")}
                        className={"px-4 py-2 rounded-full bg-blue-600 hover:bg-blue-700 transition font-bold"}
                    >
                        Register
                    </button>
                    <div className={"relative group"}>
                        <button className={"px-4 py-2 rounded-full bg-gray-700 hover:bg-gray-600 transition"}>Menu</button>
                        <div className={"absolute right-0 mt-0 bg-gray-800 rounded shadow-lg hidden group-hover:block"}>
                            <button className={"block px-4 py-2 hover:bg-gray-700 w-full text-left"}>Help</button>
                            <button className={"block px-4 py-2 hover:bg-gray-700 w-full text-left"}>Learn</button>
                        </div>
                    </div>
                </div>
            </nav>

            <div className={"flex flex-1 items-center justify-center px-4"}>
                <form
                    onSubmit={handleSubmit}
                    className={"bg-white text-black rounded-xl shadow-xl w-full max-w-md p-8 space-y-4"}
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
            </div>
        </div>
    )
}