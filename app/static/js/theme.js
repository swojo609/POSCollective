const themeToggle = document.getElementById("theme-toggle");
const root = document.documentElement;

function setTheme(theme) {
    root.dataset.theme = theme;

    if (themeToggle) {
        themeToggle.setAttribute("aria-checked", theme === "dark");
    }

    localStorage.setItem("theme", theme);
}

const savedTheme = localStorage.getItem("theme") || "light";
setTheme(savedTheme);

if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const currentTheme = root.dataset.theme;
        const newTheme = currentTheme === "dark" ? "light" : "dark";

        setTheme(newTheme);
    });
}