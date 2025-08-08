// Fade-in animation when scrolling
const fadeElements = document.querySelectorAll('.fade-in');

const appearOptions = {
    threshold: 0.2,
    rootMargin: "0px 0px -50px 0px"
};

const appearOnScroll = new IntersectionObserver(function(entries, observer) {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('appear');
        observer.unobserve(entry.target);
    });
}, appearOptions);

fadeElements.forEach(el => {
    appearOnScroll.observe(el);
});

// Copy route to clipboard
document.querySelectorAll("td").forEach(cell => {
    cell.addEventListener("click", function() {
        const text = cell.innerText;
        navigator.clipboard.writeText(text).then(() => {
            showTooltip(cell, "Copied!");
        }).catch(err => console.error("Copy failed", err));
    });
});

// Tooltip notification
function showTooltip(element, message) {
    let tooltip = document.createElement("span");
    tooltip.className = "tooltip";
    tooltip.innerText = message;
    element.appendChild(tooltip);

    setTimeout(() => {
        tooltip.remove();
    }, 1500);
}
