function updateDashboardStats(data) {
    const currentQueueLengthElement = document.querySelector('.current-queue-length');
    const estimatedWaitTimeElement = document.querySelector('.estimated-wait-time');
    const participantsTodayElement = document.querySelector('.participants-today');
    const statusElement = document.querySelector('.queue-status');

    if (currentQueueLengthElement) {
        currentQueueLengthElement.textContent = data.current_queue_length;
    }

    if (estimatedWaitTimeElement) {
        estimatedWaitTimeElement.textContent = data.estimated_wait_time + ' min';
    }

    if (participantsTodayElement) {
        participantsTodayElement.textContent = data.participants_today;
    }

    if (statusElement) {
        statusElement.textContent = data.status;
    }
}