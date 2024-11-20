// static/js/theme-toggle.js
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const themeToggle = document.querySelector('.theme-controller');
    if (themeToggle) themeToggle.checked = theme === 'dark';
}

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
});

document.addEventListener('change', (e) => {
    if (e.target.classList.contains('theme-controller')) {
        const newTheme = e.target.checked ? 'dark' : 'light';
        setTheme(newTheme);
    }
});

function copyToClipboard() {
        // Get the text from the paragraph with id 'joinLink'
        const joinLink = document.getElementById("joinLink").innerText;

        // Copy the text to clipboard
        navigator.clipboard.writeText(joinLink).then(() => {
            alert("Link copied to clipboard!");
        }).catch(err => {
            console.error("Failed to copy: ", err);
        });
    }
