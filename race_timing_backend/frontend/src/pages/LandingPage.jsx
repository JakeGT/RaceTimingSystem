import React, { useEffect } from "react";
import {useNavigate} from "react-router-dom";
import {motion, useAnimation} from "framer-motion";
import {useInView} from "react-intersection-observer";
import ExternalNavbar from "../components/external-narbar.jsx";


const infographics = [
    {
        title: "",
        description: "",
        image: "/assets/infographic-1.jpg"
    },
    {
        title: "",
        description: "",
        image: "/assets/infographic-2.jpg"
    },
    {
        title: "",
        description: "",
        image: "/assets/infographic-3.jpg"
    },
]

const FadeInSection = ({ children, delay = 0 }) => {
    const controls = useAnimation();
    const [ref, inView] = useInView({ triggerOnce: true, threshold: 0.2 });

    useEffect(() => {
        if (inView) {
        controls.start({ opacity: 1, y: 0 });
        }
    }, [controls, inView]);

    return (
        <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 50 }}
        animate={controls}
          transition={{ duration: 0.8, delay }}
        className="w-full"
        >
            {children}
        </motion.div>
    );
};

export default function LandingPage() {
    const navigate = useNavigate()

    return (
        <div className={"font-sans bg-gray-900 text-white min-h-screen"}>
            {/*Navigation Bar*/}
            <ExternalNavbar />



            {/* Hero Section */}
            <div className="flex flex-col items-center justify-center h-screen px-4 text-center bg-cover bg-center bg-no-repeat" style={{ backgroundImage: 'url(/assets/hero-background.jpg'}}>
                <h1 className="text-5xl md:text-7xl font-bold mb-6 pt-32">Race Timing System</h1>
                    <p className="text-lg md:text-2xl mb-10 max-w-xl">
                        Accurate real-time race timing powered by AI-driven bib detection and tracking.
                    </p>
                    <div className="flex flex-col md:flex-row gap-6">
                        <button
                            onClick={() => navigate("/runner-login")}
                            className="px-6 py-3 text-lg font-medium bg-blue-600 hover:bg-blue-700 rounded-xl shadow-md transition duration-300"
                        >
                            Login as Runner
                        </button>
                        <button
                            onClick={() => navigate("/organiser-login")}
                            className="px-6 py-3 text-lg font-medium border border-white hover:bg-white hover:text-black rounded-xl shadow-md transition duration-300"
                        >
                            Login as Organiser
                        </button>
                    </div>
                <p className={"text-sm md:text-base py-4"}>
                    <button
                        onClick={() => navigate("/register")}
                        className={"hover:underline font-medium cursor-pointer"}
                    >
                        Don't have an account?{" "}Register here
                    </button>
                </p>
            </div>
            <div className="max-w-6xl mx-auto px-4 py-20 space-y-16">
                {infographics.map((info, i) => (
                    <FadeInSection key={i} delay={i * 0.3}>
                        <div
                            className="bg-cover bg-center rounded-2xl shadow-lg p-8 text-white"
                            style={{
                                backgroundImage: `url(${info.image})`
                            }}
                        >
                            <div className="backdrop-blur-sm bg-black/50 rounded-xl p-6">
                                <h2 className="text-2xl font-semibold mb-2">{info.title}</h2>
                                <p>
                                    {info.description}
                                </p>
                            </div>
                        </div>
                    </FadeInSection>
                ))}
            </div>
        </div>
    )
}