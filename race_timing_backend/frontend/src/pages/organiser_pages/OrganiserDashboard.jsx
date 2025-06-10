import Sidebar from "../../components/Sidebar.jsx";
import {Outlet} from "react-router-dom"
import {useState} from "react";
import {Menu} from "lucide-react"


export default function OrganiserDashboard() {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    return (
        <div className={"flex h-screen overflow-hidden"}>
            <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
            <div className={"flex-1 flex flex-col"}>
                <header className="bg-gray-100 shadow px-4 py-3 flex items-center lg:hidden">
                    <button onClick={() => setSidebarOpen(true)} className="text-gray-600">
                        <Menu size={24} />
                    </button>
                    <h1 className="ml-4 text-xl font-semibold">Organiser Panel</h1>
                </header>
                <main className={"flex-1 bg-gray-100 p-6 overflow-y-auto"}>
                    <Outlet />
                </main>
            </div>
        </div>
    )
}