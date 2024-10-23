async function fetchDashboardData(queueId) {
    try {
        const response = await fetch(`/get_dashboard_data/${queueId}/`);
        if (response.ok) {
            const data = await response.json();
            updateDashboardStats(data);
        } else {
            console.error('Error fetching dashboard queue data:', response.statusText);
        }
    } catch (error) {
        console.error('Error fetching dashboard queue data:', error);
    }
}