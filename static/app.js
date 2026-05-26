/*
Frontend polling and UI update logic for the concurrency system.

Handles live updates for the waiting queue, dashboard state,
file access waiting messages, and file-mode cleanup when leaving pages.
*/

function updateList(listElementId, emptyElementId, items) {
    // Rebuilds a list element from live data and toggles its empty message.
    const list = document.getElementById(listElementId);
    const empty = document.getElementById(emptyElementId);

    if (!list || !empty) return;

    list.innerHTML = "";

    if (items.length === 0) {
        empty.style.display = "block";
        return;
    }

    empty.style.display = "none";

    items.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
    });
}

function startWaitingPagePolling() {
    // Polls the queue endpoint so waiting users can be promoted automatically.
    const statusText = document.getElementById("queue-status-text");
    if (!statusText) return;

    setInterval(async () => {
        try {
            const response = await fetch("/queue-status");
            const data = await response.json();

            if (data.status === "active") {
                statusText.textContent = "A slot is now free. Redirecting to dashboard...";
                window.location.href = "/dashboard";
                return;
            }

            if (data.status === "waiting") {
                if (data.position !== null && data.position !== undefined) {
                    statusText.textContent = `You are still waiting. Queue position: ${data.position}`;
                } else {
                    statusText.textContent = "You are still waiting for a free slot.";
                }
                return;
            }

            window.location.href = "/";
        } catch (error) {
            statusText.textContent = "Error checking queue status.";
        }
    }, 2000);
}

function startDashboardPolling() {
    // Refreshes all live system state shown on the dashboard.
    setInterval(async () => {
        try {
            const response = await fetch("/system-state");

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));

                if (data.error === "not_active") {
                    window.location.href = "/waiting";
                    return;
                }

                window.location.href = "/";
                return;
            }

            const data = await response.json();

            updateList("active-users-list", "active-users-empty", data.active_users || []);
            updateList("waiting-users-list", "waiting-users-empty", data.waiting_users || []);
            updateList("active-readers-list", "active-readers-empty", data.active_readers || []);
            updateSingleItemList("active-writer-list", "active-writer-empty", data.active_writer || null);

            const fileStatus = document.getElementById("file-status");
            if (fileStatus) {
                fileStatus.textContent = data.file_status || "Idle";
            }
        } catch (error) {
            console.error("Dashboard refresh failed:", error);
        }
    }, 2000);
}

document.addEventListener("DOMContentLoaded", () => {
    const pageType = document.body.dataset.page;

    if (pageType === "waiting") {
        startWaitingPagePolling();
    }

    if (pageType === "dashboard") {
        startDashboardPolling();
    }
});

function updateSingleItemList(listElementId, emptyElementId, item) {
    const list = document.getElementById(listElementId);
    const empty = document.getElementById(emptyElementId);

    if (!list || !empty) return;

    list.innerHTML = "";

    if (!item) {
        empty.style.display = "block";
        return;
    }

    empty.style.display = "none";

    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
}

function leaveFileModeOnUnload() {
    // Best-effort cleanup so read/write modes are released when leaving the page.
    navigator.sendBeacon("/leave-file-mode");
}

document.addEventListener("DOMContentLoaded", () => {
    // Enable only the polling relevant to the current page.
    const pageType = document.body.dataset.page;

    if (pageType === "waiting") {
        startWaitingPagePolling();
    }

    if (pageType === "dashboard") {
        startDashboardPolling();
    }

    if (pageType === "document" || pageType === "edit-document") {
        window.addEventListener("beforeunload", leaveFileModeOnUnload);
    }
});