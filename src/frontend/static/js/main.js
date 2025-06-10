// src/frontend/static/js/main.js

// Simple Application Namespace
window.App = {
    currentTaskIdToMonitor: null, // Stores the ID of the most recently submitted task from URL
    pollingIntervals: {},       // Stores interval IDs for active polling, keyed by taskId
    // Configuration
    config: {
        pollingIntervalTime: 3000, // Milliseconds for polling interval
        maxPollingAttempts: 100    // Example: Stop polling after ~5 minutes (100 * 3s) if still not final
    },
    pollingCounters: {} // Stores current polling attempt count for each task
};

// --- Task Status Polling Functions ---

/**
 * Fetches the status of a given Celery task from the backend API.
 * @param {string} taskId - The ID of the task to fetch status for.
 * @returns {Promise<object|null>} A promise that resolves to the task data object or null if a critical error occurs.
 */
async function fetchTaskStatus(taskId) {
    const taskElement = document.getElementById(`task-div-${taskId}`);
    // If the UI element for this task no longer exists, stop polling for it.
    if (!taskElement) {
        console.warn(`UI element for task ${taskId} not found. Stopping polling.`);
        if (App.pollingIntervals[taskId]) {
            clearInterval(App.pollingIntervals[taskId]);
            delete App.pollingIntervals[taskId];
            delete App.pollingCounters[taskId];
        }
        return null;
    }

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/status`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
            // Cookies (auth token) are sent automatically by the browser.
        });

        if (!response.ok) {
            let errorDetail = `HTTP error ${response.status}`;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || errorDetail;
            } catch (e) { /* Ignore if response is not JSON, use status code as detail */ }

            console.error(`Error fetching status for task ${taskId}: ${errorDetail}`);
            // Update UI to show error and indicate polling stopped.
            taskElement.innerHTML = `<p class="mb-0 text-danger">Task <strong>${taskId}</strong>: Error fetching status (${errorDetail}). Polling stopped.</p>`;
            taskElement.className = 'task-status-item alert alert-danger';
            return null; // Signal error to stop polling
        }
        return await response.json(); // Expected: { task_id, status, result, error_info }
    } catch (error) {
        console.error(`Network or other error fetching status for task ${taskId}:`, error);
        taskElement.innerHTML = `<p class="mb-0 text-danger">Task <strong>${taskId}</strong>: Network error fetching status. Polling stopped.</p>`;
        taskElement.className = 'task-status-item alert alert-danger';
        return null; // Signal error to stop polling
    }
}

/**
 * Updates the UI element for a specific task with new status and result data.
 * @param {string} taskId - The ID of the task whose UI needs updating.
 * @param {object} taskData - The task data object from fetchTaskStatus.
 */
function updateTaskUI(taskId, taskData) {
    const taskElement = document.getElementById(`task-div-${taskId}`);
    if (!taskElement) return; // Should have been caught by fetchTaskStatus, but defensive check.

    let statusMessage = taskData.status;
    // Add details from taskData.result if it's a simple message (often for PENDING/STARTED)
    if (taskData.result && typeof taskData.result.message === 'string' && (taskData.status === "PENDING" || taskData.status === "STARTED")) {
        statusMessage += ` - ${taskData.result.message}`;
    }

    let statusHtml = `<p class="mb-0">Task <strong>${taskId}</strong>: Status - <span class="font-weight-bold">${statusMessage}</span>`;

    let progressBarHtml = `
        <div class="progress mt-1" style="height: 8px;">
            <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%;" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100"></div>
        </div>`;

    taskElement.className = 'task-status-item alert'; // Reset to base alert class

    if (taskData.status === "SUCCESS") {
        statusHtml += `<br>Result: <pre class="mt-1 p-2 bg-light border rounded small">${JSON.stringify(taskData.result, null, 2)}</pre>`;
        taskElement.classList.add('alert-success');
        progressBarHtml = ''; // Remove progress bar
    } else if (taskData.status === "FAILURE") {
        const errorMsg = taskData.error_info ? (taskData.error_info.details || taskData.error_info.message) :
                         (taskData.result && typeof taskData.result === 'object' && taskData.result.error ? taskData.result.error :
                         (taskData.result ? JSON.stringify(taskData.result) : 'Unknown error'));
        statusHtml += `<br>Error: <pre class="mt-1 p-2 bg-light border rounded small text-danger">${errorMsg}</pre>`;
        taskElement.classList.add('alert-danger');
        progressBarHtml = ''; // Remove progress bar
    } else if (["PENDING", "STARTED", "RETRY"].includes(taskData.status)) {
        taskElement.classList.add('alert-info');
        // Keep progress bar for ongoing tasks
    } else { // Other states (e.g., REVOKED, or custom states)
        taskElement.classList.add('alert-warning');
        if (taskData.result) {
            statusHtml += `<br>Info: <pre class="mt-1 p-2 bg-light border rounded small">${JSON.stringify(taskData.result, null, 2)}</pre>`;
        }
        progressBarHtml = ''; // Remove progress bar for non-active states
    }

    statusHtml += `</p>${progressBarHtml}`;
    taskElement.innerHTML = statusHtml;
}

/**
 * Starts polling for the status of a given Celery task.
 * @param {string} taskId - The ID of the task to poll.
 */
function startPollingForTask(taskId) {
    if (!taskId) return;

    if (App.pollingIntervals[taskId]) { // Clear existing interval if any
        clearInterval(App.pollingIntervals[taskId]);
    }
    App.pollingCounters[taskId] = 0; // Reset/initialize polling attempt counter

    console.log(`Starting polling for task ${taskId}`);

    // Ensure initial UI element exists or create it
    let taskElement = document.getElementById(`task-div-${taskId}`);
    const taskStatusArea = document.getElementById('task-status-area'); // Defined in DOMContentLoaded
    const initialGlobalMessageEl = document.getElementById('initial-task-message'); // Defined in DOMContentLoaded

    if (!taskElement && taskStatusArea) {
        if (initialGlobalMessageEl) initialGlobalMessageEl.style.display = 'none';

        taskElement = document.createElement('div');
        taskElement.id = `task-div-${taskId}`;
        taskElement.className = 'task-status-item alert alert-info';
        // Initial message is now set by DOMContentLoaded or updated immediately by first poll.
        // This just ensures the div exists.
        taskStatusArea.appendChild(taskElement);
    }

    // Perform an immediate first fetch and UI update
    (async () => {
        const initialTaskData = await fetchTaskStatus(taskId);
        if (initialTaskData) {
            updateTaskUI(taskId, initialTaskData);
            const finalStates = ["SUCCESS", "FAILURE", "REVOKED"];
            if (finalStates.includes(initialTaskData.status)) {
                console.log(`Task ${taskId} already in final state ${initialTaskData.status} on first check. No polling needed.`);
                return; // Don't start interval if already final
            }
        } else { // fetchTaskStatus returned null (error or element gone)
            return; // Don't start interval
        }

        // If not final, then start interval
        App.pollingIntervals[taskId] = setInterval(async () => {
            App.pollingCounters[taskId]++;
            console.log(`Polling for task ${taskId} (Attempt: ${App.pollingCounters[taskId]})...`);
            const taskData = await fetchTaskStatus(taskId);

            if (taskData) {
                updateTaskUI(taskId, taskData);
                const finalStates = ["SUCCESS", "FAILURE", "REVOKED"];
                if (finalStates.includes(taskData.status) || App.pollingCounters[taskId] >= App.config.maxPollingAttempts) {
                    if (App.pollingCounters[taskId] >= App.config.maxPollingAttempts && !finalStates.includes(taskData.status)) {
                        console.warn(`Stopping polling for task ${taskId} after ${App.config.maxPollingAttempts} attempts (still in state ${taskData.status}).`);
                        if(taskElement) { // Update UI to reflect timeout
                             taskElement.innerHTML += `<p class="text-warning small mt-1">Polling timed out. Status: ${taskData.status}.</p>`;
                             const progressBar = taskElement.querySelector('.progress');
                             if(progressBar) progressBar.remove();
                        }
                    } else {
                        console.log(`Stopping polling for task ${taskId} due to final state: ${taskData.status}`);
                    }
                    clearInterval(App.pollingIntervals[taskId]);
                    delete App.pollingIntervals[taskId];
                    delete App.pollingCounters[taskId];
                }
            } else {
                console.log(`Stopping polling for task ${taskId} due to fetch error or missing UI element (interval).`);
                clearInterval(App.pollingIntervals[taskId]);
                delete App.pollingIntervals[taskId];
                delete App.pollingCounters[taskId];
            }
        }, App.config.pollingIntervalTime);
    })(); // IIFE to run the async immediate check
}

// --- DOMContentLoaded ---
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed. main.js is active.");

    // Cache frequently accessed DOM elements
    const taskStatusArea = document.getElementById('task-status-area');
    const initialTaskMessageEl = document.getElementById('initial-task-message');
    const connectM365Btn = document.getElementById('connect-m365-btn');
    const disconnectM365Form = document.getElementById('disconnect-m365-form');
    const m365ActionFeedback = document.getElementById('m365-action-feedback');

    App.currentTaskIdToMonitor = null; // Reset on page load

    // --- Handle Submitted Task from URL ---
    const urlParams = new URLSearchParams(window.location.search);
    const submittedTaskIdFromUrl = urlParams.get('submitted_task_id');
    const messageFromQuery = urlParams.get('message');

    if (submittedTaskIdFromUrl) {
        console.log("Found submitted_task_id in URL:", submittedTaskIdFromUrl);
        if (taskStatusArea) {
            if (initialTaskMessageEl) initialTaskMessageEl.style.display = 'none';

            let taskDiv = document.getElementById(`task-div-${submittedTaskIdFromUrl}`);
            if (!taskDiv) {
                taskDiv = document.createElement('div');
                taskDiv.id = `task-div-${submittedTaskIdFromUrl}`;
                taskDiv.className = 'task-status-item alert alert-info'; // Initial class
                taskStatusArea.appendChild(taskDiv);
            }
            // Initial message using message from query param if available and task-related
            const initialText = messageFromQuery && messageFromQuery.toLowerCase().includes("task id:") ?
                                messageFromQuery : // Use full message if it already mentions task
                                (messageFromQuery ? `${messageFromQuery} (Task ID: ${submittedTaskIdFromUrl})` : `Task <strong>${submittedTaskIdFromUrl}</strong> submitted.`);

            taskDiv.innerHTML = `<p class="mb-0">${initialText} Waiting for status...</p>
                                 <div class="progress mt-1" style="height: 8px;">
                                     <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%"></div>
                                 </div>`;

            App.currentTaskIdToMonitor = submittedTaskIdFromUrl;
        }

        // Clean specific query params from URL
        const newUrlParams = new URLSearchParams(window.location.search);
        newUrlParams.delete('submitted_task_id');
        if (messageFromQuery && (messageFromQuery.toLowerCase().includes("task id:") || messageFromQuery.toLowerCase().includes("queued") || messageFromQuery.toLowerCase().includes("started"))) {
            newUrlParams.delete('message');
        }
        let newSearch = newUrlParams.toString();
        const newUrl = `${window.location.pathname}${newSearch ? '?' + newSearch : ''}`;
        if (window.location.href !== newUrl) {
             window.history.replaceState({}, document.title, newUrl);
        }
    } else { // No specific task submitted via URL
        if (initialTaskMessageEl && taskStatusArea && taskStatusArea.children.length <= 1) {
            // Only show "No new tasks" if no other general message (like login success) is present AND no tasks are already shown
            if (!messageFromQuery && !urlParams.get('error')) {
                initialTaskMessageEl.textContent = "No new tasks currently being monitored.";
                initialTaskMessageEl.style.display = 'block';
            } else if (initialTaskMessageEl) {
                 initialTaskMessageEl.style.display = 'none';
            }
        } else if (initialTaskMessageEl) {
             initialTaskMessageEl.style.display = 'none';
        }
    }

    if (App.currentTaskIdToMonitor) {
        startPollingForTask(App.currentTaskIdToMonitor);
    }

    // --- M365 Connection UI Logic ---
    if (connectM365Btn && m365ActionFeedback) {
        connectM365Btn.addEventListener('click', function(event) {
            if (this.classList.contains('disabled')) {
                event.preventDefault(); return;
            }
            this.classList.add('disabled');
            this.setAttribute('aria-disabled', 'true');
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Redirecting...';
            m365ActionFeedback.className = 'text-info small mt-2 d-block';
            m365ActionFeedback.textContent = 'Redirecting to Microsoft for authorization... Please wait.';
        });
    }

    if (disconnectM365Form && m365ActionFeedback) {
        disconnectM365Form.addEventListener('submit', function() {
            const disconnectBtn = document.getElementById('disconnect-m365-btn');
            if (disconnectBtn) {
                disconnectBtn.disabled = true;
                disconnectBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
            m365ActionFeedback.className = 'text-info small mt-2 d-block';
            m365ActionFeedback.textContent = 'Processing disconnection... Please wait.';
        });
    }

    // Clear M365 specific feedback if a general page message exists that isn't about M365 connection itself.
    if (m365ActionFeedback && messageFromQuery && !messageFromQuery.toLowerCase().includes("m365")) {
        m365ActionFeedback.textContent = '';
    }
});
```
