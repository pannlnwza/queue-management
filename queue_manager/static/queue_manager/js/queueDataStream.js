const combinedEventSource = new EventSource('/api/data-stream/');

combinedEventSource.onmessage = function (event) {
    const data = JSON.parse(event.data);

    data.queues.forEach(queue => {
        const statusElement = document.getElementById(`status-${queue.id}`);
        const status = queue.status.toLowerCase();
        statusElement.innerText = queue.status;
        statusElement.classList.remove('status-normal', 'status-busy', 'status-full');

        if (status === 'normal') {
            statusElement.classList.add('status-normal');
        } else if (status === 'busy') {
            statusElement.classList.add('status-busy');
        } else if (status === 'full') {
            statusElement.classList.add('status-full');
        }

        document.getElementById(`length-${queue.id}`).innerText = queue.participant_count;
        document.getElementById(`position-${queue.id}`).innerText = queue.position;
    });

    // Handle notifications
    data.notifications.forEach(notification => {
        openNotificationModal(notification);
    });
};

combinedEventSource.onerror = function (event) {
    console.error('Error with combined SSE:', event);
    combinedEventSource.close();
};

let currentNotificationId = null;

function openNotificationModal(notification) {
    const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
    const modalMessage = document.getElementById('modalMessage');
    modalMessage.innerText = `Your turn for ${notification.queue_name} is ready! Please proceed to the counter.`;
    currentNotificationId = notification.id;
    modal.show();
}

async function markAsRead(notificationId) {
    try {
        const response = await fetch(`/mark-as-read/${notificationId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        });

        if (!response.ok) {
            console.error("Failed to mark notification as read:", response.statusText);
        } else {
            console.log("Notification marked as read.");
        }
    } catch (error) {
        console.error("Error while marking notification as read:", error);
    }
}

document.getElementById('modalOkButton').addEventListener('click', function() {
    if (currentNotificationId) {
        markAsRead(currentNotificationId);
        currentNotificationId = null;
    }
    const modal = bootstrap.Modal.getInstance(document.getElementById('notificationModal'));
    modal.hide();
});

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

window.onload = function() {
};
