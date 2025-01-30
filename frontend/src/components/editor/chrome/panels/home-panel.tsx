import { useState } from "react";

export default function HomePanel() {
    const searchParams = new URLSearchParams(window.location.href);
    const name = searchParams.get('name') || '';
    const id = searchParams.get('id') || '';
    const [error, setError] = useState<string | null>(null);

    const handleConfirm = () => {
        console.log("handleConfirm", id, name);
        const notebookUrl = "http://localhost:3000/dashboard/projects/"
        try {
            window.location.replace(notebookUrl);
        } catch (e) {
            setError('Failed to load notebook. Please try again later.');
        }
    };

    if (error) {
        return <div>
            <h1>404 - Notebook Not Found</h1>
            <p>{error}</p>
        </div>;
    }


    return (
        <div>
            <div className="bg-white p-6 rounded-lg shadow-lg">
                <h2 className="text-lg font-semibold mb-4">Return to Dashboard?</h2>
                <p className="mb-4">Are you sure you want to return to the dashboard? Any unsaved changes will be lost.</p>
                <div className="flex justify-end gap-4">
                    {/* <button
                        onClick={handleCancel}
                        className="px-4 py-2 border rounded hover:bg-gray-100"
                    >
                        Cancel
                    </button> */}
                    <button
                        onClick={handleConfirm}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                    >
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    );
}