async function fetchQueueData() {
    try {
        const response = await fetch('get_queue_data/');
        if (response.ok) {
            const data = await response.json();
            updateQueueStats(data);
        }
    }
    catch (error) {
        console.error('Error fetching queue data:', error);
    }
}
