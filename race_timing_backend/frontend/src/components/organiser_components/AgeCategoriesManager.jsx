import {useAuth} from "../../context/AuthContext.jsx";
import {useState} from "react";

export default function AgeCategoriesManager( {ageCategoryData, setAgeCategoryData} ) {
    const { accessToken, refreshAccessToken } = useAuth();

    /**
     *
     *  const [ageCategoryData, setAgeCategoryData] = useState({
     *      "AgeCategoryName1": {min_age: 18, max_age: 24, etc...},
     *      "AgeCategoryName2": {min_age: 25, max_age: 31, etc...},
     *  })
     *
     *
     * **/


    return (
        <h1>AgeCategoriesManager</h1>
    )
}