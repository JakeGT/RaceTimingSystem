// MyRaces.jsx
import { useEffect, useState } from "react";
import { fetchWithAuth } from "../utils/fetchWithAuth";
import { useAuth } from "../context/AuthContext";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, SquarePen } from "lucide-react";

const ITEMS_PER_PAGE = 10;

const MyRaces = () => {
    const { accessToken, refreshAccessToken } = useAuth();
    const [races, setRaces] = useState([]);
    const [filtered, setFiltered] = useState([]);
    const [selectedRace, setSelectedRace] = useState(null);
    const [formState, setFormState] = useState({});
    const [search, setSearch] = useState("");
    const [sortKey, setSortKey] = useState("start_datetime");
    const [sortAsc, setSortAsc] = useState(true);
    const [page, setPage] = useState(1);

    useEffect(() => {
        const fetchRaces = async () => {
            const res = await fetchWithAuth("/api/races/my/", {}, accessToken, refreshAccessToken);
            if (res.ok) {
                const data = await res.json();
                setRaces(data);
            }
        };
        fetchRaces();
    }, [accessToken, refreshAccessToken]);

    useEffect(() => {
        let result = [...races];
        if (search) {
            result = result.filter((r) =>
                r.name.toLowerCase().includes(search.toLowerCase())
            );
        }
        result.sort((a, b) => {
            const aVal = sortKey === "name" ? a.name : new Date(a.start_datetime);
            const bVal = sortKey === "name" ? b.name : new Date(b.start_datetime);
            return sortAsc ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
        });
        setFiltered(result);
        setPage(1);
    }, [races, search, sortKey, sortAsc]);

    const paginated = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

    const openEditPanel = (race) => {
        setSelectedRace(race);
        setFormState(race);
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormState((prev) => ({ ...prev, [name]: value }));
    };

    const handleSave = async () => {
        const res = await fetchWithAuth(
            `/api/races/${selectedRace.id}/update/`,
            {
                method: "PATCH",
                body: JSON.stringify(formState),
            },
            accessToken,
            refreshAccessToken
        );
        if (res.ok) {
            const updated = await res.json();
            setRaces((prev) =>
                prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r))
            );
            setSelectedRace(null);
        }
    };

    const handleSort = (key) => {
        if (sortKey === key) {
            setSortAsc(!sortAsc);
        } else {
            setSortKey(key);
            setSortAsc(true);
        }
    };

    return (
        <div className="p-6">
            <div className="flex justify-between items-center mb-4">
                <h1 className="text-2xl font-bold">My Races</h1>
                <input
                    type="text"
                    placeholder="Search..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="border px-3 py-1 rounded"
                />
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full bg-white rounded-lg shadow">
                    <thead className="bg-gray-800 text-white text-left">
                    <tr>
                        <th className="p-3 text-sm font-semibold cursor-pointer" onClick={() => handleSort("name")}>Name {sortKey === "name" && (sortAsc ? <ChevronUp className="inline w-4 h-4" /> : <ChevronDown className="inline w-4 h-4" />)}</th>
                        <th className="p-3 text-sm font-semibold cursor-pointer" onClick={() => handleSort("start_datetime")}>Start {sortKey === "start_datetime" && (sortAsc ? <ChevronUp className="inline w-4 h-4" /> : <ChevronDown className="inline w-4 h-4" />)}</th>
                        <th className="p-3 text-sm font-semibold">Location</th>
                        <th className="p-3 text-sm font-semibold">Category</th>
                        <th className="p-3 text-sm font-semibold">Status</th>
                        <th className="p-3 text-sm font-semibold text-right">Actions</th>
                    </tr>
                    </thead>
                    <tbody>
                    {paginated.map((race) => (
                        <tr key={race.id} className="border-t hover:bg-gray-50">
                            <td className="p-3">{race.name}</td>
                            <td className="p-3">{new Date(race.start_datetime).toLocaleString()}</td>
                            <td className="p-3">{race.address}</td>
                            <td className="p-3">{race.race_category?.name || "-"}</td>
                            <td className="p-3">
                                {race.is_completed ? (
                                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Completed</span>
                                ) : (
                                    <span className="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full">Upcoming</span>
                                )}
                            </td>
                            <td className="p-3 text-right">
                                <button
                                    onClick={() => openEditPanel(race)}
                                    className="text-indigo-600 hover:underline cursor-pointer"
                                >
                                    <SquarePen size={15}/>
                                </button>
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-end items-center mt-4 gap-2">
                {Array.from({ length: Math.ceil(filtered.length / ITEMS_PER_PAGE) }).map((_, i) => (
                    <button
                        key={i}
                        onClick={() => setPage(i + 1)}
                        className={`px-3 py-1 rounded ${page === i + 1 ? "bg-indigo-600 text-white" : "bg-gray-200"}`}
                    >
                        {i + 1}
                    </button>
                ))}
            </div>

            <AnimatePresence>
                {selectedRace && (
                    <>
                        <motion.div
                            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setSelectedRace(null)}
                        />
                        <motion.div
                            className="fixed right-0 top-0 w-full max-w-md h-full bg-gray-50 shadow-xl p-6 z-50 overflow-y-auto rounded-l-xl"
                            initial={{ x: "100%" }}
                            animate={{ x: 0 }}
                            exit={{ x: "100%" }}
                            transition={{ type: "tween", duration: 0.3 }}
                        >
                            <h2 className="text-xl font-semibold mb-4">Edit Race</h2>
                            <div className="space-y-4">
                                <input type="text" name="name" value={formState.name || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Race Name" />
                                <input type="datetime-local" name="start_datetime" value={formState.start_datetime ? new Date(formState.start_datetime).toISOString().slice(0, 16) : ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" />
                                <input type="text" name="address" value={formState.address || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Address" />
                                <input type="url" name="organiser_website" value={formState.organiser_website || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Organiser Website" />
                                <input type="text" name="social_twitter" value={formState.social_twitter || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Twitter URL" />
                                <input type="text" name="social_instagram" value={formState.social_instagram || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Instagram URL" />
                                <input type="text" name="social_facebook" value={formState.social_facebook || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="Facebook URL" />
                                <input type="url" name="stream_url" value={formState.stream_url || ""} onChange={handleChange} className="w-full bg-gray-100 border px-3 py-2 rounded" placeholder="YouTube Stream URL" />
                                <div className="flex justify-end mt-6 gap-2">
                                    <button onClick={() => setSelectedRace(null)} className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">Cancel</button>
                                    <button onClick={handleSave} className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">Save</button>
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};

export default MyRaces;
