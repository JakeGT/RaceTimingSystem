import {useNavigate} from "react-router-dom"
import {useState} from "react";
import {Menu, X} from "lucide-react"
import {motion, AnimatePresence} from "framer-motion"

export default function ExternalNavbar() {
    const navigate = useNavigate()
    const [menuOpen, setMenuOpen] = useState(false)

    return (
        <nav className={"text-white bg-black/80 backdrop-blur-sm fixed top-0 w-full z-50 px-4 py-3 flex items-center justify-between shadow-md"}>
            <div className={"text-xl font-bold cursor-pointer"} onClick={() => navigate("/")}>RaceTiming</div>

            {/* Desktop Menu */}
            <div className={"space-x-4 hidden md:flex items-center"}>
                <button
                    onClick={() => navigate("/register")}
                    className={"px-4 py-2 rounded-full bg-blue-600 hover:bg-blue-700 transition duration-300 font-bold cursor-pointer"}
                >
                    Register
                </button>
                <button
                    className={"px-4 py-2 rounded-full hover:bg-gray-700 transition duration-300 cursor-pointer"}
                    onClick={() => {
                        navigate("/login")
                    }}
                >
                    Log In
                </button>
                <div className={"relative"}>
                    <button
                        className={"p-2 rounded-full hover:bg-gray-700 transition duration-300 cursor-pointer"}
                        onClick={() => setMenuOpen(!menuOpen)}
                    >
                        {menuOpen ? <X size={24} /> : <Menu size={24} />}
                    </button>
                    <AnimatePresence>
                        {menuOpen && (
                        <motion.div
                            initial={{opacity :0, scale: 0.95}}
                            animate={{opacity: 1, scale: 1}}
                            exit={{opacity: 0, scale: 0.95}}
                            transition={{duration: 0.2}}
                            className={"absolute right-0 mt-2 bg-gray-800 rounded shadow-lg py-2 w-48"}
                        >
                            <button
                                className={"block px-4 py-2 hover:bg-gray-700 w-full text-left cursor-pointer"}
                                onClick={() => {
                                    setMenuOpen(false);
                                    navigate("/help");
                                }}
                            >
                                Help
                            </button>
                            <button
                                className={"block px-4 py-2 hover:bg-gray-700 w-full text-left cursor-pointer"}
                                onClick={() => {
                                    setMenuOpen(false);
                                    navigate("/learn");
                                }}
                            >
                                Learn
                            </button>
                        </motion.div>
                    )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Mobile Menu */}
            <div className={"md:hidden"}>
                <button
                    onClick={() => setMenuOpen(!menuOpen)}
                    className={"p-2 rounded-full"}
                >
                    {menuOpen ? <X size={24} /> : <Menu size={24} />}
                </button>
            </div>

            <AnimatePresence>
                {menuOpen && (
                    <motion.div
                        initial={{opacity :0, y: -10}}
                        animate={{opacity: 1, y: 0}}
                        exit={{opacity: 0, y: -10}}
                        transition={{duration: 0.2}}
                        className={"absolute top-16 right-4 bg-gray-800 rounded shadow-lg py-4 w-64 flex flex-col space-y-2 md:hidden"}
                    >
                        <button
                            onClick={() => navigate("/register")}
                            className={"px-4 py-3 w-full text-left"}
                        >
                            Register
                        </button>
                        <button
                            className={"px-4 py-3 w-full text-left"}
                            onClick={() => {
                                navigate("/login")
                            }}
                        >
                            Log In
                        </button>
                        <button
                            className={"px-4 py-3 w-full text-left"}
                            onClick={() => {
                                setMenuOpen(false);
                                navigate("/help");
                            }}
                        >
                            Help
                        </button>
                        <button
                            className={"px-4 py-3 w-full text-left"}
                            onClick={() => {
                                setMenuOpen(false);
                                navigate("/learn");
                            }}
                        >
                            Learn
                            </button>

                    </motion.div>
                )}
            </AnimatePresence>
        </nav>
    )
}