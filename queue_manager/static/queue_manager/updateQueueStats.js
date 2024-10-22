function updateQueueStats(data) {
    if (Array.isArray(data)) {
        data.forEach(queue => {
            console.log('Processing queue:', queue);
            const queueElement = document.getElementById(`queue-${queue.id}`);
            if (!queueElement) {
                console.error(`No element found for queue ID: ${queue.id}`);
                return;
            }
            queueElement.querySelector('.stat-value.position').textContent = queue.position;
            queueElement.querySelector('.stat-value.participant-count').textContent = queue.participant_count;
            queueElement.querySelector('.stat-value.status').textContent = queue.status;
        });
    } else {
        console.error('Unexpected data structure:', data);
    }
}
