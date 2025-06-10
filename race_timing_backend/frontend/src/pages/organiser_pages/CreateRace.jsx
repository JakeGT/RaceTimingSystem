import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import {useAuth} from "../../context/AuthContext.jsx";
import {fetchWithAuth} from "../../utils/fetchWithAuth.js";


export default function CreateRace() {
    const navigate = useNavigate()
    const {accessToken, refreshAccessToken} = useAuth()

    const [formData, setFormData] = useState({
        race_name: "",
        start_datetime_iso: "",
        race_location: "",
        latitude: "",
        longitude: "",
        organiser_website: "",
        social_twitter: "",
        social_instagram: "",
        social_facebook: "",
        youtube_stream_url: "",
        race_category: "",
        participant_categories: [],
    });

    const [categories, setCategories] = useState({
        race_categories: [],
        participant_categories: [],
    })

    const [error, setError] = useState(null);
    const [success, setSuccess] = useState('');

    useEffect(() => {
        const fetchCategories = async() => {
            const res = await fetchWithAuth(
                "/api/categories/",
                { method : "GET" },
                accessToken,
                refreshAccessToken
            );
            if (res.ok) {
                const data = await res.json();
                setCategories(data);
            } else {
                console.error("Failed to load category options");
            }
        };

        fetchCategories();
    }, [accessToken, refreshAccessToken]);

    const handleChange = (e) => {
        const {name, value} = e.target;
        setFormData((prev) => ({
            ...prev,
            [name]: value,
        }));
    };

    const handleCheckboxChange = (e) => {
        const {value, checked} = e.target;
        setFormData((prev) => {
            const current = new Set(prev.participant_categories);
            checked ? current.add(value) : current.delete(value);
            return {
                ...prev,
                participant_categories: Array.form(current)
            }
        })
    };

    const handleDateChange = (e) => {
        const localDate = e.target.value;
        try {
            const isoDate = new Date(localDate).toISOString();
            setFormData((prev) => ({
                ...prev,
                start_datetime_iso: isoDate,
            }));
        } catch {
            setError("Invalid date format.")
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null)
        setSuccess('')

        const res = await fetchWithAuth(
            "/api/create-race/",
            {
                method: "POST",
                body: JSON.stringify(formData),
            },
            accessToken,
            refreshAccessToken
        );

        if (res.ok) {
            const data = await res.json();
            setSuccess("Race created successfully!");
            navigate(`/organiser/dashboard/race/`);
        } else {
            const errData = await res.json();
            setError(errData?.error || "Failed to create race.");
        }
    };


    return (
        <div className={"max-w-2xl mx-auto bg-white shadow-md p-6 rounded-md"}>
            <h1 className={"text-2xl font-semibold mb-4"}>Create Race</h1>
            {error && <p className={"text-red-500 mb-2"}>{error}</p>}
            {success && <p className={"text-green-600 mb-2"}>{success}</p>}

            <form onSubmit={handleSubmit} className={"space-y-4"}>
                <div>
                    <h2 className={"text-lg font-semibold mb-2"}>Race Info</h2>
                    <div className={"space-y-3"}>
                        <input
                            type={"text"}
                            name={"race_name"}
                            placeholder={"Race Name"}
                            value={formData.race_name}
                            onChange={handleChange}
                            required
                            className={"w-full border px-3 py-2 rounded"}
                        />
                        <input
                            type={"datetime-local"}
                            name={"start_datetime_local"}
                            onChange={handleDateChange}
                            required
                            className={"w-full border px-3 py-2 rounded"}
                        />
                    </div>
                </div>
                <div>
                    <h2 className={"text-lg font-semibold mb-2"}>Location</h2>
                    <div className={"space-y-3"}>
                        <input
                            type={"text"}
                            name={"race_location"}
                            placeholder={"Race Location"}
                            value={formData.race_location}
                            onChange={handleChange}
                            className={"w-full border px-3 py-2 rounded"}
                        />
                        <div className="flex gap-4">
                        <input
                            type="text"
                            name="latitude"
                            placeholder="Latitude"
                            value={formData.latitude}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />
                        <input
                            type="text"
                            name="longitude"
                            placeholder="Longitude"
                            value={formData.longitude}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />
                        </div>
                    </div>
                </div>
                <div>
                    <h2 className={"text-lg font-semibold mb-2"}>Categories</h2>
                    <div className={"space-y-3"}>
                        <select
                            name="race_category"
                            value={formData.race_category}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        >
                            <option value="">Select Race Category</option>
                            {categories.race_categories.map((cat) => (
                                <option key={cat.id} value={cat.id}>
                                    {cat.name}
                                </option>
                            ))}
                        </select>

                        <fieldset className={"border rounded p-3"}>
                            <legend className={"font-medium mb-2"}>Participant Categories</legend>
                            <div className={"grid grid-cols-2 gap-2"}>
                                {categories.participant_categories.map((cat) => (
                                    <label key={cat.id} className={"flex items-center gap-2"}>
                                        <input
                                            type={"checkbox"}
                                            value={cat.id}
                                            checked={formData.participant_categories.includes(String(cat.id))}
                                            onChange={handleCheckboxChange}
                                            className={"accent-blue-600"}
                                        />
                                        {cat.name}
                                    </label>
                                ))}
                            </div>
                        </fieldset>
                    </div>
                </div>
                <div>
                    <h2 className={"text-lg font-semibold mb-2"}>Organiser and Social</h2>
                    <div className={"space-y-3"}>
                        <input
                            type="url"
                            name="organiser_website"
                            placeholder="Organiser Website"
                            value={formData.organiser_website}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />

                        <input
                            type="text"
                            name="social_twitter"
                            placeholder="Twitter URL"
                            value={formData.social_twitter}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />

                        <input
                            type="text"
                            name="social_instagram"
                            placeholder="Instagram URL"
                            value={formData.social_instagram}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />

                        <input
                            type="text"
                            name="social_facebook"
                            placeholder="Facebook URL"
                            value={formData.social_facebook}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />

                        <input
                            type="url"
                            name="youtube_stream_url"
                            placeholder="YouTube Stream URL"
                            value={formData.youtube_stream_url}
                            onChange={handleChange}
                            className="w-full border px-3 py-2 rounded"
                        />
                    </div>
                </div>
                <button
                    type="submit"
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded w-full transition duration-300"
                >
                    Create Race
                </button>
            </form>
        </div>
    )
}