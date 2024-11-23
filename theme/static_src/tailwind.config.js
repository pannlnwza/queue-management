    module.exports = {
    content: [
        /**
         * HTML. Paths to Django template files that will contain Tailwind CSS classes.
         */

        // Templates within theme app (e.g., base.html)
        '../templates/**/*.html',

        // Main templates directory of the project
        '../../templates/**/*.html',

        // Templates in other Django apps
        '../../**/templates/**/*.html',

        './templates/**/*.{html,js}',
        './static/src/**/*.{js,css}',

        /**
         * JS: Tailwind CSS in JavaScript files.
         * Include all JavaScript files in the project and ignore node_modules.
         */
        '!../../**/node_modules', // Ignore JS files in node_modules
        '../../**/*.js', // Process all JavaScript files

        /**
         * Python: Tailwind CSS classes in Python files (e.g., dynamically generated classes).
         */
        '../../**/*.py', // Include all Python files
    ],
    theme: {
        extend: {},
    },
    plugins: [
        /**
         * Include plugins for additional utilities and components.
         */
        require('@tailwindcss/forms'),
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
        require('daisyui'),
    ],

    daisyui: {
        themes: ["light", "dracula"], // Specific themes for daisyUI
        base: true,
        styled: true,
        utils: true,
        prefix: "",
        logs: true,
        themeRoot: ":root",
    },
};
