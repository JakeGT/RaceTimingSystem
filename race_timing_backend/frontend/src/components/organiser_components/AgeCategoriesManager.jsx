import {useAuth} from "../../context/AuthContext.jsx";

export default function AgeCategoriesManager() {
    const { accessToken, refreshAccessToken } = useAuth();


    return (
        <h1>AgeCategoriesManager</h1>
    )
}