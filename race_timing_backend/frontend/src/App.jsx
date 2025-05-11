import React from 'react';
import {BrowserRouter as Router, Routes, Route} from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import RegisterPage from './pages/RegisterPage.jsx'
import LoginPage from "./pages/LoginPage.jsx";
import OrganiserDashboard from "./pages/OrganiserDashboard.jsx";
import CreateRace from "./pages/CreateRace.jsx";
import ModifyResults from "./pages/ModifyResults.jsx";
import MyRaces from "./pages/MyRaces.jsx";

function App() {
    return (
        <Router>
            <Routes>
                <Route path={"/"} element={<LandingPage />} />
                <Route path={"/runner-login"} element={<LoginPage dashboardPath={"/runner/dashboard"} heading={"Runner Log In"} />} />
                <Route path={"/organiser-login"} element={<LoginPage dashboardPath={"/organiser/dashboard"} heading={"Organiser Log In"} />} />
                <Route path={"/register"} element={<RegisterPage />} />
                <Route path={"/login"} element={<div>Login Redirect</div>} />
                <Route path={"/runner/dashboard"} element={<div>Runner Dashboard</div>} />
                <Route path={"/organiser/dashboard"} element={<OrganiserDashboard />}>
                    <Route index element={<h1>HomePage</h1>} />
                    <Route path={"/organiser/dashboard/create-race"} element={<CreateRace />} />
                    <Route path={"/organiser/dashboard/results/modify"} element={<ModifyResults />} />
                    <Route path={"/organiser/dashboard/race"} element={<MyRaces />} />
                </Route>
            </Routes>
        </Router>
    )
}

export default App
