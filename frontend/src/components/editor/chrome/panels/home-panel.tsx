import { useState } from "react";

export default function HomePanel() {
    const url = new URL(window.location.href);
    const name = url.searchParams.get('file') || '';
    const id = url.searchParams.get('id') || '';
    const notebook_id = url.searchParams.get('notebook_id') || '';
    const [error, setError] = useState<string | null>(null);
    const isDev = process.env.NODE_ENV === "development";

    const handleConfirm = () => {
        console.log("handleConfirm", id, name, notebook_id);

        // notebook/d3593113-a04d-43f2-a6d6-491fc14971a1/settings?name=posthog-recipe.py
        
        const notebookUrl = isDev ? 
            `http://localhost:3000/dashboard/notebook/${notebook_id}/settings?name=${name}` 
            :
            `https://trycosmic.ai/dashboard/notebook/${notebook_id}/settings?name=${name}`;

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