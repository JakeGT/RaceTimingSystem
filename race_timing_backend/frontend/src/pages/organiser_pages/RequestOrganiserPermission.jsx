import { useEffect, useState} from 'react';
import { fetchWithAuth } from "../../utils/fetchWithAuth"
import { useAuth } from "../../context/AuthContext"

const RequestOrganiserPermission = ({race, closeComponent}) => {
    const {accessToken, refreshAccessToken} = useAuth();
    const [message, setMessage] = useState("");
    const [existingApplication, setExistingApplication] = useState(null);

    useEffect(() => {
        const fetchApplication = async() => {
            const res = await fetchWithAuth(
                `/api/races/${race.id}/check-organiser-application/`,
                {
                    method: "GET"
                },
                accessToken,
                refreshAccessToken
            )
            if (res.ok) {
                const data = await res.json();
                console.log(data)
                if (data.exists === true) {
                    setExistingApplication(data.message)
                }
            }
        }
        fetchApplication()
    })

    useEffect(() => {
        setMessage("")
    }, [race]);
    const handleSend = async () => {
        {/*TODO: Loading Spinner*/}
        const res = await fetchWithAuth(
            `/api/races/${race.id}/request-organiser-permission/`,
            {
                method: "POST",
                body: JSON.stringify({"message": message})
            },
            accessToken,
            refreshAccessToken
        )
        if (res.ok) {
            closeComponent()
        }
    }

    return (
        <div className={"bg-white p-6 rounded shadow-md w-full max-w-md"}>
            { existingApplication ? (
                    <>
                        <h2 className={"text-xl font-semibold"}>Application Already Submitted</h2>
                        <h3 className={"text-m font-bold text-gray-500 mb-4"}>{race.name}</h3>
                        <p className={"w-full bg-gray-100 border px-3 py-2 rounded mb-4"}>{existingApplication}</p>
                        <button onClick={() => closeComponent()} className={"px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"}>Close</button>
                    </>
                ) : (
                    <>
                        <h2 className={"text-xl font-semibold"}>Request Organiser Permission</h2>
                        <h3 className={"text-m font-bold text-gray-500 mb-4"}>{race.name}</h3>
                        <div className={"space-y-4"}>
                            <input type="text" name="message" className={"w-full bg-gray-100 border px-3 py-2 rounded"} placeholder="Enter a message to request permission..." onChange={e => setMessage(e.target.value)}/>
                            <div className={"flex justify-end mt-6 gap-2"}>
                                <button onClick={() => closeComponent()} className={"px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"}>Cancel</button>
                                <button onClick={handleSend} className={"px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"}>Send</button>
                            </div>
                        </div>
                    </>

                )
            }

        </div>
    )
}

export default RequestOrganiserPermission