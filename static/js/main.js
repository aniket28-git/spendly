// Toast auto-dismiss and close button
(function () {
    const AUTO_DISMISS_MS = 4000;

    function dismissToast(toast) {
        toast.classList.add("toast-hiding");
        toast.addEventListener("transitionend", () => toast.remove(), { once: true });
    }

    document.querySelectorAll(".toast").forEach(function (toast) {
        const timer = setTimeout(() => dismissToast(toast), AUTO_DISMISS_MS);

        toast.querySelector(".toast-close").addEventListener("click", function () {
            clearTimeout(timer);
            dismissToast(toast);
        });
    });
}());
