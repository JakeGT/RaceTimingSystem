import React from 'react';
import {BrowserRouter as Router, Routes, Route} from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import RegisterPage from './pages/RegisterPage.jsx'

function App() {
    return (
        <Router>
            <Routes>
                <Route path={"/"} element={<LandingPage />} />
                <Route path={"/runner-login"} element={<div>Runner Login</div>} />
                <Route path={"/organiser-login"} element={<div>Organiser Login</div>} />
                <Route path={"/register"} element={<RegisterPage />} />
            </Routes>
        </Router>
    )
}

export default App
