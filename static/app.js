/*
Frontend polling for the DistRes web client.

The browser talks to Flask over HTTP. Flask talks to the DistRes TCP server.
*/

function updateList(listElementId, emptyElementId, items) {
    const list = document.getElementById(listElementId);
    const empty = document.getElementById(emptyElementId);

    if (!list || !empty) return;

    list.innerHTML = "";

    if (!items || items.length === 0) {
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

function showNotification(message) {
    const panel = document.getElementById("notification-panel");
    if (!panel) return;

    panel.textContent = message;
    panel.style.display = "block";
}

function startWaitingPagePolling() {
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

            if (data.status === "server_unavailable") {
                statusText.textContent = "DistRes TCP server is unavailable.";
                return;
            }

            window.location.href = "/";
        } catch (error) {
            statusText.textContent = "Error checking queue status.";
        }
    }, 2000);
}

function startDashboardPolling() {
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
            updateList("file-queue-list", "file-queue-empty", data.file_queue || []);
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

function startNotificationPolling() {
    setInterval(async () => {
        try {
            const response = await fetch("/notifications");
            const data = await response.json();

            (data.notifications || []).forEach(notification => {
                if (notification.type === "promotion") {
                    window.location.href = "/dashboard";
                    return;
                }

                if (notification.type === "resource_updated") {
                    const updatedBy = notification.updated_by || "another user";
                    showNotification(`${notification.message} Updated by ${updatedBy}.`);
                }

                if (notification.type === "file_access_granted") {
                    if (notification.mode === "write") {
                        showNotification("Write access granted. Opening editor...");
                        window.location.href = "/edit-document";
                        return;
                    }

                    if (notification.mode === "read") {
                        showNotification("Read access granted. Opening document...");
                        window.location.href = "/document";
                    }
                }
            });
        } catch (error) {
            console.error("Notification refresh failed:", error);
        }
    }, 2000);
}

function leaveFileModeOnUnload() {
    navigator.sendBeacon("/leave-file-mode");
}

function setupFileModeCleanup(pageType) {
    if (pageType !== "document" && pageType !== "edit-document") {
        return;
    }

    window.addEventListener("beforeunload", leaveFileModeOnUnload);

    const editForm = document.getElementById("edit-document-form");
    if (editForm) {
        editForm.addEventListener("submit", () => {
            window.removeEventListener("beforeunload", leaveFileModeOnUnload);
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const pageType = document.body.dataset.page;

    if (pageType === "waiting") {
        startWaitingPagePolling();
        startNotificationPolling();
    }

    if (pageType === "dashboard") {
        startDashboardPolling();
        startNotificationPolling();
    }

    setupFileModeCleanup(pageType);
});
