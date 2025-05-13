/**
 * GENESIS Trading Platform - Theme Switcher
 * This script handles theme switching between light and dark modes.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Set up constants
    const LIGHT_THEME = 'light-theme';
    const DARK_THEME = 'dark-theme';
    const SYSTEM_THEME = 'system-theme';
    const THEME_STORAGE_KEY = 'genesis_theme';
    
    // Get DOM elements
    const themeRadios = document.querySelectorAll('input[name="theme"]');
    const themeForm = document.getElementById('appearance-form');
    
    // Function to detect system theme preference
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches 
            ? DARK_THEME 
            : LIGHT_THEME;
    }
    
    // Function to set active theme
    function setActiveTheme(themeName) {
        // Remove all possible theme classes
        document.body.classList.remove(LIGHT_THEME, DARK_THEME);
        
        // Apply the correct theme class
        if (themeName === SYSTEM_THEME) {
            // Use system preference
            document.body.classList.add(getSystemTheme());
        } else {
            document.body.classList.add(themeName);
        }
        
        // Store preference
        localStorage.setItem(THEME_STORAGE_KEY, themeName);
        
        console.log(`Theme set to: ${themeName}`);
    }
    
    // Initial theme setup
    function initializeTheme() {
        // Get saved theme or use default
        const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || LIGHT_THEME;
        
        // Set the appropriate radio button
        for (const radio of themeRadios) {
            if (radio.id === `theme-${savedTheme.split('-')[0]}`) {
                radio.checked = true;
                break;
            }
        }
        
        // Apply the theme
        setActiveTheme(savedTheme);
        
        // Listen for system theme changes if using system setting
        if (savedTheme === SYSTEM_THEME) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
                setActiveTheme(SYSTEM_THEME);
            });
        }
    }
    
    // Set up theme toggle handlers
    if (themeForm) {
        themeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get selected theme
            let selectedTheme = LIGHT_THEME;
            for (const radio of themeRadios) {
                if (radio.checked) {
                    if (radio.id === 'theme-light') selectedTheme = LIGHT_THEME;
                    else if (radio.id === 'theme-dark') selectedTheme = DARK_THEME;
                    else if (radio.id === 'theme-system') selectedTheme = SYSTEM_THEME;
                    break;
                }
            }
            
            // Apply the theme
            setActiveTheme(selectedTheme);
            
            // Show success alert
            const alertContainer = document.getElementById('alert-container');
            if (alertContainer) {
                alertContainer.innerHTML = `
                    <div class="alert alert-success alert-dismissible fade show" role="alert">
                        Theme settings saved successfully!
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                `;
            }
        });
    }
    
    // Initialize theme on page load
    initializeTheme();
});