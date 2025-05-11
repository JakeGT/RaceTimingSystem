import {Link, useLocation, useNavigate} from "react-router-dom";
import {useState} from "react";
import {
    LayoutDashboard,
    PlusCircle,
    ListOrdered,
    ChevronDown,
    ChevronUp,
    X,
    Flag,
} from "lucide-react"
import {motion, AnimatePresence} from "framer-motion"
const Sidebar = ({isOpen, onClose}) => {
    const location = useLocation()
    const navigate = useNavigate()
    const [resultsOpen, setResultsOpen] = useState(false);

    const navItemClass = (path) =>
    `flex items-center gap-3 px-4 py-2 rounded-md transition-colors duration-200 ${
      location.pathname === path
        ? "bg-gray-700 border-l-4 border-blue-500 text-white"
        : "hover:bg-gray-700 text-gray-300"
    }`;

    return (
        <>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        className = {"fixed inset-0 z-30 bg-black bg-opacity-50 lg:hidden"}
                        initial = {{opacity: 0}}
                        animate = {{opacity: 1}}
                        exit = {{opacity:0}}
                        onclick={onClose}
                    />
                )}
            </AnimatePresence>

            <AnimatePresence>
                {(isOpen || window.innerWidth >= 1024) && (
                    <motion.div
                        key={"sidebar"}
                        initial={{x: -300}}
                        animate={{x: 0}}
                        exit={{x: -300}}
                        transition={{type: "tween", duration: 0.3}}
                        className={"fixed, lg:static z-40 w-64 h-full bg-gray-900 text-gray-300 flex flex-col p-4"}
                    >
                        <div className={"flex items-center justify-between mb-6"}>
                            <Link to={"/organiser/dashboard/"} className={"text-2xl font-semibold flex items-center gap-2 cursor-pointer"}><LayoutDashboard size={24} /> Dashboard</Link>
                            <button className="lg:hidden text-gray-400" onClick={onClose}>
                                <X size={24} />
                            </button>
                        </div>
                        <nav className={"flex flex-col gap-1"}>
                            <Link to="/organiser/dashboard/race" className={navItemClass("/organiser/dashboard/race")}> <Flag size={20} />My Races</Link>
                            <Link to="/organiser/dashboard/create-race" className={navItemClass("/organiser/dashboard/create-race")}> <PlusCircle size={20} />Create Race</Link>

                            <button
                                onClick={() => setResultsOpen((prev) => !prev)}
                                className={"flex items-center justify-between px-4 py-2 rounded-md hover:bg-gray-700 transition-colors duration-200"}
                            >
                                <span className={"flex items-center gap-3 text-gray-300"}>
                                    <ListOrdered size={20} /> Results
                                </span>
                                {resultsOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </button>

                            <AnimatePresence initial={false}>
                                {resultsOpen && (
                                    <motion.div
                                        initial={{height: 0, opacity: 0}}
                                        animate={{height: 'auto', opacity: 1}}
                                        exit={{height:0, opacity: 0}}
                                        transition={{duration: 0.3, ease: "easeInOut"}}
                                        className={"overflow-hidden"}
                                    >
                                        <div className={"ml-6 mt-1 flex flex-col gap-1"}>
                                            <Link
                                                to={"/organiser/dashboard/results/modify"}
                                                className={navItemClass("/organiser/dashboard/results/modify")}
                                            >
                                                Modify Results
                                            </Link>
                                        </div>

                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </nav>
                    </motion.div>
                )}
            </AnimatePresence>

        </>
    )
}

export default Sidebar